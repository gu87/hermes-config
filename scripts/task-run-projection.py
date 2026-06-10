#!/usr/bin/env python3
"""
Hermes Unified Task/Run Contract — Phase 1A

Pure data models, deterministic ID functions, and pure mapping functions
for the Task Card Pipeline shadow projection.

Implements §4 and §5.2 of docs/architecture/unified-task-run-contract.md.

Phase 1A scope:
  - @dataclass definitions for all unified model entities
  - Deterministic ID generators (no random UUID/ULID)
  - Pure mapping functions for Task Card, ledger, and gate records
  - NO file I/O, NO network, NO imports from Pipeline/Kanban/Gateway/Desktop
  - NO CLI, NO file scanning, NO JSONL output, NO shadow projection writer

Design invariants (Phase 1A):
  - Determinism: same inputs → exactly the same outputs. NO datetime.now(),
    NO random, NO guessing, NO fake data.
  - Missing required fields → MappingError. Missing optional fields → None.
  - ReviewDecision.run_id and Evidence.run_id are Optional[str]; None when
    the original gate record has no run_id.
  - Unknown gate decision → UnsupportedRecord, never silently mapped to 'reject'.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union


# ---------------------------------------------------------------------------
# 1.  Deterministic ID Functions  (§5.2.1)
# ---------------------------------------------------------------------------

def task_id(project_id: str, source_task_id: str) -> str:
    """Return deterministic namespaced task ID.

    Format: pipeline:{project_id}:task:{source_task_id}

    >>> task_id("staam", "staam_t6")
    'pipeline:staam:task:staam_t6'
    """
    if not project_id or not source_task_id:
        raise ValueError("project_id and source_task_id are required")
    return f"pipeline:{project_id}:task:{source_task_id}"


def run_id(project_id: str, source_run_id: str) -> str:
    """Return deterministic namespaced run ID.

    Format: pipeline:{project_id}:run:{source_run_id}

    >>> run_id("staam", "run_t6_20260307_152200_123456")
    'pipeline:staam:run:run_t6_20260307_152200_123456'
    """
    if not project_id or not source_run_id:
        raise ValueError("project_id and source_run_id are required")
    return f"pipeline:{project_id}:run:{source_run_id}"


def event_id(project_id: str, source_file: str, source_record_identity: str) -> str:
    """Return deterministic SHA-256-based event ID.

    Computes SHA-256("pipeline:{project_id}:{source_file}:{source_record_identity}")
    and returns the first 32 hex characters.

    Same inputs always produce the same ID.

    Raises ValueError if any argument is empty — empty identity causes collisions.
    """
    if not project_id or not source_file or not source_record_identity:
        raise ValueError(
            "project_id, source_file, and source_record_identity "
            "are all required and must be non-empty"
        )
    raw = f"pipeline:{project_id}:{source_file}:{source_record_identity}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _require_nonempty(value: str, label: str) -> str:
    """Validate that a string is non-empty; raise ValueError otherwise."""
    if not value or not str(value).strip():
        raise ValueError(f"{label} must be non-empty")
    return str(value).strip()


# ---------------------------------------------------------------------------
# 2.  Data Models  (§4.2)
# ---------------------------------------------------------------------------

# --- Enums as string literals ---

TaskStatus = str  # 'draft' | 'queued' | 'running' | 'needs_review' | 'done' | 'failed' | 'blocked' | 'cancelled'
RunType = str     # 'main' | 'review' | 'qa' | 'gate' | 'retry' | 'revision'
RunStatus = str   # 'created' | 'queued' | 'starting' | 'running' | 'waiting_review' | 'completed' | 'failed' | 'cancelled'
TaskRelationType = str  # 'parent_child' | 'swarm' | 'revision'
RunRelationType = str   # 'delegated' | 'review' | 'qa' | 'gate' | 'retry'
TaskSource = str  # 'desktop' | 'cli' | 'feishu' | 'discord' | 'api' | 'scheduler'


# --- Core entities ---

@dataclass
class Task:
    """§4.2.2"""
    id: str
    project_id: str
    title: str
    status: TaskStatus
    created_at: str
    body: Optional[str] = None
    updated_at: Optional[str] = None
    root_task_id: Optional[str] = None  # revision task 始终指向根 Task


@dataclass
class TaskSpec:
    """§4.2.3"""
    task_id: str
    interpreted_intent: str = ""
    real_task: str = ""
    task_category: str = ""
    risk_level: str = ""
    execution_mode: str = ""
    primary_agent: str = ""
    agents: List[str] = field(default_factory=list)
    output_schema_version: str = ""
    required_output_fields: List[str] = field(default_factory=list)
    allowed_files: List[str] = field(default_factory=list)
    must_keep: List[str] = field(default_factory=list)
    must_change: List[str] = field(default_factory=list)
    must_avoid: List[str] = field(default_factory=list)
    success_criteria: List[str] = field(default_factory=list)


@dataclass
class TaskRelation:
    """§4.2.5"""
    id: str
    parent_task_id: str
    child_task_id: str
    relation_type: TaskRelationType
    created_at: str


@dataclass
class Run:
    """§4.2.6 — core fields only; private metadata in sub-structures below."""
    id: str
    task_id: str
    run_type: RunType
    executor_id: str
    agent_id: str
    status: RunStatus
    base_path: str
    created_at: str
    parent_run_id: Optional[str] = None
    run_seq: Optional[int] = None
    outcome: Optional[str] = None
    summary: Optional[str] = None
    error_summary: Optional[str] = None
    started_at: Optional[str] = None
    ended_at: Optional[str] = None


# --- Run sub-structures (§4.2.7) ---

@dataclass
class RunExecutionRef:
    """§4.2.7"""
    run_id: str
    source_system: str
    external_run_id: Optional[str] = None


@dataclass
class SchedulerMetadata:
    """§4.2.7"""
    run_id: str
    claim_lock: Optional[str] = None
    claim_expires: Optional[int] = None
    worker_pid: Optional[int] = None
    max_runtime_seconds: Optional[int] = None
    last_heartbeat_at: Optional[int] = None


@dataclass
class ProcessMetadata:
    """§4.2.7"""
    run_id: str
    command: Optional[str] = None
    cwd: Optional[str] = None
    exit_code: Optional[int] = None
    classification: Optional[str] = None
    model: Optional[str] = None
    profile: Optional[str] = None
    git_snapshot: Optional[str] = None
    worktree_path: Optional[str] = None
    timeout_seconds: Optional[float] = None


@dataclass
class RunRelation:
    """§4.2.8"""
    id: str
    parent_run_id: str
    child_run_id: str
    relation_type: RunRelationType
    created_at: str


# --- Events, Artifacts, Evidence, Review ---

@dataclass
class DomainEventEnvelope:
    """§4.2.9"""
    event_id: str
    event_scope: str  # 'task' | 'run'
    event_type: str
    task_id: str
    source: str       # 'pipeline' | 'kanban' | 'desktop' | 'delegate_task' | 'gateway'
    occurred_at: str
    schema_version: str
    payload: Dict[str, Any] = field(default_factory=dict)
    run_id: Optional[str] = None
    parent_run_id: Optional[str] = None
    source_event_id: Optional[str] = None
    source_location: Optional[str] = None


@dataclass
class Artifact:
    """§4.2.10 — task_id required; run_id and created_at optional."""
    id: str
    task_id: str
    artifact_type: str
    run_id: Optional[str] = None
    path: Optional[str] = None
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    checksum: Optional[str] = None
    created_at: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class Evidence:
    """§4.2.10 — task_id required; run_id optional."""
    task_id: str
    run_id: Optional[str] = None
    commands_run: List[str] = field(default_factory=list)
    test_results: Optional[Dict[str, Any]] = None
    verification_output: Optional[str] = None
    coverage_delta: Optional[str] = None
    risks: List[str] = field(default_factory=list)


@dataclass
class ReviewDecision:
    """§4.2.11 — task_id required; run_id optional."""
    id: str
    task_id: str
    reviewer: str
    decision: str  # 'approve' | 'needs_revision' | 'reject'
    summary: str
    decided_at: str
    run_id: Optional[str] = None
    failed_checks: List[Dict[str, Any]] = field(default_factory=list)
    revision_instructions: List[str] = field(default_factory=list)


# --- Error / unsupported signalling types (§5.2.5 rule 4) ---

@dataclass
class UnsupportedRecord:
    """Explicit signal that a record cannot be mapped — not an error, not silent."""
    reason: str
    source_location: Optional[str] = None
    raw_record_summary: str = ""


@dataclass
class MappingError:
    """Explicit signal that mapping failed due to invalid or corrupt input."""
    error: str
    source_location: Optional[str] = None
    raw_record_summary: str = ""


# ---------------------------------------------------------------------------
# 3.  Pure Mapping Functions  (§5.2.5)
# ---------------------------------------------------------------------------

# ProjectionResult = Union of any entity or error sentinel
ProjectionResult = Union[
    Task, TaskSpec, TaskRelation, Run, RunRelation,
    RunExecutionRef, SchedulerMetadata, ProcessMetadata,
    DomainEventEnvelope, Artifact, Evidence, ReviewDecision,
    UnsupportedRecord, MappingError,
]

# Known Pipeline gate decisions → unified decision mapping
_GATE_DECISION_MAP = {
    "approved": "approve",
    "revision_needed": "needs_revision",
    "rejected": "reject",
}


def _extract_task_card_id(record: Dict[str, Any]) -> Optional[str]:
    """Best-effort extraction of source task_card_id from a Task Card dict."""
    return record.get("task_card_id") or record.get("task_id")


def _extract_revision_of(record: Dict[str, Any]) -> Optional[str]:
    """Return the original task_id that a revision task card was derived from."""
    revision = record.get("revision")
    if isinstance(revision, dict):
        return revision.get("of_task_id")
    return None


def _classification_from_ledger(record: Dict[str, Any]) -> Optional[str]:
    return record.get("classification")


def _exit_code_from_ledger(record: Dict[str, Any]) -> Optional[int]:
    ec = record.get("exit_code")
    if ec is None:
        return None
    try:
        return int(ec)
    except (TypeError, ValueError):
        return None


def _iso_timestamp(record: Dict[str, Any], key: str) -> Optional[str]:
    """Normalise a timestamp field to ISO 8601 string, or None if absent."""
    val = record.get(key)
    if val is None:
        return None
    return str(val)


def _require_timestamp(
    record: Dict[str, Any], key: str, context: str, source_location: Optional[str] = None
) -> Union[str, MappingError]:
    """Extract a required timestamp; returns MappingError if missing."""
    val = _iso_timestamp(record, key)
    if not val:
        return MappingError(
            error=f"{context}: missing required timestamp '{key}'",
            source_location=source_location,
            raw_record_summary=str(record)[:200],
        )
    return val


def _mapping_error(error: str, record: Dict[str, Any], source_location: Optional[str] = None) -> MappingError:
    return MappingError(
        error=error,
        source_location=source_location,
        raw_record_summary=str(record)[:200],
    )


def _is_error(result: Any) -> bool:
    """Check if a value is a MappingError or UnsupportedRecord."""
    return isinstance(result, (MappingError, UnsupportedRecord))


# ---------------------------------------------------------------------------
# 3.1  map_task_card
# ---------------------------------------------------------------------------

def map_task_card(
    project_id: str,
    parsed_record: Dict[str, Any],
    source_location: Optional[str] = None,
) -> List[ProjectionResult]:
    """Map a Pipeline Task Card (inbox JSON) to unified model entities.

    Produces:
      - Task (always, requires created_at)
      - TaskSpec (when compiled_intent fields are present)
      - TaskRelation(type=revision) (when this is a revision task card)

    Rules (§5.2.2, §5.2.5):
      - Revision Task gets its own task_id; root_task_id points to the root.
      - No file I/O, no network, no Pipeline imports.
      - Missing required timestamps → MappingError (no datetime.now() fallback).
      - Unsupported or malformed records → UnsupportedRecord / MappingError.
    """
    if not isinstance(parsed_record, dict):
        return [_mapping_error(
            f"map_task_card requires a dict, got {type(parsed_record).__name__}",
            {},
            source_location,
        )]

    source_task_id = _extract_task_card_id(parsed_record)
    if not source_task_id:
        return [_mapping_error(
            "Task Card missing task_card_id and task_id",
            parsed_record,
            source_location,
        )]

    # Required timestamp — no datetime.now() fallback
    created_at_or_err = _require_timestamp(parsed_record, "created_at", "Task Card", source_location)
    if _is_error(created_at_or_err):
        return [created_at_or_err]  # type: ignore[return-value]
    created_at = created_at_or_err  # type: str

    result: List[ProjectionResult] = []

    # --- Task ---
    tid = task_id(project_id, source_task_id)
    revision_of = _extract_revision_of(parsed_record)
    root_tid = task_id(project_id, revision_of) if revision_of else None

    goal_text = str(parsed_record.get("goal") or parsed_record.get("title") or source_task_id)
    updated_at = _iso_timestamp(parsed_record, "updated_at") or created_at

    task = Task(
        id=tid,
        project_id=project_id,
        title=goal_text[:200],
        body=parsed_record.get("body"),
        status="draft",
        created_at=created_at,
        updated_at=updated_at,
        root_task_id=root_tid or tid,
    )
    result.append(task)

    # --- TaskSpec (best-effort from compiled_intent) ---
    compiled = parsed_record.get("compiled_intent")
    if isinstance(compiled, dict):
        plan = parsed_record.get("execution_plan") or {}
        contract = parsed_record.get("output_contract") or {}
        spec = TaskSpec(
            task_id=tid,
            interpreted_intent=str(compiled.get("interpreted_intent") or ""),
            real_task=str(compiled.get("real_task") or ""),
            task_category=str(compiled.get("task_category") or ""),
            risk_level=str(compiled.get("risk_level") or ""),
            execution_mode=str(plan.get("mode") or plan.get("execution_mode") or ""),
            primary_agent=str(plan.get("primary_agent") or compiled.get("preferred_agent") or ""),
            agents=(
                list(plan["agents"]) if isinstance(plan.get("agents"), list)
                else [plan["primary_agent"]] if plan.get("primary_agent")
                else []
            ),
            output_schema_version=str(contract.get("schema_version") or contract.get("schema") or ""),
            required_output_fields=(
                list(contract["required_fields"]) if isinstance(contract.get("required_fields"), list)
                else []
            ),
            allowed_files=(
                list(parsed_record["allowed_files"]) if isinstance(parsed_record.get("allowed_files"), list)
                else []
            ),
            must_keep=(
                list(compiled["must_keep"]) if isinstance(compiled.get("must_keep"), list)
                else []
            ),
            must_change=(
                list(compiled["must_change"]) if isinstance(compiled.get("must_change"), list)
                else []
            ),
            must_avoid=(
                list(compiled["must_avoid"]) if isinstance(compiled.get("must_avoid"), list)
                else []
            ),
            success_criteria=(
                list(compiled["success_criteria"]) if isinstance(compiled.get("success_criteria"), list)
                else []
            ),
        )
        result.append(spec)

    # --- TaskRelation(type=revision) ---
    if revision_of:
        parent_tid = task_id(project_id, revision_of)
        rel = TaskRelation(
            id=f"tr_{tid}_revision",
            parent_task_id=parent_tid,
            child_task_id=tid,
            relation_type="revision",
            created_at=created_at,
        )
        result.append(rel)

    return result


# ---------------------------------------------------------------------------
# 3.2  map_ledger_record
# ---------------------------------------------------------------------------

def map_ledger_record(
    project_id: str,
    parsed_record: Dict[str, Any],
    source_location: Optional[str] = None,
) -> List[ProjectionResult]:
    """Map a single ledger.jsonl record to unified model entities.

    Handles:
      - lifecycle_event → DomainEventEnvelope (event_scope=task)
      - run_started     → Run (status=running) + RunExecutionRef + ProcessMetadata
                          + DomainEventEnvelope (event_scope=run)
      - run_finished    → Run (status=completed/failed) + DomainEventEnvelope

    Rules (§5.2.3, §5.2.5):
      - Only generates Run when run_id is present.
      - run_seq is always None (no reliable seq in Pipeline).
      - No fake Runs for records without run_id.
      - No RunRelation(revision_dispatch).
      - Missing timestamps → MappingError (no datetime.now() fallback).
      - lifecycle_event with no stable event_id → MappingError.
    """
    if not isinstance(parsed_record, dict):
        return [_mapping_error(
            "map_ledger_record requires a dict",
            {},
            source_location,
        )]

    event = parsed_record.get("event")
    if not event:
        return [_mapping_error("ledger record missing 'event' field", parsed_record, source_location)]

    result: List[ProjectionResult] = []
    source_task_id = str(parsed_record.get("task_id") or "unknown")
    tid = task_id(project_id, source_task_id)

    if event == "lifecycle_event":
        # Must have a stable event_id for deterministic event identity.
        raw_event_id = parsed_record.get("event_id")
        if not raw_event_id or not str(raw_event_id).strip():
            return [_mapping_error(
                "lifecycle_event missing stable event_id — cannot generate deterministic DomainEventEnvelope",
                parsed_record,
                source_location,
            )]

        occurred_or_err = _require_timestamp(parsed_record, "started_at", "lifecycle_event", source_location)
        if _is_error(occurred_or_err):
            return [occurred_or_err]  # type: ignore[return-value]
        occurred = occurred_or_err  # type: str

        phase = str(parsed_record.get("phase", "")).strip()
        if not phase:
            return [_mapping_error(
                "lifecycle_event missing phase field",
                parsed_record,
                source_location,
            )]
        if phase not in _SUPPORTED_LIFECYCLE_PHASES:
            return [UnsupportedRecord(
                reason=f"unknown lifecycle phase (not in Phase 1 whitelist): {phase!r}",
                source_location=source_location,
                raw_record_summary=str(parsed_record)[:200],
            )]
        # For ledger lifecycle_event, the execution run is related_run_id.
        # The lifecycle's own run_id (same as event_id) is NOT an execution run.
        ledger_execution_run_id = str(parsed_record.get("related_run_id") or "").strip() or None
        norm_tid, norm_rid, norm_scope, norm_type, norm_payload = _normalize_lifecycle(
            project_id, parsed_record, phase_or_kind=phase,
            execution_run_id=ledger_execution_run_id,
        )

        ev = DomainEventEnvelope(
            event_id=event_id(project_id, "ledger.jsonl", str(raw_event_id)),
            event_scope=norm_scope,
            event_type=norm_type,
            task_id=norm_tid,
            run_id=norm_rid if norm_scope == "run" else None,
            source="pipeline",
            occurred_at=occurred,
            schema_version=parsed_record.get("schema_version", "2.8"),
            payload=norm_payload,
            source_event_id=str(raw_event_id),
            source_location=source_location,
        )
        result.append(ev)
        return result

    if event == "run_started":
        source_run_id = parsed_record.get("run_id")
        if not source_run_id:
            return [_mapping_error("run_started record missing run_id", parsed_record, source_location)]

        occurred_or_err = _require_timestamp(parsed_record, "started_at", "run_started", source_location)
        if _is_error(occurred_or_err):
            return [occurred_or_err]  # type: ignore[return-value]
        occurred = occurred_or_err  # type: str

        rid = run_id(project_id, source_run_id)
        agent = str(parsed_record.get("agent_id") or "unknown")
        run_type_val = str(parsed_record.get("run_type") or "main")
        cwd = str(parsed_record.get("cwd") or "")

        r = Run(
            id=rid,
            task_id=tid,
            parent_run_id=None,
            run_seq=None,
            run_type=run_type_val,
            executor_id="hermes-local",
            agent_id=agent,
            status="running",
            base_path=cwd,
            created_at=occurred,
            started_at=occurred,
        )
        result.append(r)

        ref = RunExecutionRef(
            run_id=rid,
            source_system="pipeline",
            external_run_id=source_run_id,
        )
        result.append(ref)

        pm = ProcessMetadata(
            run_id=rid,
            command=parsed_record.get("command"),
            cwd=cwd,
            timeout_seconds=parsed_record.get("timeout_seconds"),
        )
        result.append(pm)

        ev = DomainEventEnvelope(
            event_id=event_id(project_id, "ledger.jsonl", source_run_id + ":started"),
            event_scope="run",
            event_type="pipeline.run_started",
            task_id=tid,
            run_id=rid,
            source="pipeline",
            occurred_at=occurred,
            schema_version=parsed_record.get("schema_version", "2.8"),
            payload={"command": parsed_record.get("command"), "cwd": cwd},
            source_event_id=source_run_id,
            source_location=source_location,
        )
        result.append(ev)
        return result

    if event == "run_finished":
        source_run_id = parsed_record.get("run_id")
        if not source_run_id:
            return [_mapping_error("run_finished record missing run_id", parsed_record, source_location)]

        occurred_or_err = _require_timestamp(parsed_record, "finished_at", "run_finished", source_location)
        if _is_error(occurred_or_err):
            return [occurred_or_err]  # type: ignore[return-value]
        occurred = occurred_or_err  # type: str

        rid = run_id(project_id, source_run_id)

        classification = _classification_from_ledger(parsed_record)
        if classification == "ok":
            status: RunStatus = "completed"
        else:
            status = "failed"

        r = Run(
            id=rid,
            task_id=tid,
            run_type=str(parsed_record.get("run_type") or "main"),
            executor_id="hermes-local",
            agent_id=str(parsed_record.get("agent_id") or "unknown"),
            status=status,
            base_path=str(parsed_record.get("cwd") or ""),
            created_at=occurred,
            run_seq=None,
            outcome=classification,
            error_summary=(
                str(parsed_record["stderr_tail"])[:500]
                if parsed_record.get("stderr_tail") and classification not in ("ok", None)
                else None
            ),
            started_at=_iso_timestamp(parsed_record, "started_at"),
            ended_at=occurred,
        )
        result.append(r)

        ev = DomainEventEnvelope(
            event_id=event_id(project_id, "ledger.jsonl", source_run_id + ":finished"),
            event_scope="run",
            event_type="pipeline.run_finished",
            task_id=tid,
            run_id=rid,
            source="pipeline",
            occurred_at=occurred,
            schema_version=parsed_record.get("schema_version", "2.8"),
            payload={
                "exit_code": _exit_code_from_ledger(parsed_record),
                "classification": classification,
                "duration_seconds": parsed_record.get("duration_seconds"),
                "stdout_tail": str(parsed_record.get("stdout_tail") or "")[:500],
                "stderr_tail": str(parsed_record.get("stderr_tail") or "")[:500],
            },
            source_event_id=source_run_id,
            source_location=source_location,
        )
        result.append(ev)
        return result

    # Unknown event → unsupported (not an error, just not handled)
    return [UnsupportedRecord(
        reason=f"unknown ledger event type: {event}",
        source_location=source_location,
        raw_record_summary=str(parsed_record)[:200],
    )]


# ---------------------------------------------------------------------------
# 3.3  map_gate_record
# ---------------------------------------------------------------------------

def map_gate_record(
    project_id: str,
    parsed_record: Dict[str, Any],
    source_location: Optional[str] = None,
) -> List[ProjectionResult]:
    """Map a Pipeline gate record (review/*.json) to unified model entities.

    Produces:
      - ReviewDecision (requires gate_id and checked_at)
      - Evidence (when verification data is present)

    Does NOT produce:
      - DomainEventEnvelope — gate events come from events.jsonl (fallback), not gate records

    Rules (§5.2.3, §5.2.5):
      - Gate approved  → ReviewDecision(approve) — NOT Task accepted.
      - NO fake Run generated.
      - NO RunRelation generated.
      - ReviewDecision.run_id and Evidence.run_id are None when gate has no run_id.
      - When gate HAS run_id, it must be namespaced: pipeline:{project}:run:{source_run_id}.
      - Unknown decision → UnsupportedRecord, never silently mapped to 'reject'.
      - Missing gate_id → MappingError (cannot produce deterministic IDs).
      - Missing checked_at → MappingError (no datetime.now() fallback).
    """
    if not isinstance(parsed_record, dict):
        return [_mapping_error(
            f"map_gate_record requires a dict, got {type(parsed_record).__name__}",
            {},
            source_location,
        )]

    # --- Gate identity (required for deterministic ReviewDecision.id) ---
    gate_id = parsed_record.get("gate_id")
    if not gate_id or not str(gate_id).strip():
        return [_mapping_error(
            "gate record missing gate_id — cannot generate deterministic ReviewDecision.id",
            parsed_record,
            source_location,
        )]
    gate_id = str(gate_id).strip()

    # --- Decision ---
    pipeline_decision = str(parsed_record.get("decision") or parsed_record.get("gate_decision") or "").strip()
    if not pipeline_decision:
        return [UnsupportedRecord(
            reason="gate record has no decision field",
            source_location=source_location,
            raw_record_summary=str(parsed_record)[:200],
        )]

    unified_decision = _GATE_DECISION_MAP.get(pipeline_decision)
    if unified_decision is None:
        return [UnsupportedRecord(
            reason=f"unknown gate decision: {pipeline_decision!r}",
            source_location=source_location,
            raw_record_summary=str(parsed_record)[:200],
        )]

    # --- Timestamp ---
    occurred_or_err = _require_timestamp(parsed_record, "checked_at", "gate record", source_location)
    if _is_error(occurred_or_err):
        return [occurred_or_err]  # type: ignore[return-value]
    occurred = occurred_or_err  # type: str

    source_task_id = str(parsed_record.get("task_id") or "unknown")
    tid = task_id(project_id, source_task_id)

    # --- run_id: Optional, and MUST be namespaced when present ---
    raw_run_id = parsed_record.get("run_id")
    namespaced_run_id: Optional[str] = None
    if raw_run_id:
        namespaced_run_id = run_id(project_id, str(raw_run_id))

    result: List[ProjectionResult] = []

    # --- ReviewDecision ---
    review = ReviewDecision(
        id=event_id(project_id, "review.json", gate_id),
        task_id=tid,
        run_id=namespaced_run_id,  # None when gate has no run_id
        reviewer="codex",
        decision=unified_decision,
        summary=str(parsed_record.get("summary") or pipeline_decision),
        decided_at=occurred,
        failed_checks=(
            list(parsed_record["review"]["failed_checks"])
            if isinstance(parsed_record.get("review"), dict)
            and isinstance(parsed_record["review"].get("failed_checks"), list)
            else []
        ),
        revision_instructions=(
            list(parsed_record["review"]["revision_instructions"])
            if isinstance(parsed_record.get("review"), dict)
            and isinstance(parsed_record["review"].get("revision_instructions"), list)
            else []
        ),
    )
    result.append(review)

    # --- Evidence ---
    verify = parsed_record.get("verify")
    commands_run: List[str] = []
    if isinstance(verify, dict):
        if isinstance(verify.get("command"), str):
            commands_run = [str(verify["command"])]

    result.append(Evidence(
        task_id=tid,
        run_id=namespaced_run_id,  # None when gate has no run_id
        commands_run=commands_run,
        verification_output=(
            str(verify["summary"])[:2000]
            if isinstance(verify, dict) and verify.get("summary")
            else None
        ),
        risks=(
            list(parsed_record["known_risks"])
            if isinstance(parsed_record.get("known_risks"), list)
            else []
        ),
    ))

    return result


# ---------------------------------------------------------------------------
# 3.3a  Shared lifecycle event normalization  (§4.2.9)
# ---------------------------------------------------------------------------

# Known events.jsonl event types
_VALID_EVENTS_JSONL_KINDS = frozenset({
    "gate_checked",
    "revision_created",
    "revision_dispatched",
    "revision_dispatch_timeout",
    "revision_dispatch_skipped",
    "revision_policy_blocked",
    "revision_limit_reached",
})

# Events where revision_task_id should be used as the task_id
_REVISION_TASK_EVENTS = frozenset({"revision_dispatched", "revision_dispatch_timeout"})

# Phase 1 explicit whitelist of supported lifecycle_event phases.
# Ledger lifecycle_event with a phase NOT in this whitelist produces
# UnsupportedRecord — unknown phases must not silently extend the unified
# event vocabulary.  This list MUST be updated deliberately, never
# auto-extended, when new phases are added to the Pipeline.
_SUPPORTED_LIFECYCLE_PHASES = frozenset({
    "compiled",
    "gate_checked",
    "revision_created",
    "revision_dispatched",
    "revision_dispatch_timeout",
    "revision_dispatch_skipped",
    "revision_policy_blocked",
    "revision_limit_reached",
    "execution_handoff_started",
    "execution_handoff_finished",
    "execution_policy_applied",
    "opencode_result_evaluated",
})

# Unified lifecycle event_type mapping: phase/kind → event_type.
# All entries in _SUPPORTED_LIFECYCLE_PHASES and _VALID_EVENTS_JSONL_KINDS
# use the same normalization function so ledger lifecycle_event and
# events.jsonl fallback produce identical event_type when they describe the
# same logical event.
_LIFECYCLE_PHASE_TO_EVENT_TYPE: Dict[str, str] = {
    k: f"pipeline.{k}" for k in _SUPPORTED_LIFECYCLE_PHASES
}


def _normalize_lifecycle(
    project_id: str,
    parsed_record: Dict[str, Any],
    *,
    phase_or_kind: str,
    execution_run_id: Optional[str] = None,
) -> Tuple[str, Optional[str], str, str, Dict[str, Any]]:
    """Unified lifecycle event normalization used by BOTH ledger and events.jsonl.

    Returns (task_id, run_id, event_scope, event_type, payload).

    Identical input record produces identical output regardless of source.
    Does NOT set event_id — that is source-specific.

    CRITICAL: The CALLER is responsible for extracting the correct execution
    run ID based on source:
      - For ledger lifecycle_event: use related_run_id (the lifecycle's own
        run_id is its identity field, NOT an execution run).
      - For events.jsonl fallback: use the record's top-level run_id (which
        IS the execution run when present).

    When execution_run_id is None/empty, the unified run_id is None and
    the event scope is 'task' (never 'run').
    """
    # --- Effective task_id ---
    source_task_id = str(parsed_record.get("task_id") or "")
    revision_task_id = str(parsed_record.get("revision_task_id") or "").strip()
    if phase_or_kind in _REVISION_TASK_EVENTS and revision_task_id:
        effective_source_task_id = revision_task_id
    else:
        effective_source_task_id = source_task_id
    tid = task_id(project_id, effective_source_task_id)

    # --- run_id: uses execution_run_id from caller ---
    namespaced_run_id: Optional[str] = None
    if execution_run_id:
        namespaced_run_id = run_id(project_id, execution_run_id)

    # --- Event scope ---
    if phase_or_kind in _REVISION_TASK_EVENTS and namespaced_run_id:
        event_scope = "run"
    else:
        event_scope = "task"

    # --- Event type ---
    event_type = _LIFECYCLE_PHASE_TO_EVENT_TYPE.get(
        phase_or_kind, f"pipeline.{phase_or_kind}"
    )

    # --- Payload: preserve all available fields from original record ---
    payload: Dict[str, Any] = {"phase": phase_or_kind}
    for f in (
        "status", "message", "decision", "policy_action",
        "revision_task_id", "attempt",
        "classification", "exit_code", "duration_seconds",
        "reason", "max_revisions",
        "inbox_path", "outbox_path", "gate_record_path",
        "revision_inbox_path",
    ):
        v = parsed_record.get(f)
        if v is not None:
            payload[f] = v
    # Preserve related_run_id explicitly — it is the canonical execution run
    # link.  Also preserve lifecycle_run_id for traceability.
    related_run_id = str(parsed_record.get("related_run_id") or "").strip()
    top_level_run_id = str(parsed_record.get("run_id") or "").strip()
    if related_run_id:
        payload["related_run_id"] = related_run_id
    if top_level_run_id and top_level_run_id != related_run_id:
        payload["lifecycle_run_id"] = top_level_run_id
    if top_level_run_id and not related_run_id and execution_run_id != top_level_run_id:
        # events.jsonl case: run_id IS the execution run, preserve it
        if "run_id" not in payload:
            payload["run_id"] = top_level_run_id

    return (tid, namespaced_run_id, event_scope, event_type, payload)


def ledger_lifecycle_key(parsed_record: Dict[str, Any]) -> Optional[str]:
    """Extract a deterministic lifecycle matching key from a ledger record.

    Returns None for non-lifecycle_event records (run_started, run_finished).
    Uses the same task_id routing as _normalize_lifecycle for consistent dedup.
    Key format: effective_task_id|phase|revision_task_id|execution_run_id|decision|attempt
    with missing fields as empty string.

    CRITICAL: uses related_run_id (the real execution run) for the run_id
    dimension so that ledger lifecycle_event and events.jsonl fallback produce
    matching keys when they describe the same logical event.  The lifecycle's
    own run_id (life_xxx) is NOT used for dedup.

    Used by the builder to deduplicate events.jsonl against ledger.
    """
    if parsed_record.get("event") != "lifecycle_event":
        return None
    task_id_val = str(parsed_record.get("task_id") or "")
    phase = str(parsed_record.get("phase") or "")
    revision_task_id = str(parsed_record.get("revision_task_id") or "")
    # Same routing as _normalize_lifecycle
    if phase in _REVISION_TASK_EVENTS and revision_task_id:
        effective_task_id = revision_task_id
    else:
        effective_task_id = task_id_val
    # Use ONLY related_run_id for dedup alignment with events.jsonl run_id.
    # The lifecycle's own run_id (e.g. life_xxx) is its identity, NOT an
    # execution run — falling back to it would cause false dedup mismatches
    # against events.jsonl where run_id is empty.
    execution_run_id = str(parsed_record.get("related_run_id") or "")
    decision = str(parsed_record.get("decision") or "")
    attempt = str(parsed_record.get("attempt") or "")
    return f"{effective_task_id}|{phase}|{revision_task_id}|{execution_run_id}|{decision}|{attempt}"


def _events_jsonl_lifecycle_key(parsed_record: Dict[str, Any]) -> str:
    """Build a lifecycle matching key for an events.jsonl record.

    Uses the same normalized task_id logic as _normalize_lifecycle so that
    ledger lifecycle_event and events.jsonl fallback produce matching keys
    when they describe the same logical event.
    """
    event_kind = str(parsed_record.get("event") or "")
    task_id_val = str(parsed_record.get("task_id") or "")
    revision_task_id = str(parsed_record.get("revision_task_id") or "")
    # For dedup, use the same task_id routing as _normalize_lifecycle
    if event_kind in _REVISION_TASK_EVENTS and revision_task_id:
        effective_task_id = revision_task_id
    else:
        effective_task_id = task_id_val
    run_id_val = str(parsed_record.get("run_id") or "")
    decision = str(parsed_record.get("decision") or "")
    attempt = str(parsed_record.get("attempt") or "")
    return f"{effective_task_id}|{event_kind}|{revision_task_id}|{run_id_val}|{decision}|{attempt}"


# ---------------------------------------------------------------------------
# 3.3b  map_events_jsonl_record
# ---------------------------------------------------------------------------

def map_events_jsonl_record(
    project_id: str,
    parsed_record: Dict[str, Any],
    source_location: Optional[str] = None,
) -> List[ProjectionResult]:
    """Map an events.jsonl record to DomainEventEnvelope (fallback only).

    Rules (§4.2.9):
      - Only 7 event kinds are supported; unknown → UnsupportedRecord.
      - Missing task_id or timestamp → MappingError.
      - revision_dispatched / revision_dispatch_timeout with revision_task_id:
        task_id uses revision_task_id; run scope when run_id present.
      - Other events: event_scope=task, run_id=None.
      - Does NOT create Run, RunRelation, Task, or TaskRelation.
    """
    if not isinstance(parsed_record, dict):
        return [_mapping_error(
            f"map_events_jsonl_record requires a dict, got {type(parsed_record).__name__}",
            {},
            source_location,
        )]

    # --- Event kind ---
    event_kind = str(parsed_record.get("event") or "").strip()
    if not event_kind:
        return [_mapping_error("events.jsonl record missing 'event' field", parsed_record, source_location)]

    if event_kind not in _VALID_EVENTS_JSONL_KINDS:
        return [UnsupportedRecord(
            reason=f"unknown events.jsonl event kind: {event_kind!r}",
            source_location=source_location,
            raw_record_summary=str(parsed_record)[:200],
        )]

    # --- Validate task_id (required) ---
    source_task_id = str(parsed_record.get("task_id") or "").strip()
    if not source_task_id:
        return [_mapping_error("events.jsonl record missing task_id", parsed_record, source_location)]

    # --- Timestamp ---
    occurred_or_err = _require_timestamp(parsed_record, "timestamp", "events.jsonl", source_location)
    if _is_error(occurred_or_err):
        return [occurred_or_err]  # type: ignore[return-value]
    occurred = occurred_or_err  # type: str

    # --- Unified normalization (same as ledger lifecycle_event) ---
    # For events.jsonl, the top-level run_id IS the execution run.
    ev_execution_run_id = str(parsed_record.get("run_id") or "").strip() or None
    norm_tid, norm_rid, norm_scope, norm_type, norm_payload = _normalize_lifecycle(
        project_id, parsed_record, phase_or_kind=event_kind,
        execution_run_id=ev_execution_run_id,
    )

    # --- Deterministic event_id from source_location ---
    # events.jsonl has no stable event_id; use source_location (with line
    # number) so different lines produce different IDs and missing
    # source_location is an error.
    if not source_location or not str(source_location).strip():
        return [_mapping_error(
            "events.jsonl record missing source_location — cannot generate deterministic event_id",
            parsed_record,
            source_location,
        )]
    eid = event_id(project_id, "events.jsonl", str(source_location))

    ev = DomainEventEnvelope(
        event_id=eid,
        event_scope=norm_scope,
        event_type=norm_type,
        task_id=norm_tid,
        run_id=norm_rid if norm_scope == "run" else None,
        source="pipeline",
        occurred_at=occurred,
        schema_version="2.8",
        payload=norm_payload,
        source_event_id=None,
        source_location=source_location,
    )
    return [ev]


# ---------------------------------------------------------------------------
# 3.4  map_outbox_record
# ---------------------------------------------------------------------------

def map_outbox_record(
    project_id: str,
    parsed_record: Dict[str, Any],
    source_location: Optional[str] = None,
) -> List[ProjectionResult]:
    """Map a Pipeline outbox.json to unified model entities.

    Produces ONLY:
      - Artifact (1+): one for the outbox itself, one per changed_file
      - Evidence: structured verification data when present
      - MappingError / UnsupportedRecord: on invalid input

    Produces NEVER:
      - DomainEventEnvelope  — outbox_mapped is projector behaviour, not a Pipeline fact
      - Run, RunRelation      — outbox has no reliable run_id

    Rules:
      - Artifact.task_id and Evidence.task_id are always populated; run_id is
        None when absent, namespaced when present.
      - Artifact.created_at is None when no timestamp is available — never
        fake current time, never empty string.
      - changed_files_source preserved in Artifact.metadata.
      - error_taxonomy is an outbox field, not a source event; NO per-item
        DomainEventEnvelope is fabricated.
      - Missing task_id → MappingError.  Type errors → MappingError.
    """
    if not isinstance(parsed_record, dict):
        return [_mapping_error(
            f"map_outbox_record requires a dict, got {type(parsed_record).__name__}",
            {},
            source_location,
        )]

    source_task_id = str(parsed_record.get("task_id") or "").strip()
    if not source_task_id:
        return [_mapping_error("outbox missing task_id", parsed_record, source_location)]

    tid = task_id(project_id, source_task_id)

    # --- run_id: Optional, namespaced when present ---
    raw_run_id = parsed_record.get("run_id")
    namespaced_run_id: Optional[str] = None
    if raw_run_id and str(raw_run_id).strip():
        namespaced_run_id = run_id(project_id, str(raw_run_id))

    # --- Timestamps: None when absent, never fake ---
    created_at: Optional[str] = (
        _iso_timestamp(parsed_record, "timestamp")
        or _iso_timestamp(parsed_record, "created_at")
        or None
    )

    # --- Metadata: raw outbox attributes preserved as-is ---
    cf_source = str(parsed_record.get("changed_files_source") or "")
    outbox_metadata: Dict[str, Any] = {}
    if cf_source:
        outbox_metadata["changed_files_source"] = cf_source
    outbox_status = parsed_record.get("status")
    if outbox_status:
        outbox_metadata["outbox_status"] = outbox_status
    needs_hr = parsed_record.get("needs_human_review")
    if needs_hr is not None:
        outbox_metadata["needs_human_review"] = needs_hr
    agent_id_val = parsed_record.get("agent_id")
    if agent_id_val:
        outbox_metadata["agent_id"] = str(agent_id_val)
    summary_val = parsed_record.get("summary")
    if summary_val:
        outbox_metadata["summary"] = str(summary_val)[:500]

    result: List[ProjectionResult] = []
    artifact_index = 0

    def _artifact_id(tag: str) -> str:
        nonlocal artifact_index
        artifact_index += 1
        return event_id(project_id, "outbox.json", f"{source_task_id}:artifact:{tag}:{artifact_index}")

    # --- Artifact: the outbox file itself ---
    result.append(Artifact(
        id=_artifact_id("outbox_file"),
        task_id=tid,
        run_id=namespaced_run_id,
        artifact_type="outbox",
        created_at=created_at,
        path=source_location,
        metadata=dict(outbox_metadata) if outbox_metadata else None,
    ))

    # --- Artifact: per changed_file ---
    changed_files = parsed_record.get("changed_files")
    if isinstance(changed_files, list):
        for cf in changed_files:
            cf_path = str(cf) if isinstance(cf, str) else None
            result.append(Artifact(
                id=_artifact_id("changed_file"),
                task_id=tid,
                run_id=namespaced_run_id,
                artifact_type="changed_file",
                created_at=created_at,
                path=cf_path,
                metadata=dict(outbox_metadata) if outbox_metadata else None,
            ))
    elif changed_files is not None and not isinstance(changed_files, list):
        result.append(_mapping_error(
            f"outbox.changed_files is not a list: {type(changed_files).__name__}",
            parsed_record,
            source_location,
        ))

    # --- Evidence ---
    evidence_block = parsed_record.get("evidence")
    commands_run: List[str] = []
    if isinstance(evidence_block, dict):
        vc = evidence_block.get("verification_commands")
        if isinstance(vc, list):
            commands_run = [str(c) for c in vc]
        elif isinstance(vc, str):
            commands_run = [vc]

    verification_output: Optional[str] = None
    verification_raw = parsed_record.get("verification")
    if isinstance(verification_raw, dict):
        vos = str(verification_raw.get("output_summary") or verification_raw.get("summary") or "")[:2000]
        verification_output = vos or None
    if isinstance(evidence_block, dict) and not verification_output:
        vos = str(evidence_block.get("verification_output_summary") or "")[:2000]
        verification_output = vos or None

    known_risks: List[str] = []
    risks_raw = parsed_record.get("known_risks")
    if isinstance(risks_raw, list):
        known_risks = [str(r)[:500] for r in risks_raw]
    errors_raw = parsed_record.get("errors")
    if isinstance(errors_raw, list) and errors_raw:
        for err in errors_raw:
            known_risks.append(f"agent_error: {str(err)[:200]}")

    evidence = Evidence(
        task_id=tid,
        run_id=namespaced_run_id,
        commands_run=commands_run,
        verification_output=verification_output,
        risks=known_risks,
    )
    result.append(evidence)

    return result


# ============================================================================
# Phase 2B — Delegation Journal Projection
# ============================================================================
# Implements §5-§8 of docs/architecture/delegate-task-projection-phase2.md
#
# Reads ~/.hermes/delegations/*.jsonl and maps into unified Task, Run,
# TaskRelation, RunRelation, and DomainEventEnvelope entities.
#
# Key invariants:
#   - Deterministic IDs from (subagent_session_id, delegate_call_id, task_index)
#   - started-only → status=running, outcome=null
#   - terminal-only → MappingError
#   - Byte-identical duplicates → dedup
#   - Conflicting duplicates → MappingError
#   - Bad JSONL lines → MappingError, continue reading
# ============================================================================

from enum import Enum as _Enum


class DelegateRunStatus(_Enum):
    """Terminal status values from journal run_finished records."""
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    ERROR = "error"
    INTERRUPTED = "interrupted"


# Phase 2 delegate-specific RunStatus values
_DELEGATE_RUNNING = "running"


# ---------------------------------------------------------------------------
# Delegation ID functions (§5.2)
# ---------------------------------------------------------------------------

def delegate_task_id(subagent_session_id: str, delegate_call_id: str, task_index: int) -> str:
    """Deterministic delegate Task ID.

    >>> delegate_task_id("s1", "toolu_abc", 0)
    'delegate:s1:task:toolu_abc:0'
    """
    if not subagent_session_id or not delegate_call_id:
        raise ValueError("subagent_session_id and delegate_call_id are required")
    if not isinstance(task_index, int) or task_index < 0:
        raise ValueError(f"task_index must be non-negative int, got {task_index}")
    return f"delegate:{subagent_session_id}:task:{delegate_call_id}:{task_index}"


def delegate_run_id(subagent_session_id: str, delegate_call_id: str, task_index: int) -> str:
    """Deterministic delegate Run ID.

    >>> delegate_run_id("s1", "toolu_abc", 0)
    'delegate:s1:run:toolu_abc:0'
    """
    if not subagent_session_id or not delegate_call_id:
        raise ValueError("subagent_session_id and delegate_call_id are required")
    if not isinstance(task_index, int) or task_index < 0:
        raise ValueError(f"task_index must be non-negative int, got {task_index}")
    return f"delegate:{subagent_session_id}:run:{delegate_call_id}:{task_index}"


def delegate_event_id(
    subagent_session_id: str, delegate_call_id: str, task_index: int, phase: str
) -> str:
    """Deterministic SHA-256 event ID for delegation events (§5.2)."""
    raw = f"delegate:{subagent_session_id}:{delegate_call_id}:{task_index}:{phase}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


# ---------------------------------------------------------------------------
# Delegation journal record types
# ---------------------------------------------------------------------------

@dataclass
class DelegationStartedRecord:
    """Parsed run_started journal record."""
    parent_session_id: str
    delegate_call_id: str
    task_index: int
    subagent_session_id: str
    parent_delegate_task_id: Optional[str]
    parent_delegate_run_id: Optional[str]
    root_task_id: Optional[str]
    depth: int
    role: str
    goal: str
    toolsets: Optional[List[str]]
    model: Optional[str]
    started_at: str


@dataclass
class DelegationTerminalRecord:
    """Parsed run_finished journal record."""
    parent_session_id: str
    delegate_call_id: str
    task_index: int
    subagent_session_id: str
    parent_delegate_task_id: Optional[str]
    parent_delegate_run_id: Optional[str]
    root_task_id: Optional[str]
    depth: int
    status: str
    summary: Optional[str]
    exit_reason: str
    api_calls: int
    duration_seconds: float
    tokens: Dict[str, int]
    cost_usd: float
    tool_trace: List[Dict[str, Any]]
    files_written: List[str]
    files_read: List[str]
    error: Optional[str]
    ended_at: str


@dataclass
class DelegationMappingError:
    """Represents a mapping failure for a journal record."""
    error: str
    source_location: str
    record_type: str  # "started" | "terminal" | "unknown"


# ---------------------------------------------------------------------------
# Journal pairing and projection (§8.3-§8.4)
# ---------------------------------------------------------------------------

def _pair_key(record: Dict[str, Any]) -> Tuple[str, str, int]:
    """Extract pairing key: (parent_session_id, delegate_call_id, task_index)."""
    return (
        str(record.get("parent_session_id", "")),
        str(record.get("delegate_call_id", "")),
        int(record.get("task_index", -1)),
    )


def _parse_started(record: Dict[str, Any], source: str) -> Any:
    """Parse a run_started journal record."""
    try:
        return DelegationStartedRecord(
            parent_session_id=str(record["parent_session_id"]),
            delegate_call_id=str(record["delegate_call_id"]),
            task_index=int(record["task_index"]),
            subagent_session_id=str(record["subagent_session_id"]),
            parent_delegate_task_id=record.get("parent_delegate_task_id"),
            parent_delegate_run_id=record.get("parent_delegate_run_id"),
            root_task_id=record.get("root_task_id"),
            depth=int(record.get("depth", 1)),
            role=str(record.get("role", "leaf")),
            goal=str(record.get("goal", "")),
            toolsets=record.get("toolsets"),
            model=record.get("model"),
            started_at=str(record.get("started_at", "")),
        )
    except (KeyError, ValueError, TypeError) as e:
        return DelegationMappingError(
            error=f"Failed to parse run_started: {e}",
            source_location=source,
            record_type="started",
        )


def _parse_terminal(record: Dict[str, Any], source: str) -> Any:
    """Parse a run_finished journal record."""
    try:
        return DelegationTerminalRecord(
            parent_session_id=str(record["parent_session_id"]),
            delegate_call_id=str(record["delegate_call_id"]),
            task_index=int(record["task_index"]),
            subagent_session_id=str(record["subagent_session_id"]),
            parent_delegate_task_id=record.get("parent_delegate_task_id"),
            parent_delegate_run_id=record.get("parent_delegate_run_id"),
            root_task_id=record.get("root_task_id"),
            depth=int(record.get("depth", 1)),
            status=str(record["status"]),
            summary=record.get("summary"),
            exit_reason=str(record.get("exit_reason", "")),
            api_calls=int(record.get("api_calls", 0)),
            duration_seconds=float(record.get("duration_seconds", 0.0)),
            tokens=record.get("tokens", {"input": 0, "output": 0}),
            cost_usd=float(record.get("cost_usd", 0.0)),
            tool_trace=record.get("tool_trace", []),
            files_written=record.get("files_written", []),
            files_read=record.get("files_read", []),
            error=record.get("error"),
            ended_at=str(record.get("ended_at", "")),
        )
    except (KeyError, ValueError, TypeError) as e:
        return DelegationMappingError(
            error=f"Failed to parse run_finished: {e}",
            source_location=source,
            record_type="terminal",
        )


def _map_delegate_status(terminal_status: str) -> Tuple[str, Optional[str]]:
    """Map journal terminal status → (RunStatus, outcome). §6.3"""
    mapping = {
        "completed": ("completed", "completed"),
        "failed": ("failed", "failed"),
        "timeout": ("failed", "timeout"),
        "error": ("failed", "error"),
        "interrupted": ("cancelled", "interrupted"),
    }
    return mapping.get(terminal_status, ("failed", "error"))


def map_delegation_journal(
    journal_path: str,
) -> Tuple[
    List[Task],
    List[Run],
    List[TaskRelation],
    List[RunRelation],
    List[Any],  # DomainEventEnvelope
    List[DelegationMappingError],
]:
    """Map a single delegation journal file into unified entities.

    Returns (tasks, runs, task_relations, run_relations, events, errors).
    Implements §8.3-§8.4 pairing and exception boundary rules.
    """
    tasks: List[Task] = []
    runs: List[Run] = []
    task_relations: List[TaskRelation] = []
    run_relations: List[RunRelation] = []
    events: List[Any] = []
    errors: List[DelegationMappingError] = []

    # 1. Read and parse all lines
    raw_lines: List[Tuple[int, Dict[str, _A]]] = []
    with open(journal_path, "r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError as e:
                errors.append(DelegationMappingError(
                    error=f"bad journal line: {e}",
                    source_location=f"{journal_path}:{line_no}",
                    record_type="unknown",
                ))
                continue
            raw_lines.append((line_no, record))

    # 2. Group by pairing key, deduplicate, detect conflicts
    buckets: Dict[Tuple[str, str, int], List[Tuple[int, Dict[str, _A]]]] = {}
    for line_no, record in raw_lines:
        key = _pair_key(record)
        buckets.setdefault(key, []).append((line_no, record))

    for key, entries in buckets.items():
        started_records: List[Tuple[int, Dict[str, _A]]] = []
        terminal_records: List[Tuple[int, Dict[str, _A]]] = []

        for line_no, record in entries:
            phase = record.get("phase", "")
            if phase == "run_started":
                started_records.append((line_no, record))
            elif phase == "run_finished":
                terminal_records.append((line_no, record))

        # Dedup: byte-identical duplicates
        def _dedup(recs: List[Tuple[int, Dict[str, _A]]]) -> List[Tuple[int, Dict[str, _A]]]:
            seen: List[str] = []
            result: List[Tuple[int, Dict[str, _A]]] = []
            for ln, rec in recs:
                serialized = json.dumps(rec, sort_keys=True, ensure_ascii=False)
                if serialized in seen:
                    continue
                seen.append(serialized)
                result.append((ln, rec))
            return result

        started_records = _dedup(started_records)
        terminal_records = _dedup(terminal_records)

        # Conflict detection
        if len(started_records) > 1:
            errors.append(DelegationMappingError(
                error=f"Conflicting duplicate run_started records for key {key}",
                source_location=f"{journal_path}:{started_records[1][0]}",
                record_type="started",
            ))
            continue
        if len(terminal_records) > 1:
            errors.append(DelegationMappingError(
                error=f"Conflicting duplicate run_finished records for key {key}",
                source_location=f"{journal_path}:{terminal_records[1][0]}",
                record_type="terminal",
            ))
            continue

        # Terminal-only → MappingError (§8.4)
        if not started_records and terminal_records:
            errors.append(DelegationMappingError(
                error="terminal-only record without matching started",
                source_location=f"{journal_path}:{terminal_records[0][0]}",
                record_type="terminal",
            ))
            continue

        if not started_records:
            continue  # should not happen, but be safe

        # Parse started
        started_line_no, started_raw = started_records[0]
        started = _parse_started(started_raw, f"{journal_path}:{started_line_no}")
        if isinstance(started, DelegationMappingError):
            errors.append(started)
            continue

        # Parse terminal (if present)
        terminal: Optional[DelegationTerminalRecord] = None
        if terminal_records:
            term_line_no, term_raw = terminal_records[0]
            parsed = _parse_terminal(term_raw, f"{journal_path}:{term_line_no}")
            if isinstance(parsed, DelegationMappingError):
                errors.append(parsed)
                continue
            terminal = parsed

        # Build Task
        tid = delegate_task_id(started.subagent_session_id, started.delegate_call_id, started.task_index)

        task_status: TaskStatus
        if terminal:
            run_status, _outcome = _map_delegate_status(terminal.status)
            if run_status == "completed":
                task_status = "done"
            elif run_status == "cancelled":
                task_status = "cancelled"
            elif run_status == "failed":
                task_status = "failed"
            else:
                task_status = "failed"
        else:
            task_status = "running"

        task = Task(
            id=tid,
            project_id="delegate",
            title=(started.goal or "")[:200],
            status=task_status,
            created_at=started.started_at or "",
            root_task_id=started.root_task_id or tid,
        )
        tasks.append(task)

        # Build TaskRelation (if parent_delegate_task_id is present)
        if started.parent_delegate_task_id:
            tr_id = f"tr_{tid}_delegation"
            task_relations.append(TaskRelation(
                id=tr_id,
                parent_task_id=started.parent_delegate_task_id,
                child_task_id=tid,
                relation_type="parent_child",
                created_at=started.started_at or "",
            ))

        # Build Run
        rid = delegate_run_id(started.subagent_session_id, started.delegate_call_id, started.task_index)

        if terminal:
            run_status, outcome = _map_delegate_status(terminal.status)
            run = Run(
                id=rid,
                task_id=tid,
                run_type="delegated",
                executor_id="hermes-local",
                agent_id=getattr(terminal, "model", None) or started.model or "unknown",
                status=run_status,
                base_path="",
                created_at=started.started_at or "",
                parent_run_id=started.parent_delegate_run_id,
                outcome=outcome,
                summary=(terminal.summary or "")[:500] if terminal.summary else None,
                error_summary=terminal.error,
                started_at=started.started_at or "",
                ended_at=terminal.ended_at or "",
            )
        else:
            # started-only → running (§4.3 / §8.4)
            run = Run(
                id=rid,
                task_id=tid,
                run_type="delegated",
                executor_id="hermes-local",
                agent_id=started.model or "unknown",
                status=_DELEGATE_RUNNING,
                base_path="",
                created_at=started.started_at or "",
                parent_run_id=started.parent_delegate_run_id,
                outcome=None,
                summary=None,
                error_summary=None,
                started_at=started.started_at or "",
                ended_at=None,
            )
        runs.append(run)

        # Build RunRelation (if parent_delegate_run_id is present)
        if started.parent_delegate_run_id:
            rr_id = f"dr_{rid}_{started.parent_delegate_run_id}"
            run_relations.append(RunRelation(
                id=rr_id,
                parent_run_id=started.parent_delegate_run_id,
                child_run_id=rid,
                relation_type="delegated",
                created_at=started.started_at or "",
            ))

        # Build DomainEventEnvelope for run_started
        events.append({
            "event_id": delegate_event_id(
                started.subagent_session_id, started.delegate_call_id,
                started.task_index, "started"
            ),
            "event_type": "delegate.run_started",
            "event_scope": "run",
            "source_event_id": rid,
            "timestamp": started.started_at or "",
            "payload": {
                "run_id": rid,
                "task_id": tid,
                "status": "running",
                "goal": started.goal or "",
            },
        })

        # Build DomainEventEnvelope for run_finished (if terminal)
        if terminal:
            run_status, outcome = _map_delegate_status(terminal.status)
            events.append({
                "event_id": delegate_event_id(
                    started.subagent_session_id, started.delegate_call_id,
                    started.task_index, "finished"
                ),
                "event_type": "delegate.run_finished",
                "event_scope": "run",
                "source_event_id": rid,
                "timestamp": terminal.ended_at or "",
                "payload": {
                    "run_id": rid,
                    "task_id": tid,
                    "status": terminal.status,
                    "outcome": outcome,
                    "duration_seconds": terminal.duration_seconds,
                    "api_calls": terminal.api_calls,
                },
            })

    return tasks, runs, task_relations, run_relations, events, errors


def collect_delegation_journals(
    delegations_dir: Optional[str] = None,
) -> List[str]:
    """Collect all delegation journal file paths.

    Scans ~/.hermes/delegations/*.jsonl (or custom directory).
    Returns sorted list of absolute paths.
    """
    if delegations_dir is None:
        hermes_home = os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes"))
        delegations_dir = str(Path(hermes_home) / "delegations")
    dpath = Path(delegations_dir)
    if not dpath.is_dir():
        return []
    return sorted(str(p) for p in dpath.glob("*.jsonl"))


def map_all_delegations(
    delegations_dir: Optional[str] = None,
) -> Tuple[
    List[Task],
    List[Run],
    List[TaskRelation],
    List[RunRelation],
    List[Any],  # events
    List[DelegationMappingError],
]:
    """Map all delegation journals in the delegations directory.

    Aggregate result from all *.jsonl files.
    """
    all_tasks: List[Task] = []
    all_runs: List[Run] = []
    all_task_relations: List[TaskRelation] = []
    all_run_relations: List[RunRelation] = []
    all_events: List[Any] = []
    all_errors: List[DelegationMappingError] = []

    for journal_path in collect_delegation_journals(delegations_dir):
        tasks, runs, trs, rrs, events, errors = map_delegation_journal(journal_path)
        all_tasks.extend(tasks)
        all_runs.extend(runs)
        all_task_relations.extend(trs)
        all_run_relations.extend(rrs)
        all_events.extend(events)
        all_errors.extend(errors)

    return all_tasks, all_runs, all_task_relations, all_run_relations, all_events, all_errors


# ============================================================================
# Phase 3B — Kanban SQLite Projection (§2-§3)
# ============================================================================
# Implements §2-§3 of docs/architecture/kanban-unified-task-run-phase3.md
#
# Reads Kanban SQLite tables (tasks, task_runs, task_events, task_links)
# via mode=ro URI connection and maps into unified Task, Run, TaskRelation,
# RunRelation, and DomainEventEnvelope entities.
#
# Key invariants:
#   - Deterministic IDs: kanban:{board}:task/{run}/{event}:{source_id}
#   - 17 whitelisted event kinds → DomainEventEnvelope
#   - 15 diagnostic event kinds → UnsupportedRecord
#   - Unknown status/outcome/kind → UnsupportedRecord
#   - task_links → TaskRelation (parent_child | swarm)
#   - Read-only SQLite: mode=ro, no DDL, no migration, no repair
# ============================================================================

# Kanban Task status → unified TaskStatus (§2.2)
_KANBAN_TASK_STATUS_MAP: Dict[str, TaskStatus] = {
    "triage": "draft",
    "todo": "draft",
    "scheduled": "queued",
    "ready": "queued",
    "running": "running",
    "blocked": "blocked",
    "review": "needs_review",
    "done": "done",
    "archived": "cancelled",
}

# Kanban Run outcome → (RunStatus, outcome) (§2.2)
_KANBAN_OUTCOME_MAP: Dict[str, Tuple[RunStatus, Optional[str]]] = {
    "completed": ("completed", "completed"),
    "blocked": ("failed", "blocked"),
    "crashed": ("failed", "crashed"),
    "timed_out": ("failed", "timeout"),
    "spawn_failed": ("failed", "error"),
    "gave_up": ("failed", "gave_up"),
    "reclaimed": ("cancelled", "reclaimed"),
}

# Phase 3 whitelisted event kinds → unified event_type (§2.3)
_KANBAN_EVENT_KIND_MAP: Dict[str, Tuple[str, str]] = {
    "created": ("kanban.task_created", "task"),
    "assigned": ("kanban.task_assigned", "task"),
    "claimed": ("kanban.run_claimed", "run"),
    "scheduled": ("kanban.task_scheduled", "task"),
    "promoted": ("kanban.task_promoted", "task"),
    "promoted_manual": ("kanban.task_promoted", "task"),
    "completed": ("kanban.run_completed", "run"),
    "blocked": ("kanban.run_blocked", "run"),
    "unblocked": ("kanban.run_unblocked", "run"),
    "gave_up": ("kanban.task_gave_up", "task"),
    "reclaimed": ("kanban.run_reclaimed", "run"),
    "timed_out": ("kanban.run_timed_out", "run"),
    "crashed": ("kanban.run_crashed", "run"),
    "archived": ("kanban.task_archived", "task"),
    "linked": ("kanban.task_linked", "task"),
    "unlinked": ("kanban.task_unlinked", "task"),
    "decomposed": ("kanban.task_decomposed", "task"),
}

# Diagnostic event kinds → UnsupportedRecord (§2.3)
_KANBAN_DIAGNOSTIC_KINDS = frozenset({
    "claim_rejected", "claim_extended", "spawned",
    "completion_blocked_hallucination", "suspected_hallucinated_references",
    "stale", "respawn_guarded", "edited", "specified", "commented",
    "attachment_removed", "heartbeat", "tip_scratch_workspace",
    "protocol_violation", "rate_limited", "reprioritized",
})


def kanban_task_id(board: str, task_pk: str) -> str:
    """Deterministic Kanban Task ID.

    >>> kanban_task_id("default", "t6")
    'kanban:default:task:t6'
    """
    if not board or not task_pk:
        raise ValueError("board and task_pk are required")
    return f"kanban:{board}:task:{task_pk}"


def kanban_run_id(board: str, run_pk: int) -> str:
    """Deterministic Kanban Run ID.

    >>> kanban_run_id("default", 42)
    'kanban:default:run:42'
    """
    if not board:
        raise ValueError("board is required")
    if not isinstance(run_pk, int) or run_pk < 1:
        raise ValueError(f"run_pk must be positive int, got {run_pk}")
    return f"kanban:{board}:run:{run_pk}"


def kanban_event_id(board: str, event_pk: int) -> str:
    """Deterministic SHA-256 event ID for Kanban events."""
    raw = f"kanban:{board}:event:{event_pk}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def kanban_relation_id(child_task_id: str, relation_type: str) -> str:
    """Deterministic TaskRelation ID."""
    return f"tr_{child_task_id}_{relation_type}"


def _kanban_classify_event_kind(kind: str) -> Optional[Tuple[str, str]]:
    """Return (event_type, event_scope) for whitelisted kind, or None."""
    return _KANBAN_EVENT_KIND_MAP.get(kind)


def _kanban_is_diagnostic_kind(kind: str) -> bool:
    """Check if kind is a known diagnostic/internal event."""
    return kind in _KANBAN_DIAGNOSTIC_KINDS


def _kanban_parse_payload(payload_text: Optional[str]) -> Optional[Dict[str, Any]]:
    """Parse JSON payload from task_events, returning None on failure."""
    if not payload_text:
        return None
    try:
        return json.loads(payload_text)
    except json.JSONDecodeError:
        return None


def _kanban_parse_metadata(metadata_text: Optional[str]) -> Optional[Dict[str, Any]]:
    """Parse JSON metadata from task_runs, returning None on failure."""
    if not metadata_text:
        return None
    try:
        return json.loads(metadata_text)
    except json.JSONDecodeError:
        return None


def map_kanban_db(
    db_path: str,
    board: str,
) -> Tuple[
    List[Task], List[Run], List[TaskRelation], List[RunRelation],
    List[DomainEventEnvelope], List[ProjectionResult],
]:
    """Map a single Kanban SQLite database into unified entities.

    Opens the database in read-only mode (mode=ro). Returns
    (tasks, runs, task_relations, run_relations, events, errors)
    where errors may include MappingError or UnsupportedRecord.
    """
    tasks_out: List[Task] = []
    runs_out: List[Run] = []
    task_relations: List[TaskRelation] = []
    run_relations: List[RunRelation] = []
    events: List[DomainEventEnvelope] = []
    errors: List[ProjectionResult] = []

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error as e:
        errors.append(MappingError(
            error=f"Kanban DB open failed: {e}",
            source_location=db_path,
        ))
        return tasks_out, runs_out, task_relations, run_relations, events, errors

    try:
        # --- tasks ---
        task_rows = _kanban_fetch_all(conn, "SELECT * FROM tasks", db_path)
        task_by_id: Dict[str, Dict[str, Any]] = {}
        for row in task_rows:
            tid = row.get("id")
            if not tid:
                errors.append(MappingError(
                    error="task row missing id", source_location=db_path,
                ))
                continue
            task_by_id[tid] = row
            status_raw = row.get("status", "")
            unified_status = _KANBAN_TASK_STATUS_MAP.get(status_raw)
            if unified_status is None:
                errors.append(UnsupportedRecord(
                    reason=f"unknown kanban task status: {status_raw!r}",
                    source_location=db_path,
                    raw_record_summary=f"task {tid} status={status_raw}",
                ))
                continue
            created_at = _kanban_ts_to_iso(row.get("created_at"))
            task = Task(
                id=kanban_task_id(board, tid),
                project_id=f"kanban:{board}",
                title=(row.get("title") or "")[:200],
                body=row.get("body"),
                status=unified_status,
                created_at=created_at or "",
                updated_at=_kanban_ts_to_iso(row.get("completed_at")) or created_at or "",
                root_task_id=kanban_task_id(board, tid),
            )
            tasks_out.append(task)

        # --- task_runs ---
        run_rows = _kanban_fetch_all(conn, "SELECT * FROM task_runs", db_path)
        for row in run_rows:
            run_id_pk = row.get("id")
            task_id_text = row.get("task_id")
            if not run_id_pk or not task_id_text:
                errors.append(MappingError(
                    error="task_runs row missing id or task_id",
                    source_location=db_path,
                ))
                continue
            if task_id_text not in task_by_id:
                errors.append(MappingError(
                    error=f"task_runs {run_id_pk} references unknown task {task_id_text}",
                    source_location=db_path,
                ))
                continue
            outcome_raw = row.get("outcome")
            if outcome_raw is None:
                run_status: RunStatus = "running"
                outcome: Optional[str] = None
            else:
                mapped = _KANBAN_OUTCOME_MAP.get(outcome_raw)
                if mapped is None:
                    errors.append(UnsupportedRecord(
                        reason=f"unknown kanban run outcome: {outcome_raw!r}",
                        source_location=db_path,
                        raw_record_summary=f"run {run_id_pk} outcome={outcome_raw}",
                    ))
                    continue
                run_status, outcome = mapped
            metadata = _kanban_parse_metadata(row.get("metadata"))
            summary = row.get("summary")
            run = Run(
                id=kanban_run_id(board, run_id_pk),
                task_id=kanban_task_id(board, task_id_text),
                run_type="main",
                executor_id="hermes-local",
                agent_id=row.get("profile") or "unknown",
                status=run_status,
                base_path="",
                created_at=_kanban_ts_to_iso(row.get("started_at")) or "",
                parent_run_id=None,
                outcome=outcome,
                summary=(summary or "")[:500] if summary else None,
                error_summary=row.get("error"),
                started_at=_kanban_ts_to_iso(row.get("started_at")) or "",
                ended_at=_kanban_ts_to_iso(row.get("ended_at")) or "",
            )
            runs_out.append(run)

        # --- task_links ---
        link_rows = _kanban_fetch_all(conn, "SELECT * FROM task_links", db_path)
        for row in link_rows:
            parent_id = row.get("parent_id")
            child_id = row.get("child_id")
            if not parent_id or not child_id:
                continue
            if parent_id not in task_by_id or child_id not in task_by_id:
                errors.append(MappingError(
                    error=f"task_link ({parent_id}→{child_id}) references unknown task",
                    source_location=db_path,
                ))
                continue
            child_tid = kanban_task_id(board, child_id)
            parent_task = task_by_id.get(parent_id, {})
            rel_type: TaskRelationType = (
                "swarm" if parent_task.get("workflow_template_id") else "parent_child"
            )
            task_relations.append(TaskRelation(
                id=kanban_relation_id(child_tid, rel_type),
                parent_task_id=kanban_task_id(board, parent_id),
                child_task_id=child_tid,
                relation_type=rel_type,
                created_at=_kanban_ts_to_iso(parent_task.get("created_at")) or "",
            ))

        # --- task_events ---
        event_rows = _kanban_fetch_all(
            conn, "SELECT * FROM task_events ORDER BY id", db_path,
        )
        for row in event_rows:
            event_id_pk = row.get("id")
            task_id_text = row.get("task_id")
            kind = row.get("kind", "")
            if not event_id_pk or not task_id_text or not kind:
                errors.append(MappingError(
                    error="task_events row missing id, task_id, or kind",
                    source_location=db_path,
                ))
                continue

            # Classify kind
            event_info = _kanban_classify_event_kind(kind)
            if event_info is not None:
                event_type, event_scope = event_info
            elif _kanban_is_diagnostic_kind(kind):
                errors.append(UnsupportedRecord(
                    reason=f"kanban diagnostic event kind: {kind!r}",
                    source_location=db_path,
                    raw_record_summary=f"event {event_id_pk} kind={kind}",
                ))
                continue
            else:
                errors.append(UnsupportedRecord(
                    reason=f"unknown kanban event kind: {kind!r}",
                    source_location=db_path,
                    raw_record_summary=f"event {event_id_pk} kind={kind}",
                ))
                continue

            run_id_pk = row.get("run_id")
            namespaced_run_id: Optional[str] = None
            if run_id_pk is not None and isinstance(run_id_pk, int) and run_id_pk > 0:
                namespaced_run_id = kanban_run_id(board, run_id_pk)

            task_id_unified = kanban_task_id(board, task_id_text)
            payload_data = _kanban_parse_payload(row.get("payload"))
            ev = DomainEventEnvelope(
                event_id=kanban_event_id(board, event_id_pk),
                event_scope=event_scope,
                event_type=event_type,
                task_id=task_id_unified,
                run_id=namespaced_run_id if event_scope == "run" else None,
                source="kanban",
                occurred_at=_kanban_ts_to_iso(row.get("created_at")) or "",
                schema_version="kanban_v1",
                payload=payload_data or {},
                source_event_id=str(event_id_pk),
                source_location=f"{db_path}:task_events:{event_id_pk}",
            )
            events.append(ev)

    except sqlite3.Error as e:
        errors.append(MappingError(
            error=f"Kanban DB read error: {e}",
            source_location=db_path,
        ))
    finally:
        try:
            conn.close()
        except Exception:
            pass

    return tasks_out, runs_out, task_relations, run_relations, events, errors


def _kanban_fetch_all(
    conn: Any, query: str, db_path: str,
) -> List[Dict[str, Any]]:
    """Execute query and return rows as dicts. Handles missing tables gracefully."""
    try:
        cur = conn.execute(query)
        rows = cur.fetchall()
        if not rows:
            return []
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in rows]
    except sqlite3.OperationalError as e:
        err = str(e).lower()
        if "no such table" in err:
            return []
        raise


def _kanban_ts_to_iso(ts: Any) -> Optional[str]:
    """Convert Unix timestamp (int or float) to ISO-8601 string."""
    if ts is None:
        return None
    try:
        from datetime import datetime, timezone
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None
