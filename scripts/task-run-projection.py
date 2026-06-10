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
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union


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
