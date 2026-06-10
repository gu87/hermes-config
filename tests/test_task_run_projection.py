"""Tests for Phase 1A — data models, deterministic IDs, pure mapping functions.

Covers all requirements from docs/architecture/unified-task-run-contract.md §5.2.
"""

import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

_spec = importlib.util.spec_from_file_location(
    "task_run_projection", str(SCRIPTS / "task-run-projection.py")
)
proj = importlib.util.module_from_spec(_spec)
sys.modules["task_run_projection"] = proj
assert _spec.loader is not None
_spec.loader.exec_module(proj)


# ============================================================================
# 1.  Deterministic ID Functions
# ============================================================================

class TestTaskId:
    def test_format(self):
        assert proj.task_id("staam", "staam_t6") == "pipeline:staam:task:staam_t6"

    def test_idempotent(self):
        a = proj.task_id("research", "task_42")
        b = proj.task_id("research", "task_42")
        assert a == b

    def test_rejects_empty_project(self):
        with pytest.raises(ValueError):
            proj.task_id("", "task_x")

    def test_rejects_empty_source_task(self):
        with pytest.raises(ValueError):
            proj.task_id("p", "")


class TestRunId:
    def test_format(self):
        result = proj.run_id("staam", "run_t6_20260307_152200_123456")
        assert result == "pipeline:staam:run:run_t6_20260307_152200_123456"

    def test_idempotent(self):
        a = proj.run_id("staam", "run_abc")
        b = proj.run_id("staam", "run_abc")
        assert a == b

    def test_rejects_empty(self):
        with pytest.raises(ValueError):
            proj.run_id("", "run_x")
        with pytest.raises(ValueError):
            proj.run_id("p", "")


class TestEventId:
    def test_deterministic(self):
        a = proj.event_id("staam", "ledger.jsonl", "run_t6:started")
        b = proj.event_id("staam", "ledger.jsonl", "run_t6:started")
        assert a == b

    def test_different_inputs_produce_different_ids(self):
        a = proj.event_id("staam", "ledger.jsonl", "run_t6:started")
        b = proj.event_id("staam", "ledger.jsonl", "run_t6:finished")
        assert a != b

    def test_is_hex_32_chars(self):
        eid = proj.event_id("staam", "ledger.jsonl", "run_x:started")
        assert len(eid) == 32
        assert all(c in "0123456789abcdef" for c in eid)

    def test_uses_sha256(self):
        raw = "pipeline:staam:ledger.jsonl:run_x:started"
        expected = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
        assert proj.event_id("staam", "ledger.jsonl", "run_x:started") == expected

    def test_rejects_empty_identity(self):
        with pytest.raises(ValueError):
            proj.event_id("staam", "ledger.jsonl", "")


# ============================================================================
# 2.  Task Card Mapping
# ============================================================================

TASK_CARD_BASIC = {
    "task_card_id": "staam_t6",
    "goal": "Add API endpoint",
    "created_at": "2026-03-07T15:00:00Z",
}

TASK_CARD_WITH_INTENT = {
    "task_card_id": "staam_t8",
    "goal": "Refactor auth",
    "created_at": "2026-03-07T15:00:00Z",
    "compiled_intent": {
        "interpreted_intent": "Refactor the authentication module",
        "real_task": "Extract auth logic into separate service",
        "task_category": "refactor",
        "risk_level": "R2",
        "preferred_agent": "claude",
        "must_keep": ["existing tests pass"],
        "must_avoid": ["don't change API surface"],
        "success_criteria": ["all tests green", "auth still works"],
    },
    "execution_plan": {
        "mode": "single_agent",
        "primary_agent": "claude",
        "agents": ["claude"],
    },
    "output_contract": {
        "schema_version": "2.8",
        "required_fields": ["task_id", "summary", "changed_files"],
    },
    "allowed_files": ["src/auth/"],
}

TASK_CARD_NO_TS = {
    "task_card_id": "staam_t9",
    "goal": "Missing timestamp",
}


class TestMapTaskCard:
    def test_basic_task_card(self):
        results = proj.map_task_card("staam", dict(TASK_CARD_BASIC))
        tasks = [r for r in results if isinstance(r, proj.Task)]
        assert len(tasks) == 1
        t = tasks[0]
        assert t.id == "pipeline:staam:task:staam_t6"
        assert t.project_id == "staam"
        assert t.status == "draft"
        assert t.root_task_id == "pipeline:staam:task:staam_t6"

    def test_task_card_uses_task_id_fallback(self):
        record = {"task_id": "custom_task", "goal": "Fix bug", "created_at": "2026-03-07T15:00:00Z"}
        results = proj.map_task_card("staam", record)
        tasks = [r for r in results if isinstance(r, proj.Task)]
        assert tasks[0].id == "pipeline:staam:task:custom_task"

    def test_task_card_with_compiled_intent(self):
        results = proj.map_task_card("staam", dict(TASK_CARD_WITH_INTENT))
        specs = [r for r in results if isinstance(r, proj.TaskSpec)]
        assert len(specs) == 1
        s = specs[0]
        assert s.task_id == "pipeline:staam:task:staam_t8"
        assert s.real_task == "Extract auth logic into separate service"
        assert s.task_category == "refactor"
        assert s.risk_level == "R2"
        assert s.primary_agent == "claude"
        assert s.allowed_files == ["src/auth/"]
        assert s.must_keep == ["existing tests pass"]
        assert s.must_avoid == ["don't change API surface"]
        assert s.success_criteria == ["all tests green", "auth still works"]

    def test_task_card_missing_id(self):
        results = proj.map_task_card("staam", {"goal": "no id", "created_at": "2026-03-07T15:00:00Z"})
        errors = [r for r in results if isinstance(r, proj.MappingError)]
        assert len(errors) == 1
        assert "missing" in errors[0].error.lower()

    def test_task_card_non_dict_is_mapping_error(self):
        results = proj.map_task_card("staam", "not_a_dict")  # type: ignore[arg-type]
        errors = [r for r in results if isinstance(r, proj.MappingError)]
        assert len(errors) == 1

    def test_missing_created_at_returns_mapping_error(self):
        """No datetime.now() fallback — missing timestamp → MappingError."""
        results = proj.map_task_card("staam", dict(TASK_CARD_NO_TS))
        errors = [r for r in results if isinstance(r, proj.MappingError)]
        assert len(errors) == 1
        assert "created_at" in errors[0].error

    def test_same_input_always_same_output(self):
        """Determinism: running twice with same input produces identical results."""
        record = dict(TASK_CARD_BASIC)
        a = proj.map_task_card("staam", record)
        b = proj.map_task_card("staam", record)
        assert len(a) == len(b)
        for ra, rb in zip(a, b):
            assert type(ra) is type(rb)
            assert ra == rb


class TestRevisionTaskMapping:
    def test_revision_task_has_independent_task_id(self):
        record = {
            "task_card_id": "staam_t6_rev1",
            "goal": "Fix review issues",
            "created_at": "2026-03-07T15:00:00Z",
            "revision": {"of_task_id": "staam_t6", "attempt": 1, "max_revisions": 2},
        }
        results = proj.map_task_card("staam", record)
        tasks = [r for r in results if isinstance(r, proj.Task)]
        assert len(tasks) == 1
        t = tasks[0]
        assert t.id == "pipeline:staam:task:staam_t6_rev1"
        assert t.root_task_id == "pipeline:staam:task:staam_t6"

    def test_revision_task_generates_task_relation(self):
        record = {
            "task_card_id": "staam_t6_rev2",
            "created_at": "2026-03-07T15:00:00Z",
            "revision": {"of_task_id": "staam_t6_rev1", "attempt": 2},
        }
        results = proj.map_task_card("staam", record)
        rels = [r for r in results if isinstance(r, proj.TaskRelation)]
        assert len(rels) == 1
        rel = rels[0]
        assert rel.relation_type == "revision"
        assert rel.parent_task_id == "pipeline:staam:task:staam_t6_rev1"
        assert rel.child_task_id == "pipeline:staam:task:staam_t6_rev2"


# ============================================================================
# 3.  Ledger Mapping
# ============================================================================

LEDGER_RUN_STARTED = {
    "schema_version": "2.8",
    "event": "run_started",
    "run_id": "run_t6_20260307_152200_123456",
    "task_id": "staam_t6",
    "agent_id": "claude",
    "run_type": "main",
    "started_at": "2026-03-07T15:22:00.123456+00:00",
    "command": "hermes -z 'delegate_task(...)'",
    "cwd": "/home/user/projects/staam",
    "timeout_seconds": 600,
}

LEDGER_RUN_FINISHED = {
    "schema_version": "2.8",
    "event": "run_finished",
    "run_id": "run_t6_20260307_152200_123456",
    "task_id": "staam_t6",
    "agent_id": "claude",
    "run_type": "main",
    "started_at": "2026-03-07T15:22:00.123456+00:00",
    "finished_at": "2026-03-07T15:23:45.000000+00:00",
    "exit_code": 0,
    "classification": "ok",
    "duration_seconds": 104.877,
    "stdout_tail": "outbox written successfully",
    "stderr_tail": "",
}

# Real-structure lifecycle fixtures: run_id = lifecycle event ID (same as
# event_id); related_run_id = the real execution run ID when one exists.
# These match the actual output of scripts/run-ledger.py append_lifecycle_event().

LEDGER_LIFECYCLE = {
    "schema_version": "2.8",
    "event": "lifecycle_event",
    "event_id": "life_staam_t6_20260307",
    "run_id": "life_staam_t6_20260307",  # lifecycle's own ID, NOT an execution run
    "task_id": "staam_t6",
    "phase": "compiled",
    "status": "completed",
    "started_at": "2026-03-07T15:00:00Z",
}

LEDGER_LIFECYCLE_NO_EVENT_ID = {
    "schema_version": "2.8",
    "event": "lifecycle_event",
    "run_id": "life_staam_t6_20260307",
    "task_id": "staam_t6",
    "phase": "compiled",
    "status": "completed",
    "started_at": "2026-03-07T15:00:00Z",
}

# Real-structure lifecycle events with related_run_id for dedup testing.
# These mirror the run_ledger.py output and the real events at
# ~/.claude/teams/staam/runs/ledger.jsonl:472-479.

LEDGER_GATE_CHECKED = {
    "event": "lifecycle_event",
    "event_id": "life_staam_t6_gate_001",
    "run_id": "life_staam_t6_gate_001",   # lifecycle's own ID
    "task_id": "staam_t6",
    "phase": "gate_checked",
    "decision": "revision_needed",
    "started_at": "2026-03-07T15:30:00Z",
}

EVENTS_JSONL_GATE_CHECKED = {
    "event": "gate_checked",
    "task_id": "staam_t6",
    "decision": "revision_needed",
    "timestamp": "2026-03-07T15:30:00Z",
}

LEDGER_REVISION_CREATED = {
    "event": "lifecycle_event",
    "event_id": "life_staam_t6_rev_created_001",
    "run_id": "life_staam_t6_rev_created_001",  # lifecycle's own ID
    "task_id": "staam_t6",
    "phase": "revision_created",
    "revision_task_id": "staam_t6_rev1",
    "attempt": 1,
    "started_at": "2026-03-07T15:31:00Z",
}

EVENTS_JSONL_REVISION_CREATED = {
    "event": "revision_created",
    "task_id": "staam_t6",
    "revision_task_id": "staam_t6_rev1",
    "attempt": 1,
    "timestamp": "2026-03-07T15:31:00Z",
}

# Updated to match real structure: run_id is lifecycle ID; related_run_id is
# the real execution run.
LEDGER_LIFECYCLE_REVISION = {
    "event": "lifecycle_event",
    "event_id": "life_staam_t6_revision_dispatched",
    "run_id": "life_staam_t6_revision_dispatched",     # lifecycle's own ID
    "related_run_id": "run_rev1_20260307",             # real execution run
    "task_id": "staam_t6",
    "revision_task_id": "staam_t6_rev1",
    "phase": "revision_dispatched",
    "decision": "approved",
    "attempt": 1,
    "status": "completed",
    "started_at": "2026-03-07T15:32:00Z",
}

EVENTS_JSONL_REVISION = {
    "event": "revision_dispatched",
    "task_id": "staam_t6",
    "revision_task_id": "staam_t6_rev1",
    "run_id": "run_rev1_20260307",   # in events.jsonl, run_id IS the execution run
    "decision": "approved",
    "attempt": 1,
    "timestamp": "2026-03-07T15:32:00Z",
}

# gate_checked for revision task (posted after revision is approved)
LEDGER_GATE_CHECKED_REV = {
    "event": "lifecycle_event",
    "event_id": "life_staam_t6_rev1_gate_002",
    "run_id": "life_staam_t6_rev1_gate_002",  # lifecycle's own ID
    "task_id": "staam_t6_rev1",
    "phase": "gate_checked",
    "decision": "approved",
    "started_at": "2026-03-07T16:30:00Z",
}

EVENTS_JSONL_GATE_CHECKED_REV = {
    "event": "gate_checked",
    "task_id": "staam_t6_rev1",
    "decision": "approved",
    "timestamp": "2026-03-07T16:30:00Z",
}


class TestMapLedgerRecord:
    def test_run_started_creates_run(self):
        results = proj.map_ledger_record("staam", dict(LEDGER_RUN_STARTED))
        runs = [r for r in results if isinstance(r, proj.Run)]
        assert len(runs) == 1
        r = runs[0]
        assert r.id == "pipeline:staam:run:run_t6_20260307_152200_123456"
        assert r.task_id == "pipeline:staam:task:staam_t6"
        assert r.status == "running"
        assert r.run_seq is None
        assert r.agent_id == "claude"
        assert r.run_type == "main"

    def test_run_started_creates_run_execution_ref(self):
        results = proj.map_ledger_record("staam", dict(LEDGER_RUN_STARTED))
        refs = [r for r in results if isinstance(r, proj.RunExecutionRef)]
        assert len(refs) == 1
        assert refs[0].source_system == "pipeline"
        assert refs[0].external_run_id == "run_t6_20260307_152200_123456"

    def test_run_started_creates_process_metadata(self):
        results = proj.map_ledger_record("staam", dict(LEDGER_RUN_STARTED))
        pms = [r for r in results if isinstance(r, proj.ProcessMetadata)]
        assert len(pms) == 1
        assert pms[0].command == "hermes -z 'delegate_task(...)'"

    def test_run_started_creates_domain_event(self):
        results = proj.map_ledger_record("staam", dict(LEDGER_RUN_STARTED))
        events = [r for r in results if isinstance(r, proj.DomainEventEnvelope)]
        assert len(events) == 1
        ev = events[0]
        assert ev.event_scope == "run"
        assert ev.event_type == "pipeline.run_started"

    def test_same_run_id_across_started_and_finished(self):
        results_start = proj.map_ledger_record("staam", dict(LEDGER_RUN_STARTED))
        results_end = proj.map_ledger_record("staam", dict(LEDGER_RUN_FINISHED))
        run_start = [r for r in results_start if isinstance(r, proj.Run)][0]
        run_end = [r for r in results_end if isinstance(r, proj.Run)][0]
        assert run_start.id == run_end.id

    def test_run_finished_sets_completed_status(self):
        results = proj.map_ledger_record("staam", dict(LEDGER_RUN_FINISHED))
        runs = [r for r in results if isinstance(r, proj.Run)]
        assert runs[0].status == "completed"
        assert runs[0].outcome == "ok"

    def test_run_finished_timeout_sets_failed(self):
        record = dict(LEDGER_RUN_FINISHED, classification="timeout", exit_code=None)
        results = proj.map_ledger_record("staam", record)
        runs = [r for r in results if isinstance(r, proj.Run)]
        assert runs[0].status == "failed"
        assert runs[0].outcome == "timeout"

    def test_run_seq_is_always_none(self):
        results = proj.map_ledger_record("staam", dict(LEDGER_RUN_STARTED))
        runs = [r for r in results if isinstance(r, proj.Run)]
        assert runs[0].run_seq is None

    def test_lifecycle_event_no_run(self):
        results = proj.map_ledger_record("staam", dict(LEDGER_LIFECYCLE))
        runs = [r for r in results if isinstance(r, proj.Run)]
        assert len(runs) == 0
        events = [r for r in results if isinstance(r, proj.DomainEventEnvelope)]
        assert len(events) == 1
        assert events[0].event_scope == "task"

    def test_unknown_event_returns_unsupported(self):
        results = proj.map_ledger_record("staam", {"event": "something_weird", "task_id": "x"})
        unsupported = [r for r in results if isinstance(r, proj.UnsupportedRecord)]
        assert len(unsupported) == 1

    def test_non_dict_is_error(self):
        results = proj.map_ledger_record("staam", "not_dict")  # type: ignore[arg-type]
        errors = [r for r in results if isinstance(r, proj.MappingError)]
        assert len(errors) == 1

    def test_missing_event_field_is_error(self):
        results = proj.map_ledger_record("staam", {"task_id": "x"})
        errors = [r for r in results if isinstance(r, proj.MappingError)]
        assert len(errors) == 1

    def test_run_started_missing_timestamp_is_error(self):
        """No datetime.now() fallback — missing started_at → MappingError."""
        record = dict(LEDGER_RUN_STARTED)
        del record["started_at"]
        results = proj.map_ledger_record("staam", record)
        errors = [r for r in results if isinstance(r, proj.MappingError)]
        assert len(errors) == 1
        assert "started_at" in errors[0].error

    def test_run_finished_missing_timestamp_is_error(self):
        """No datetime.now() fallback — missing finished_at → MappingError."""
        record = dict(LEDGER_RUN_FINISHED)
        del record["finished_at"]
        results = proj.map_ledger_record("staam", record)
        errors = [r for r in results if isinstance(r, proj.MappingError)]
        assert len(errors) == 1
        assert "finished_at" in errors[0].error

    def test_lifecycle_event_missing_event_id_returns_mapping_error(self):
        """lifecycle_event without stable event_id → MappingError (no guessing)."""
        results = proj.map_ledger_record("staam", dict(LEDGER_LIFECYCLE_NO_EVENT_ID))
        errors = [r for r in results if isinstance(r, proj.MappingError)]
        assert len(errors) == 1
        assert "event_id" in errors[0].error.lower()


# ============================================================================
# 4.  Gate Record Mapping
# ============================================================================

GATE_APPROVED = {
    "schema_version": "2.8",
    "gate_id": "staam_t6_gate_20260307_153000",
    "task_id": "staam_t6",
    "checked_at": "2026-03-07T15:30:00Z",
    "decision": "approved",
    "gate_decision": "approved",
    "status": "completed",
    "verify_result": "pass",
    "review_decision": "approved",
    "summary": "All checks passed",
    "ready_for_user": True,
    "verify": {"exit_code": 0, "summary": "Verification passed"},
    "review": {},
    "errors": [],
    "known_risks": [],
}

GATE_REVISION_NEEDED = {
    "schema_version": "2.8",
    "gate_id": "staam_t6_gate_20260307_153000",
    "task_id": "staam_t6",
    "checked_at": "2026-03-07T15:30:00Z",
    "decision": "revision_needed",
    "gate_decision": "revision_needed",
    "status": "failed",
    "verify_result": "pass",
    "review_decision": "revision_needed",
    "summary": "Needs revision: evidence missing",
    "ready_for_user": False,
    "verify": {"exit_code": 0, "summary": "pass"},
    "review": {
        "failed_checks": [
            {"check": "evidence_quality", "passed": False, "detail": "No test results"},
        ],
        "revision_instructions": ["Add verification commands and re-run tests"],
    },
    "errors": [],
    "known_risks": [],
}

GATE_NO_GATE_ID = {
    "schema_version": "2.8",
    "task_id": "staam_t6",
    "checked_at": "2026-03-07T15:30:00Z",
    "decision": "approved",
    "summary": "No gate_id",
}

GATE_NO_DECISION = {
    "schema_version": "2.8",
    "gate_id": "staam_t6_gate_20260307_153000",
    "task_id": "staam_t6",
    "checked_at": "2026-03-07T15:30:00Z",
    "summary": "No decision",
}

GATE_UNKNOWN_DECISION = {
    "schema_version": "2.8",
    "gate_id": "staam_t6_gate_20260307_153000",
    "task_id": "staam_t6",
    "checked_at": "2026-03-07T15:30:00Z",
    "decision": "something_weird",
    "summary": "Unknown decision",
}

GATE_NO_TS = {
    "schema_version": "2.8",
    "gate_id": "staam_t6_gate_20260307_153000",
    "task_id": "staam_t6",
    "decision": "approved",
    "summary": "No timestamp",
}

GATE_WITH_RUN_ID = {
    "schema_version": "2.8",
    "gate_id": "staam_t6_gate_20260307_153000",
    "task_id": "staam_t6",
    "checked_at": "2026-03-07T15:30:00Z",
    "decision": "approved",
    "gate_decision": "approved",
    "status": "completed",
    "verify_result": "pass",
    "review_decision": "approved",
    "summary": "Gate with run reference",
    "run_id": "run_t6_20260307_152200_123456",
    "verify": {"exit_code": 0, "summary": "passed"},
    "review": {},
    "errors": [],
    "known_risks": [],
}

GATE_SECOND_REVIEW = {
    "schema_version": "2.8",
    "gate_id": "staam_t6_gate_20260307_160000",
    "task_id": "staam_t6",
    "checked_at": "2026-03-07T16:00:00Z",
    "decision": "approved",
    "gate_decision": "approved",
    "summary": "Second review",
    "verify": {"exit_code": 0, "summary": "re-verified"},
    "review": {},
    "errors": [],
    "known_risks": [],
}


class TestMapGateRecord:
    def test_gate_approved_maps_to_review_decision_approve(self):
        results = proj.map_gate_record("staam", dict(GATE_APPROVED))
        reviews = [r for r in results if isinstance(r, proj.ReviewDecision)]
        assert len(reviews) == 1
        assert reviews[0].decision == "approve"

    def test_gate_revision_needed(self):
        results = proj.map_gate_record("staam", dict(GATE_REVISION_NEEDED))
        reviews = [r for r in results if isinstance(r, proj.ReviewDecision)]
        assert len(reviews) == 1
        rd = reviews[0]
        assert rd.decision == "needs_revision"
        assert len(rd.failed_checks) == 1
        assert rd.failed_checks[0]["check"] == "evidence_quality"
        assert len(rd.revision_instructions) == 1

    def test_gate_does_not_generate_run(self):
        results = proj.map_gate_record("staam", dict(GATE_APPROVED))
        runs = [r for r in results if isinstance(r, proj.Run)]
        assert len(runs) == 0

    def test_gate_does_not_generate_run_relation(self):
        results = proj.map_gate_record("staam", dict(GATE_APPROVED))
        rels = [r for r in results if isinstance(r, proj.RunRelation)]
        assert len(rels) == 0

    def test_gate_does_not_produce_domain_event(self):
        """gate records only produce ReviewDecision + Evidence, no DomainEventEnvelope."""
        results = proj.map_gate_record("staam", dict(GATE_APPROVED))
        events = [r for r in results if isinstance(r, proj.DomainEventEnvelope)]
        assert len(events) == 0

    def test_gate_rejected(self):
        record = dict(GATE_APPROVED, decision="rejected", gate_decision="rejected")
        results = proj.map_gate_record("staam", record)
        reviews = [r for r in results if isinstance(r, proj.ReviewDecision)]
        assert reviews[0].decision == "reject"

    def test_non_dict_is_error(self):
        results = proj.map_gate_record("staam", "bad")  # type: ignore[arg-type]
        errors = [r for r in results if isinstance(r, proj.MappingError)]
        assert len(errors) == 1

    # --- New Phase 1A constraint tests ---

    def test_gate_without_run_id_sets_run_id_to_none(self):
        """Gate with no run_id → ReviewDecision.run_id and Evidence.run_id are None."""
        results = proj.map_gate_record("staam", dict(GATE_APPROVED))
        reviews = [r for r in results if isinstance(r, proj.ReviewDecision)]
        assert reviews[0].run_id is None
        evidences = [r for r in results if isinstance(r, proj.Evidence)]
        assert len(evidences) >= 1
        assert evidences[0].run_id is None

    def test_gate_with_run_id_uses_namespaced_run_id(self):
        """Gate with raw run_id → namespaced pipeline:{project}:run:{source_run_id}."""
        results = proj.map_gate_record("staam", dict(GATE_WITH_RUN_ID))
        reviews = [r for r in results if isinstance(r, proj.ReviewDecision)]
        assert reviews[0].run_id == "pipeline:staam:run:run_t6_20260307_152200_123456"
        evidences = [r for r in results if isinstance(r, proj.Evidence)]
        assert evidences[0].run_id == "pipeline:staam:run:run_t6_20260307_152200_123456"

    def test_unknown_gate_decision_not_mapped_to_reject(self):
        """Unknown gate decision → UnsupportedRecord, never silently 'reject'."""
        results = proj.map_gate_record("staam", dict(GATE_UNKNOWN_DECISION))
        unsupported = [r for r in results if isinstance(r, proj.UnsupportedRecord)]
        assert len(unsupported) == 1
        assert "something_weird" in unsupported[0].reason
        # No ReviewDecision produced
        reviews = [r for r in results if isinstance(r, proj.ReviewDecision)]
        assert len(reviews) == 0

    def test_gate_missing_decision_returns_unsupported(self):
        results = proj.map_gate_record("staam", dict(GATE_NO_DECISION))
        unsupported = [r for r in results if isinstance(r, proj.UnsupportedRecord)]
        assert len(unsupported) == 1

    def test_gate_missing_gate_id_returns_mapping_error(self):
        """No gate_id → cannot produce deterministic ReviewDecision.id."""
        results = proj.map_gate_record("staam", dict(GATE_NO_GATE_ID))
        errors = [r for r in results if isinstance(r, proj.MappingError)]
        assert len(errors) == 1
        assert "gate_id" in errors[0].error.lower()

    def test_gate_missing_checked_at_returns_mapping_error(self):
        """No checked_at → MappingError (no datetime.now() fallback)."""
        results = proj.map_gate_record("staam", dict(GATE_NO_TS))
        errors = [r for r in results if isinstance(r, proj.MappingError)]
        assert len(errors) == 1
        assert "checked_at" in errors[0].error

    def test_two_gate_reviews_produce_different_review_decision_ids(self):
        """Same Task, two different gate_ids → different ReviewDecision.id."""
        r1 = proj.map_gate_record("staam", dict(GATE_APPROVED))
        r2 = proj.map_gate_record("staam", dict(GATE_SECOND_REVIEW))
        rd1 = [r for r in r1 if isinstance(r, proj.ReviewDecision)][0]
        rd2 = [r for r in r2 if isinstance(r, proj.ReviewDecision)][0]
        assert rd1.id != rd2.id
        # Same underlying task, different review IDs — supports multiple reviews per Run/Task
        assert rd1.run_id is None  # gate without run_id → run_id is None

    def test_two_gate_records_produce_different_review_ids(self):
        """Same task, two different gate_ids → different ReviewDecision.id (not via events)."""
        r1 = proj.map_gate_record("staam", dict(GATE_APPROVED))
        r2 = proj.map_gate_record("staam", dict(GATE_SECOND_REVIEW))
        rd1 = [r for r in r1 if isinstance(r, proj.ReviewDecision)][0]
        rd2 = [r for r in r2 if isinstance(r, proj.ReviewDecision)][0]
        assert rd1.id != rd2.id

    def test_same_gate_record_produces_identical_output(self):
        """Determinism: same gate record → same output."""
        record = dict(GATE_APPROVED)
        a = proj.map_gate_record("staam", record)
        b = proj.map_gate_record("staam", record)
        assert len(a) == len(b)
        for ra, rb in zip(a, b):
            assert type(ra) is type(rb)
            assert ra == rb


# ============================================================================
# 5.  Prohibited Behaviours
# ============================================================================

class TestNoRunRelationRevisionDispatch:
    def test_map_ledger_revision_dispatch_no_run_relation(self):
        record = {
            "schema_version": "2.8",
            "event": "run_started",
            "run_id": "run_staam_t6_rev1_20260307",
            "task_id": "staam_t6_rev1",
            "agent_id": "claude",
            "run_type": "revision_dispatch",
            "started_at": "2026-03-07T15:30:00Z",
            "command": "hermes -z ...",
            "cwd": "/home/user/projects/staam",
        }
        results = proj.map_ledger_record("staam", record)
        rels = [r for r in results if isinstance(r, proj.RunRelation)]
        assert len(rels) == 0

    def test_map_gate_never_produces_run_relation(self):
        for decision in ["approved", "revision_needed", "rejected"]:
            record = dict(GATE_APPROVED, decision=decision, gate_decision=decision)
            results = proj.map_gate_record("staam", record)
            rels = [r for r in results if isinstance(r, proj.RunRelation)]
            assert len(rels) == 0, f"gate {decision} should not produce RunRelation"


class TestNoFakeRun:
    def test_lifecycle_event_no_run(self):
        results = proj.map_ledger_record("staam", dict(LEDGER_LIFECYCLE))
        runs = [r for r in results if isinstance(r, proj.Run)]
        assert len(runs) == 0

    def test_gate_no_run(self):
        results = proj.map_gate_record("staam", dict(GATE_APPROVED))
        runs = [r for r in results if isinstance(r, proj.Run)]
        assert len(runs) == 0


class TestRunSeqAlwaysNone:
    def test_run_started_run_seq_none(self):
        results = proj.map_ledger_record("staam", dict(LEDGER_RUN_STARTED))
        runs = [r for r in results if isinstance(r, proj.Run)]
        assert runs[0].run_seq is None

    def test_run_finished_run_seq_none(self):
        results = proj.map_ledger_record("staam", dict(LEDGER_RUN_FINISHED))
        runs = [r for r in results if isinstance(r, proj.Run)]
        assert runs[0].run_seq is None


class TestMappingFunctionsArePure:
    def test_no_file_io_in_task_card(self, monkeypatch):
        import builtins
        original_open = builtins.open
        calls = []
        def _tracking_open(*args, **kwargs):
            calls.append(args)
            return original_open(*args, **kwargs)
        monkeypatch.setattr(builtins, "open", _tracking_open)
        proj.map_task_card("staam", dict(TASK_CARD_BASIC))
        assert len(calls) == 0, f"map_task_card called open(): {calls}"

    def test_no_file_io_in_ledger(self, monkeypatch):
        import builtins
        original_open = builtins.open
        calls = []
        def _tracking_open(*args, **kwargs):
            calls.append(args)
            return original_open(*args, **kwargs)
        monkeypatch.setattr(builtins, "open", _tracking_open)
        proj.map_ledger_record("staam", dict(LEDGER_RUN_STARTED))
        assert len(calls) == 0

    def test_no_file_io_in_gate(self, monkeypatch):
        import builtins
        original_open = builtins.open
        calls = []
        def _tracking_open(*args, **kwargs):
            calls.append(args)
            return original_open(*args, **kwargs)
        monkeypatch.setattr(builtins, "open", _tracking_open)
        proj.map_gate_record("staam", dict(GATE_APPROVED))
        assert len(calls) == 0

    def test_no_env_writes_in_task_card(self):
        env_before = dict(os.environ)
        proj.map_task_card("staam", dict(TASK_CARD_BASIC))
        assert dict(os.environ) == env_before

    def test_no_env_writes_in_ledger(self):
        env_before = dict(os.environ)
        proj.map_ledger_record("staam", dict(LEDGER_RUN_STARTED))
        assert dict(os.environ) == env_before

    def test_no_env_writes_in_gate(self):
        env_before = dict(os.environ)
        proj.map_gate_record("staam", dict(GATE_APPROVED))
        assert dict(os.environ) == env_before


# ============================================================================
# 6.  Edge Cases & Explicit Error Signalling
# ============================================================================

class TestExplicitErrorSignalling:
    def test_missing_id_returns_mapping_error(self):
        results = proj.map_task_card("staam", {"goal": "no id", "created_at": "2026-03-07T15:00:00Z"})
        errors = [r for r in results if isinstance(r, proj.MappingError)]
        assert len(errors) == 1

    def test_non_dict_task_card_returns_mapping_error(self):
        results = proj.map_task_card("staam", ["list_not_dict"])  # type: ignore[arg-type]
        errors = [r for r in results if isinstance(r, proj.MappingError)]
        assert len(errors) == 1

    def test_non_dict_ledger_returns_mapping_error(self):
        results = proj.map_ledger_record("staam", 123)  # type: ignore[arg-type]
        errors = [r for r in results if isinstance(r, proj.MappingError)]
        assert len(errors) == 1

    def test_unknown_ledger_event_returns_unsupported_not_error(self):
        results = proj.map_ledger_record("staam", {"event": "unknown_event", "task_id": "x"})
        unsupported = [r for r in results if isinstance(r, proj.UnsupportedRecord)]
        errors = [r for r in results if isinstance(r, proj.MappingError)]
        assert len(unsupported) == 1
        assert len(errors) == 0

    def test_run_started_missing_run_id_returns_error(self):
        results = proj.map_ledger_record("staam", {"event": "run_started", "task_id": "staam_t6", "started_at": "2026-03-07T15:00:00Z"})
        errors = [r for r in results if isinstance(r, proj.MappingError)]
        assert len(errors) == 1


# ============================================================================
# 7.  Outbox Mapping (Phase 1B slice 2)
# ============================================================================

OUTBOX_FULL = {
    "schema_version": "2.8",
    "task_id": "staam_t6",
    "agent_id": "claude",
    "status": "success",
    "summary": "Added GET /users endpoint with tests",
    "changed_files": ["src/api/users.py", "tests/test_users.py"],
    "changed_files_source": "git_diff",
    "verification": {
        "commands_run": ["pytest tests/test_users.py -q"],
        "output_summary": "2 passed",
    },
    "evidence": {
        "changed_files": ["src/api/users.py", "tests/test_users.py"],
        "verification_commands": ["pytest tests/test_users.py -q"],
        "verification_output_summary": "2 passed",
        "known_risks": [],
    },
    "known_risks": [],
    "errors": [],
    "error_taxonomy": [],
    "needs_human_review": False,
    "notes": "",
    "timestamp": "2026-03-07T15:23:00Z",
}

OUTBOX_MINIMAL = {
    "task_id": "staam_t6",
    "status": "success",
    "summary": "done",
}


class TestMapOutboxRecord:
    def test_basic_outbox_produces_artifacts_and_evidence(self):
        results = proj.map_outbox_record("staam", dict(OUTBOX_FULL))
        arts = [r for r in results if isinstance(r, proj.Artifact)]
        evs = [r for r in results if isinstance(r, proj.Evidence)]
        events = [r for r in results if isinstance(r, proj.DomainEventEnvelope)]
        assert len(arts) >= 3  # outbox file + 2 changed_files
        assert len(evs) == 1
        assert len(events) == 0  # no DomainEventEnvelope from outbox

    def test_outbox_artifact_has_outbox_type(self):
        results = proj.map_outbox_record("staam", dict(OUTBOX_FULL))
        arts = [r for r in results if isinstance(r, proj.Artifact)]
        types = {a.artifact_type for a in arts}
        assert "outbox" in types
        assert "changed_file" in types

    def test_outbox_does_not_create_run(self):
        results = proj.map_outbox_record("staam", dict(OUTBOX_FULL))
        runs = [r for r in results if isinstance(r, proj.Run)]
        assert len(runs) == 0

    def test_outbox_does_not_create_run_relation(self):
        results = proj.map_outbox_record("staam", dict(OUTBOX_FULL))
        rels = [r for r in results if isinstance(r, proj.RunRelation)]
        assert len(rels) == 0

    def test_artifact_has_task_id(self):
        """Artifact must have task_id for attribution when run_id is None."""
        results = proj.map_outbox_record("staam", dict(OUTBOX_FULL))
        arts = [r for r in results if isinstance(r, proj.Artifact)]
        for a in arts:
            assert a.task_id == "pipeline:staam:task:staam_t6"

    def test_evidence_has_task_id(self):
        results = proj.map_outbox_record("staam", dict(OUTBOX_FULL))
        evs = [r for r in results if isinstance(r, proj.Evidence)]
        assert evs[0].task_id == "pipeline:staam:task:staam_t6"

    def test_run_id_is_none_when_absent(self):
        results = proj.map_outbox_record("staam", dict(OUTBOX_FULL))
        arts = [r for r in results if isinstance(r, proj.Artifact)]
        evs = [r for r in results if isinstance(r, proj.Evidence)]
        for a in arts:
            assert a.run_id is None
        for e in evs:
            assert e.run_id is None

    def test_run_id_is_namespaced_when_present(self):
        record = dict(OUTBOX_FULL, run_id="run_t6_20260307_152200")
        results = proj.map_outbox_record("staam", record)
        arts = [r for r in results if isinstance(r, proj.Artifact)]
        for a in arts:
            assert a.run_id == "pipeline:staam:run:run_t6_20260307_152200"

    def test_changed_files_projected_as_artifacts(self):
        results = proj.map_outbox_record("staam", dict(OUTBOX_FULL))
        cf_arts = [r for r in results if isinstance(r, proj.Artifact) and r.artifact_type == "changed_file"]
        assert len(cf_arts) == 2
        paths = {a.path for a in cf_arts}
        assert "src/api/users.py" in paths
        assert "tests/test_users.py" in paths

    def test_evidence_commands_run(self):
        results = proj.map_outbox_record("staam", dict(OUTBOX_FULL))
        evs = [r for r in results if isinstance(r, proj.Evidence)]
        assert len(evs[0].commands_run) >= 1

    def test_evidence_verification_output(self):
        results = proj.map_outbox_record("staam", dict(OUTBOX_FULL))
        evs = [r for r in results if isinstance(r, proj.Evidence)]
        assert evs[0].verification_output is not None

    def test_artifact_metadata_preserves_changed_files_source(self):
        """changed_files_source is preserved in Artifact.metadata, not in a fake event."""
        results = proj.map_outbox_record("staam", dict(OUTBOX_FULL))
        arts = [r for r in results if isinstance(r, proj.Artifact)]
        outbox_art = [a for a in arts if a.artifact_type == "outbox"][0]
        assert outbox_art.metadata is not None
        assert outbox_art.metadata["changed_files_source"] == "git_diff"

    def test_artifact_metadata_preserves_outbox_status(self):
        results = proj.map_outbox_record("staam", dict(OUTBOX_FULL))
        arts = [r for r in results if isinstance(r, proj.Artifact)]
        outbox_art = [a for a in arts if a.artifact_type == "outbox"][0]
        assert outbox_art.metadata["outbox_status"] == "success"

    def test_missing_timestamp_created_at_is_none(self):
        """No timestamp → created_at is None, never empty string or current time."""
        results = proj.map_outbox_record("staam", dict(OUTBOX_MINIMAL))
        arts = [r for r in results if isinstance(r, proj.Artifact)]
        for a in arts:
            assert a.created_at is None

    def test_minimal_outbox(self):
        results = proj.map_outbox_record("staam", dict(OUTBOX_MINIMAL))
        arts = [r for r in results if isinstance(r, proj.Artifact)]
        evs = [r for r in results if isinstance(r, proj.Evidence)]
        assert len(arts) >= 1  # at least outbox file itself
        assert len(evs) == 1
        # Zero DomainEventEnvelope
        events = [r for r in results if isinstance(r, proj.DomainEventEnvelope)]
        assert len(events) == 0

    def test_missing_task_id_returns_mapping_error(self):
        results = proj.map_outbox_record("staam", {"status": "success"})
        errors = [r for r in results if isinstance(r, proj.MappingError)]
        assert len(errors) == 1
        assert "task_id" in errors[0].error.lower()

    def test_non_dict_is_mapping_error(self):
        results = proj.map_outbox_record("staam", "not_dict")  # type: ignore[arg-type]
        errors = [r for r in results if isinstance(r, proj.MappingError)]
        assert len(errors) == 1

    def test_bad_changed_files_type_is_reported(self):
        record = {"task_id": "staam_t6", "changed_files": "not_a_list"}
        results = proj.map_outbox_record("staam", record)
        errors = [r for r in results if isinstance(r, proj.MappingError)]
        assert len(errors) >= 1

    def test_deterministic_ids(self):
        a = proj.map_outbox_record("staam", dict(OUTBOX_FULL))
        b = proj.map_outbox_record("staam", dict(OUTBOX_FULL))
        a_ids = [r.id for r in a if hasattr(r, "id")]
        b_ids = [r.id for r in b if hasattr(r, "id")]
        assert a_ids == b_ids

    def test_error_taxonomy_does_not_produce_events(self):
        """error_taxonomy is an outbox field, not a source event — zero DomainEventEnvelope."""
        record = {
            "task_id": "staam_t6",
            "status": "failed",
            "summary": "Failed",
            "error_taxonomy": [
                {"code": "timeout", "message": "Timed out", "recoverable": True},
            ],
        }
        results = proj.map_outbox_record("staam", record)
        events = [r for r in results if isinstance(r, proj.DomainEventEnvelope)]
        assert len(events) == 0

    def test_errors_in_risks(self):
        record = {
            "task_id": "staam_t6",
            "status": "success",
            "summary": "done",
            "errors": ["permission denied on /etc/hosts"],
        }
        results = proj.map_outbox_record("staam", record)
        evs = [r for r in results if isinstance(r, proj.Evidence)]
        assert any("agent_error" in r for r in evs[0].risks)

    def test_no_fake_timestamps(self):
        """When timestamp is absent, created_at is None, never current time."""
        import time
        results = proj.map_outbox_record("staam", dict(OUTBOX_MINIMAL))
        arts = [r for r in results if isinstance(r, proj.Artifact)]
        for a in arts:
            assert a.created_at is None, f"expected None, got {a.created_at!r}"


# ============================================================================
# 8.  Events.jsonl Mapping (Phase 1B events dedup slice)
# ============================================================================

EVENTS_GATE_CHECKED = {
    "event": "gate_checked",
    "task_id": "staam_t6",
    "decision": "approved",
    "timestamp": "2026-03-07T15:30:00Z",
}

EVENTS_REVISION_CREATED = {
    "event": "revision_created",
    "task_id": "staam_t6",
    "revision_task_id": "staam_t6_rev1",
    "attempt": 1,
    "timestamp": "2026-03-07T15:31:00Z",
}

EVENTS_REVISION_DISPATCHED = {
    "event": "revision_dispatched",
    "task_id": "staam_t6",
    "revision_task_id": "staam_t6_rev1",
    "run_id": "run_staam_t6_rev1_20260307",
    "exit_code": 0,
    "classification": "ok",
    "timestamp": "2026-03-07T15:32:00Z",
}

EVENTS_NO_TS = {
    "event": "gate_checked",
    "task_id": "staam_t6",
    "decision": "approved",
}

EVENTS_NO_TASK_ID = {
    "event": "gate_checked",
    "decision": "approved",
    "timestamp": "2026-03-07T15:30:00Z",
}

EVENTS_UNKNOWN_KIND = {
    "event": "something_weird",
    "task_id": "staam_t6",
    "timestamp": "2026-03-07T15:30:00Z",
}


def _ev(loc="events.jsonl:1"):
    """Shorthand source_location for events tests."""
    return loc


class TestMapEventsJsonlRecord:
    def test_gate_checked_produces_domain_event(self):
        results = proj.map_events_jsonl_record("staam", dict(EVENTS_GATE_CHECKED), _ev())
        events = [r for r in results if isinstance(r, proj.DomainEventEnvelope)]
        assert len(events) == 1
        ev = events[0]
        assert ev.event_type == "pipeline.gate_checked"
        assert ev.event_scope == "task"
        assert ev.task_id == "pipeline:staam:task:staam_t6"
        assert ev.run_id is None

    def test_gate_checked_payload_has_decision(self):
        results = proj.map_events_jsonl_record("staam", dict(EVENTS_GATE_CHECKED), _ev())
        events = [r for r in results if isinstance(r, proj.DomainEventEnvelope)]
        assert events[0].payload["decision"] == "approved"

    def test_revision_created(self):
        results = proj.map_events_jsonl_record("staam", dict(EVENTS_REVISION_CREATED), _ev())
        events = [r for r in results if isinstance(r, proj.DomainEventEnvelope)]
        assert len(events) == 1
        ev = events[0]
        assert ev.event_type == "pipeline.revision_created"
        assert ev.event_scope == "task"
        assert ev.payload["revision_task_id"] == "staam_t6_rev1"

    def test_revision_dispatched_uses_revision_task_id(self):
        results = proj.map_events_jsonl_record("staam", dict(EVENTS_REVISION_DISPATCHED), _ev())
        events = [r for r in results if isinstance(r, proj.DomainEventEnvelope)]
        assert events[0].task_id == "pipeline:staam:task:staam_t6_rev1"

    def test_revision_dispatched_with_run_id_is_run_scoped(self):
        results = proj.map_events_jsonl_record("staam", dict(EVENTS_REVISION_DISPATCHED), _ev())
        events = [r for r in results if isinstance(r, proj.DomainEventEnvelope)]
        assert events[0].event_scope == "run"
        assert events[0].run_id == "pipeline:staam:run:run_staam_t6_rev1_20260307"

    def test_events_does_not_create_run(self):
        results = proj.map_events_jsonl_record("staam", dict(EVENTS_REVISION_DISPATCHED), _ev())
        runs = [r for r in results if isinstance(r, proj.Run)]
        assert len(runs) == 0

    def test_events_does_not_create_task_relation(self):
        results = proj.map_events_jsonl_record("staam", dict(EVENTS_REVISION_CREATED), _ev())
        rels = [r for r in results if isinstance(r, proj.TaskRelation)]
        assert len(rels) == 0

    def test_unknown_kind_returns_unsupported(self):
        results = proj.map_events_jsonl_record("staam", dict(EVENTS_UNKNOWN_KIND), _ev())
        unsupported = [r for r in results if isinstance(r, proj.UnsupportedRecord)]
        assert len(unsupported) == 1

    def test_missing_timestamp_returns_mapping_error(self):
        results = proj.map_events_jsonl_record("staam", dict(EVENTS_NO_TS), _ev())
        errors = [r for r in results if isinstance(r, proj.MappingError)]
        assert len(errors) == 1

    def test_missing_task_id_returns_mapping_error(self):
        results = proj.map_events_jsonl_record("staam", dict(EVENTS_NO_TASK_ID), _ev())
        errors = [r for r in results if isinstance(r, proj.MappingError)]
        assert len(errors) == 1

    def test_missing_source_location_returns_mapping_error(self):
        """events.jsonl without source_location → MappingError (needed for event_id)."""
        results = proj.map_events_jsonl_record("staam", dict(EVENTS_GATE_CHECKED))  # no source_location
        errors = [r for r in results if isinstance(r, proj.MappingError)]
        assert len(errors) == 1

    def test_non_dict_is_mapping_error(self):
        results = proj.map_events_jsonl_record("staam", "not_dict", _ev())  # type: ignore[arg-type]
        errors = [r for r in results if isinstance(r, proj.MappingError)]
        assert len(errors) == 1

    def test_same_record_same_source_location_same_event_id(self):
        """Same input + same source_location → same event_id (deterministic)."""
        a = proj.map_events_jsonl_record("staam", dict(EVENTS_GATE_CHECKED), "events.jsonl:3")
        b = proj.map_events_jsonl_record("staam", dict(EVENTS_GATE_CHECKED), "events.jsonl:3")
        assert a[0].event_id == b[0].event_id  # type: ignore[union-attr]

    def test_different_source_locations_different_event_ids(self):
        """Same semantic event on different lines → different event_ids."""
        a = proj.map_events_jsonl_record("staam", dict(EVENTS_GATE_CHECKED), "events.jsonl:3")
        b = proj.map_events_jsonl_record("staam", dict(EVENTS_GATE_CHECKED), "events.jsonl:7")
        assert a[0].event_id != b[0].event_id  # type: ignore[union-attr]

    def test_all_seven_kinds_supported(self):
        for kind in sorted(proj._VALID_EVENTS_JSONL_KINDS):
            record = {"event": kind, "task_id": "staam_t6", "timestamp": "2026-01-01T00:00:00Z"}
            results = proj.map_events_jsonl_record("staam", record, f"events.jsonl:{hash(kind) % 100}")
            assert any(isinstance(r, proj.DomainEventEnvelope) for r in results), f"{kind} should produce event"

    def test_ledger_lifecycle_key_for_lifecycle_event(self):
        key = proj.ledger_lifecycle_key({
            "event": "lifecycle_event",
            "task_id": "staam_t6",
            "phase": "gate_checked",
            "decision": "approved",
        })
        assert key is not None
        assert "staam_t6" in key
        assert "gate_checked" in key

    def test_ledger_lifecycle_key_none_for_run_started(self):
        key = proj.ledger_lifecycle_key({"event": "run_started", "task_id": "x"})
        assert key is None

    def test_events_jsonl_lifecycle_key_format(self):
        key = proj._events_jsonl_lifecycle_key({
            "event": "gate_checked",
            "task_id": "staam_t6",
            "decision": "approved",
        })
        assert "staam_t6" in key
        assert "gate_checked" in key
        assert "approved" in key


# ============================================================================
# 9.  Cross-Source Consistency (ledger vs events.jsonl)
# ============================================================================
# Fixtures LEDGER_LIFECYCLE_REVISION and EVENTS_JSONL_REVISION are defined
# in the ledger fixture section above (real-structure format matching
# run_ledger.py append_lifecycle_event() output).


class TestCrossSourceConsistency:
    def test_ledger_and_events_same_revision_dispatched_semantics(self):
        """Same lifecycle record from ledger and events.jsonl → identical semantics
        except event_id, source_location, source_event_id."""
        ledger_results = proj.map_ledger_record("staam", dict(LEDGER_LIFECYCLE_REVISION))
        events_results = proj.map_events_jsonl_record("staam", dict(EVENTS_JSONL_REVISION),
                                                       "events.jsonl:5")

        lev = [r for r in ledger_results if isinstance(r, proj.DomainEventEnvelope)][0]
        eev = [r for r in events_results if isinstance(r, proj.DomainEventEnvelope)][0]

        # Identical semantics
        assert lev.task_id == eev.task_id
        assert lev.run_id == eev.run_id
        assert lev.event_scope == eev.event_scope
        assert lev.event_type == eev.event_type
        # Shared payload fields must match (ledger may have extra fields like status)
        for key in ("revision_task_id", "decision", "attempt", "run_id"):
            assert lev.payload.get(key) == eev.payload.get(key), f"payload[{key}] mismatch"

        # Different identity (source-specific)
        assert lev.event_id != eev.event_id
        assert lev.source_location != eev.source_location
        assert lev.source_event_id != eev.source_event_id

    def test_ledger_lifecycle_payload_preserves_fields(self):
        """Ledger lifecycle payload must preserve revision_task_id, decision,
        attempt, related_run_id — not just phase/status/message."""
        results = proj.map_ledger_record("staam", dict(LEDGER_LIFECYCLE_REVISION))
        events = [r for r in results if isinstance(r, proj.DomainEventEnvelope)]
        ev = events[0]
        assert ev.payload["revision_task_id"] == "staam_t6_rev1"
        assert ev.payload["decision"] == "approved"
        assert ev.payload["attempt"] == 1
        # related_run_id is the canonical execution run link
        assert ev.payload["related_run_id"] == "run_rev1_20260307"
        # lifecycle_run_id is preserved for traceability
        assert ev.payload["lifecycle_run_id"] == "life_staam_t6_revision_dispatched"
        assert ev.payload["status"] == "completed"

    def test_ledger_and_events_dedup_keys_match(self):
        """ledger lifecycle key and events.jsonl lifecycle key must match for same
        revision_dispatched event so dedup works correctly."""
        ledger_key = proj.ledger_lifecycle_key(dict(LEDGER_LIFECYCLE_REVISION))
        events_key = proj._events_jsonl_lifecycle_key(dict(EVENTS_JSONL_REVISION))
        assert ledger_key == events_key, f"keys must match: {ledger_key!r} vs {events_key!r}"


# ============================================================================
# 10.  Real-Structure Regression Tests (Phase 1D review fixes)
# ============================================================================

class TestRealStructureDedup:
    """Verify that ledger lifecycle_event + events.jsonl dedup works with
    real run_ledger.py output structure (run_id=lifecycle ID, related_run_id=execution run)."""

    def test_gate_checked_dedup(self):
        """ledger gate_checked + events.jsonl gate_checked → exactly 1 event."""
        ledger_results = proj.map_ledger_record("staam", dict(LEDGER_GATE_CHECKED))
        ledger_events = [r for r in ledger_results if isinstance(r, proj.DomainEventEnvelope)]
        assert len(ledger_events) == 1

        events_results = proj.map_events_jsonl_record("staam", dict(EVENTS_JSONL_GATE_CHECKED), "events.jsonl:1")
        events_events = [r for r in events_results if isinstance(r, proj.DomainEventEnvelope)]
        assert len(events_events) == 1

        # Keys must match for dedup to work
        lk = proj.ledger_lifecycle_key(dict(LEDGER_GATE_CHECKED))
        ek = proj._events_jsonl_lifecycle_key(dict(EVENTS_JSONL_GATE_CHECKED))
        assert lk == ek, f"gate_checked dedup keys must match: {lk!r} vs {ek!r}"

    def test_revision_created_dedup(self):
        """ledger revision_created + events.jsonl revision_created → exactly 1 event."""
        lk = proj.ledger_lifecycle_key(dict(LEDGER_REVISION_CREATED))
        ek = proj._events_jsonl_lifecycle_key(dict(EVENTS_JSONL_REVISION_CREATED))
        assert lk == ek, f"revision_created dedup keys must match: {lk!r} vs {ek!r}"

    def test_revision_dispatched_dedup(self):
        """ledger revision_dispatched + events.jsonl revision_dispatched → exactly 1 event."""
        lk = proj.ledger_lifecycle_key(dict(LEDGER_LIFECYCLE_REVISION))
        ek = proj._events_jsonl_lifecycle_key(dict(EVENTS_JSONL_REVISION))
        assert lk == ek, f"revision_dispatched dedup keys must match: {lk!r} vs {ek!r}"

    def test_gate_checked_rev_task_dedup(self):
        """ledger gate_checked for revision task + events.jsonl → exactly 1 event."""
        lk = proj.ledger_lifecycle_key(dict(LEDGER_GATE_CHECKED_REV))
        ek = proj._events_jsonl_lifecycle_key(dict(EVENTS_JSONL_GATE_CHECKED_REV))
        assert lk == ek, f"gate_checked rev dedup keys must match: {lk!r} vs {ek!r}"


class TestLifecycleRunIdIsolation:
    """Verify that the lifecycle's own run_id (life_xxx) is never treated as an
    execution Run ID."""

    def test_revision_dispatched_uses_related_run_id(self):
        """revision_dispatched from ledger → run_id is namespaced related_run_id,
        not the lifecycle's own run_id."""
        results = proj.map_ledger_record("staam", dict(LEDGER_LIFECYCLE_REVISION))
        events = [r for r in results if isinstance(r, proj.DomainEventEnvelope)]
        assert len(events) == 1
        ev = events[0]
        # The unified run_id should use related_run_id (the execution run),
        # NOT the lifecycle's own run_id (life_staam_t6_revision_dispatched)
        assert ev.run_id == "pipeline:staam:run:run_rev1_20260307", \
            f"expected execution run, got {ev.run_id}"
        assert ev.event_scope == "run"

    def test_lifecycle_without_related_run_id_has_null_run_id(self):
        """Ledger lifecycle_event without related_run_id → unified run_id is None.
        The lifecycle's own run_id (life_xxx) must NOT become the unified run_id."""
        results = proj.map_ledger_record("staam", dict(LEDGER_GATE_CHECKED))
        # LEDGER_GATE_CHECKED has run_id=life_xxx and no related_run_id
        events = [r for r in results if isinstance(r, proj.DomainEventEnvelope)]
        assert len(events) == 1
        ev = events[0]
        # run_id must be None — the lifecycle's own run_id is NOT an execution run
        assert ev.run_id is None, \
            f"lifecycle without related_run_id must have run_id=None, got {ev.run_id}"
        assert ev.event_scope == "task"

    def test_compiled_event_without_related_run_id_has_null_run_id(self):
        """compiled lifecycle event (no related_run_id) → run_id is None."""
        results = proj.map_ledger_record("staam", dict(LEDGER_LIFECYCLE))
        events = [r for r in results if isinstance(r, proj.DomainEventEnvelope)]
        assert len(events) == 1
        ev = events[0]
        # LEDGER_LIFECYCLE has run_id=life_xxx (lifecycle's own ID)
        # There is no related_run_id, so unified run_id must be None
        assert ev.run_id is None, \
            f"compiled event must have run_id=None, got {ev.run_id}"

    def test_lifecycle_run_id_preserved_in_payload(self):
        """The lifecycle's own run_id must be preserved in the payload as
        lifecycle_run_id for traceability."""
        results = proj.map_ledger_record("staam", dict(LEDGER_LIFECYCLE_REVISION))
        events = [r for r in results if isinstance(r, proj.DomainEventEnvelope)]
        ev = events[0]
        assert ev.payload.get("lifecycle_run_id") == "life_staam_t6_revision_dispatched"

    def test_related_run_id_in_payload(self):
        """related_run_id must be in payload."""
        results = proj.map_ledger_record("staam", dict(LEDGER_LIFECYCLE_REVISION))
        events = [r for r in results if isinstance(r, proj.DomainEventEnvelope)]
        ev = events[0]
        assert ev.payload.get("related_run_id") == "run_rev1_20260307"


class TestLifecyclePhaseWhitelist:
    """Verify that unknown lifecycle phases produce UnsupportedRecord."""

    def test_known_phase_compiled_passes(self):
        results = proj.map_ledger_record("staam", dict(LEDGER_LIFECYCLE))
        events = [r for r in results if isinstance(r, proj.DomainEventEnvelope)]
        assert len(events) == 1
        assert events[0].event_type == "pipeline.compiled"

    def test_unknown_lifecycle_phase_unsupported(self):
        """Unknown lifecycle phase → UnsupportedRecord, not silently mapped."""
        record = {
            "event": "lifecycle_event",
            "event_id": "life_test_001",
            "run_id": "life_test_001",
            "task_id": "staam_t6",
            "phase": "future_phase_not_yet_supported",
            "started_at": "2026-01-01T00:00:00Z",
        }
        results = proj.map_ledger_record("staam", record)
        unsupported = [r for r in results if isinstance(r, proj.UnsupportedRecord)]
        assert len(unsupported) == 1
        assert "future_phase_not_yet_supported" in unsupported[0].reason
        # No DomainEventEnvelope should be produced
        events = [r for r in results if isinstance(r, proj.DomainEventEnvelope)]
        assert len(events) == 0

    def test_empty_phase_is_mapping_error(self):
        """Empty phase → MappingError."""
        record = {
            "event": "lifecycle_event",
            "event_id": "life_test_001",
            "run_id": "life_test_001",
            "task_id": "staam_t6",
            "phase": "",
            "started_at": "2026-01-01T00:00:00Z",
        }
        results = proj.map_ledger_record("staam", record)
        errors = [r for r in results if isinstance(r, proj.MappingError)]
        assert len(errors) == 1


# ============================================================================
# 11.  Phase 2B — Delegation Journal Projection Tests
# ============================================================================

VALID_STARTED = {
    "schema_version": "delegate_v1", "phase": "run_started",
    "parent_session_id": "uuid-S0", "delegate_call_id": "toolu_abc",
    "task_index": 0, "subagent_session_id": "uuid-S1",
    "parent_delegate_task_id": None, "parent_delegate_run_id": None,
    "root_task_id": None, "depth": 1, "role": "leaf",
    "goal": "Add unit tests", "toolsets": ["read", "write"],
    "model": "claude-sonnet-4-6",
    "started_at": "2026-06-10T15:00:00.000000+00:00",
}

VALID_TERMINAL = {
    "schema_version": "delegate_v1", "phase": "run_finished",
    "parent_session_id": "uuid-S0", "delegate_call_id": "toolu_abc",
    "task_index": 0, "subagent_session_id": "uuid-S1",
    "parent_delegate_task_id": None, "parent_delegate_run_id": None,
    "root_task_id": None, "depth": 1,
    "status": "completed", "summary": "Done", "exit_reason": "completed",
    "api_calls": 5, "duration_seconds": 10.5,
    "tokens": {"input": 100, "output": 50}, "cost_usd": 0.01,
    "tool_trace": [], "files_written": [], "files_read": [],
    "error": None, "ended_at": "2026-06-10T15:00:10.000000+00:00",
}


class TestDelegateTaskId:
    def test_format(self):
        assert proj.delegate_task_id("s1", "toolu_abc", 0) == "delegate:s1:task:toolu_abc:0"

    def test_deterministic(self):
        a = proj.delegate_task_id("s1", "toolu_abc", 0)
        b = proj.delegate_task_id("s1", "toolu_abc", 0)
        assert a == b

    def test_different_inputs(self):
        a = proj.delegate_task_id("s1", "toolu_a", 0)
        b = proj.delegate_task_id("s1", "toolu_b", 0)
        assert a != b

    def test_rejects_empty_session(self):
        with pytest.raises(ValueError):
            proj.delegate_task_id("", "toolu_x", 0)

    def test_rejects_empty_call_id(self):
        with pytest.raises(ValueError):
            proj.delegate_task_id("s1", "", 0)

    def test_rejects_negative_index(self):
        with pytest.raises(ValueError):
            proj.delegate_task_id("s1", "toolu_x", -1)


class TestDelegateRunId:
    def test_format(self):
        assert proj.delegate_run_id("s1", "toolu_abc", 0) == "delegate:s1:run:toolu_abc:0"

    def test_deterministic(self):
        assert proj.delegate_run_id("s1", "toolu_a", 0) == proj.delegate_run_id("s1", "toolu_a", 0)


class TestDelegateEventId:
    def test_format(self):
        eid = proj.delegate_event_id("s1", "toolu_abc", 0, "started")
        assert len(eid) == 32

    def test_deterministic(self):
        a = proj.delegate_event_id("s1", "toolu_abc", 0, "started")
        b = proj.delegate_event_id("s1", "toolu_abc", 0, "started")
        assert a == b

    def test_different_phases(self):
        a = proj.delegate_event_id("s1", "toolu_abc", 0, "started")
        b = proj.delegate_event_id("s1", "toolu_abc", 0, "finished")
        assert a != b


class TestPairKey:
    def test_format(self):
        assert proj._pair_key(VALID_STARTED) == ("uuid-S0", "toolu_abc", 0)

    def test_missing_fields(self):
        assert proj._pair_key({}) == ("", "", -1)


class TestParseStarted:
    def test_valid(self):
        r = proj._parse_started(dict(VALID_STARTED), "test.jsonl:1")
        assert isinstance(r, proj.DelegationStartedRecord)
        assert r.goal == "Add unit tests"

    def test_missing_required(self):
        r = proj._parse_started({}, "test.jsonl:1")
        assert isinstance(r, proj.DelegationMappingError)


class TestParseTerminal:
    def test_valid(self):
        r = proj._parse_terminal(dict(VALID_TERMINAL), "test.jsonl:1")
        assert isinstance(r, proj.DelegationTerminalRecord)
        assert r.status == "completed"

    def test_missing_status(self):
        r = proj._parse_terminal({}, "test.jsonl:1")
        assert isinstance(r, proj.DelegationMappingError)


class TestMapDelegateStatus:
    def test_completed(self):
        assert proj._map_delegate_status("completed") == ("completed", "completed")

    def test_failed(self):
        assert proj._map_delegate_status("failed") == ("failed", "failed")

    def test_timeout(self):
        assert proj._map_delegate_status("timeout") == ("failed", "timeout")

    def test_error(self):
        assert proj._map_delegate_status("error") == ("failed", "error")

    def test_interrupted(self):
        assert proj._map_delegate_status("interrupted") == ("cancelled", "interrupted")


class TestMapDelegationJournal:
    """Full journal pairing and projection pipeline tests (§8)."""

    def test_normal_pair(self, tmp_path):
        jf = tmp_path / "t.jsonl"
        jf.write_text(json.dumps(VALID_STARTED) + "\n" + json.dumps(VALID_TERMINAL) + "\n")
        tasks, runs, trs, rrs, events, errors = proj.map_delegation_journal(str(jf))
        assert len(tasks) == 1
        assert tasks[0].id == "delegate:uuid-S1:task:toolu_abc:0"
        assert tasks[0].status == "done"
        assert len(runs) == 1
        assert runs[0].status == "completed"
        assert runs[0].outcome == "completed"
        assert len(events) == 2
        assert len(errors) == 0

    def test_started_only(self, tmp_path):
        jf = tmp_path / "t.jsonl"
        jf.write_text(json.dumps(VALID_STARTED) + "\n")
        tasks, runs, trs, rrs, events, errors = proj.map_delegation_journal(str(jf))
        assert len(tasks) == 1
        assert tasks[0].status == "running"
        assert runs[0].status == "running"
        assert runs[0].outcome is None
        assert len(events) == 1
        assert len(errors) == 0

    def test_terminal_only_is_error(self, tmp_path):
        jf = tmp_path / "t.jsonl"
        jf.write_text(json.dumps(VALID_TERMINAL) + "\n")
        tasks, runs, trs, rrs, events, errors = proj.map_delegation_journal(str(jf))
        assert len(tasks) == 0
        assert len(errors) == 1
        assert "terminal-only" in errors[0].error

    def test_byte_identical_dedup(self, tmp_path):
        jf = tmp_path / "t.jsonl"
        jf.write_text(
            json.dumps(VALID_STARTED) + "\n" + json.dumps(VALID_STARTED) + "\n"
            + json.dumps(VALID_TERMINAL) + "\n"
        )
        tasks, runs, trs, rrs, events, errors = proj.map_delegation_journal(str(jf))
        assert len(tasks) == 1
        assert len(errors) == 0

    def test_conflicting_started(self, tmp_path):
        jf = tmp_path / "t.jsonl"
        jf.write_text(
            json.dumps(VALID_STARTED) + "\n"
            + json.dumps(dict(VALID_STARTED, goal="Different")) + "\n"
        )
        tasks, runs, trs, rrs, events, errors = proj.map_delegation_journal(str(jf))
        assert len(errors) >= 1
        assert "Conflicting" in errors[0].error

    def test_bad_json_line(self, tmp_path):
        jf = tmp_path / "t.jsonl"
        jf.write_text("not json!!!\n" + json.dumps(VALID_STARTED) + "\n"
                       + json.dumps(VALID_TERMINAL) + "\n")
        tasks, runs, trs, rrs, events, errors = proj.map_delegation_journal(str(jf))
        assert len(tasks) == 1
        assert len(errors) >= 1

    def test_empty_file(self, tmp_path):
        jf = tmp_path / "t.jsonl"
        jf.write_text("")
        tasks, runs, trs, rrs, events, errors = proj.map_delegation_journal(str(jf))
        assert len(tasks) == 0
        assert len(errors) == 0

    def test_multiple_pairs(self, tmp_path):
        jf = tmp_path / "t.jsonl"
        s2 = dict(VALID_STARTED, delegate_call_id="tc2", subagent_session_id="s2")
        t2 = dict(VALID_TERMINAL, delegate_call_id="tc2", subagent_session_id="s2")
        jf.write_text(json.dumps(VALID_STARTED) + "\n" + json.dumps(VALID_TERMINAL) + "\n"
                       + json.dumps(s2) + "\n" + json.dumps(t2) + "\n")
        tasks, runs, trs, rrs, events, errors = proj.map_delegation_journal(str(jf))
        assert len(tasks) == 2
        assert len(runs) == 2
        assert len(errors) == 0

    def test_with_parent_relations(self, tmp_path):
        s = dict(VALID_STARTED, parent_delegate_task_id="delegate:S0:task:tc0:0",
                 parent_delegate_run_id="delegate:S0:run:tc0:0",
                 root_task_id="delegate:S0:task:tc0:0")
        t = dict(VALID_TERMINAL, parent_delegate_task_id="delegate:S0:task:tc0:0",
                 parent_delegate_run_id="delegate:S0:run:tc0:0",
                 root_task_id="delegate:S0:task:tc0:0")
        jf = tmp_path / "t.jsonl"
        jf.write_text(json.dumps(s) + "\n" + json.dumps(t) + "\n")
        tasks, runs, trs, rrs, events, errors = proj.map_delegation_journal(str(jf))
        assert len(trs) == 1
        assert trs[0].parent_task_id == "delegate:S0:task:tc0:0"
        assert len(rrs) == 1
        assert rrs[0].parent_run_id == "delegate:S0:run:tc0:0"
        assert rrs[0].relation_type == "delegated"

    def test_without_parent_relations(self, tmp_path):
        jf = tmp_path / "t.jsonl"
        jf.write_text(json.dumps(VALID_STARTED) + "\n" + json.dumps(VALID_TERMINAL) + "\n")
        tasks, runs, trs, rrs, events, errors = proj.map_delegation_journal(str(jf))
        assert len(trs) == 0
        assert len(rrs) == 0

    def test_timeout_status(self, tmp_path):
        jf = tmp_path / "t.jsonl"
        t = dict(VALID_TERMINAL, status="timeout")
        jf.write_text(json.dumps(VALID_STARTED) + "\n" + json.dumps(t) + "\n")
        tasks, runs, trs, rrs, events, errors = proj.map_delegation_journal(str(jf))
        assert runs[0].status == "failed"
        assert runs[0].outcome == "timeout"

    def test_interrupted_status(self, tmp_path):
        jf = tmp_path / "t.jsonl"
        t = dict(VALID_TERMINAL, status="interrupted")
        jf.write_text(json.dumps(VALID_STARTED) + "\n" + json.dumps(t) + "\n")
        tasks, runs, trs, rrs, events, errors = proj.map_delegation_journal(str(jf))
        assert runs[0].status == "cancelled"


class TestMapAllDelegations:
    def test_empty_dir(self, tmp_path):
        tasks, runs, trs, rrs, events, errors = proj.map_all_delegations(str(tmp_path))
        assert len(tasks) == 0
        assert len(errors) == 0

    def test_multiple_files(self, tmp_path):
        (tmp_path / "j1.jsonl").write_text(
            json.dumps(dict(VALID_STARTED, delegate_call_id="tc1", subagent_session_id="s1")) + "\n"
            + json.dumps(dict(VALID_TERMINAL, delegate_call_id="tc1", subagent_session_id="s1")) + "\n"
        )
        (tmp_path / "j2.jsonl").write_text(
            json.dumps(dict(VALID_STARTED, delegate_call_id="tc2", subagent_session_id="s2")) + "\n"
            + json.dumps(dict(VALID_TERMINAL, delegate_call_id="tc2", subagent_session_id="s2")) + "\n"
        )
        tasks, runs, trs, rrs, events, errors = proj.map_all_delegations(str(tmp_path))
        assert len(tasks) == 2
        assert len(errors) == 0

    def test_collect_empty_dir(self):
        assert proj.collect_delegation_journals("/nonexistent") == []


# ============================================================================
# 12.  Phase 3B — Kanban SQLite Projection Tests
# ============================================================================

import sqlite3


def _kanban_test_db(tmp_path, board="default", extra_sql=""):
    """Create an in-memory Kanban SQLite database with test data."""
    db_path = str(tmp_path / f"{board}.db")
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY, title TEXT NOT NULL, body TEXT,
            assignee TEXT, status TEXT NOT NULL, priority INTEGER DEFAULT 0,
            created_by TEXT, created_at INTEGER NOT NULL, started_at INTEGER,
            completed_at INTEGER, workspace_kind TEXT DEFAULT 'scratch',
            workspace_path TEXT, branch_name TEXT, claim_lock TEXT,
            session_id TEXT, workflow_template_id TEXT, current_step_key TEXT
        );
        CREATE TABLE IF NOT EXISTS task_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL,
            profile TEXT, status TEXT NOT NULL, started_at INTEGER NOT NULL,
            ended_at INTEGER, outcome TEXT, summary TEXT, metadata TEXT, error TEXT
        );
        CREATE TABLE IF NOT EXISTS task_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL,
            run_id INTEGER, kind TEXT NOT NULL, payload TEXT, created_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS task_links (
            parent_id TEXT NOT NULL, child_id TEXT NOT NULL,
            PRIMARY KEY (parent_id, child_id)
        );
    """)
    if extra_sql:
        conn.executescript(extra_sql)
    conn.commit()
    conn.close()
    return db_path, board


# --- ID Functions ---

class TestKanbanId:
    def test_task_id(self):
        assert proj.kanban_task_id("default", "t6") == "kanban:default:task:t6"

    def test_run_id(self):
        assert proj.kanban_run_id("default", 42) == "kanban:default:run:42"

    def test_event_id(self):
        eid = proj.kanban_event_id("default", 100)
        assert len(eid) == 32

    def test_different_boards(self):
        a = proj.kanban_task_id("default", "t1")
        b = proj.kanban_task_id("atm10", "t1")
        assert a != b

    def test_rejects_empty(self):
        with pytest.raises(ValueError):
            proj.kanban_task_id("", "t1")


# --- Status Mapping ---

class TestKanbanStatusMap:
    def test_completed(self):
        rs, out = proj._KANBAN_OUTCOME_MAP["completed"]
        assert rs == "completed"
        assert out == "completed"

    def test_unknown_status_is_none(self):
        assert proj._KANBAN_TASK_STATUS_MAP.get("nonexistent") is None


# --- Event Kind Classification ---

class TestKanbanEventKind:
    def test_whitelisted(self):
        for kind in ["created", "completed", "crashed", "archived"]:
            result = proj._kanban_classify_event_kind(kind)
            assert result is not None, f"{kind} should be whitelisted"

    def test_diagnostic(self):
        for kind in ["heartbeat", "commented", "spawned", "edited"]:
            assert proj._kanban_is_diagnostic_kind(kind), f"{kind} should be diagnostic"

    def test_unknown(self):
        assert proj._kanban_classify_event_kind("nonexistent") is None
        assert not proj._kanban_is_diagnostic_kind("nonexistent")


# --- map_kanban_db Integration ---

BASIC_KANBAN_SQL = """
    INSERT INTO tasks VALUES ('t1','Test task',NULL,NULL,'running',0,NULL,1000,NULL,NULL,'scratch',NULL,NULL,NULL,NULL,NULL,NULL);
    INSERT INTO task_runs VALUES (1,'t1','claude','running',1000,NULL,NULL,NULL,NULL,NULL);
    INSERT INTO task_events VALUES (1,'t1',1,'created',NULL,1000);
    INSERT INTO task_events VALUES (2,'t1',1,'claimed',NULL,1001);
    INSERT INTO task_events VALUES (3,'t1',1,'completed','{"ok":true}',1002);
"""

MULTI_RUN_SQL = BASIC_KANBAN_SQL + """
    INSERT INTO task_runs VALUES (2,'t1','claude','running',2000,2005,'crashed',NULL,NULL,'OOM');
"""

LINK_SQL = BASIC_KANBAN_SQL + """
    INSERT INTO tasks VALUES ('t2','Child task',NULL,NULL,'running',0,NULL,1000,NULL,NULL,'scratch',NULL,NULL,NULL,NULL,NULL,NULL);
    INSERT INTO task_runs VALUES (2,'t2','claude','running',2000,NULL,NULL,NULL,NULL,NULL);
    INSERT INTO task_links VALUES ('t1','t2');
"""

SWARM_SQL = BASIC_KANBAN_SQL + """
    INSERT INTO tasks VALUES ('swarm_root','Swarm','root body','claude','done',0,NULL,1000,NULL,1000,'scratch',NULL,NULL,NULL,NULL,'swarm_tpl','plan');
    INSERT INTO tasks VALUES ('worker1','Worker 1',NULL,NULL,'done',0,NULL,1001,1001,1100,'scratch',NULL,NULL,NULL,NULL,NULL,NULL);
    INSERT INTO task_runs VALUES (2,'swarm_root','claude','done',1000,1000,'completed','Done',NULL,NULL);
    INSERT INTO task_runs VALUES (3,'worker1','claude','done',1001,1100,'completed','Done',NULL,NULL);
    INSERT INTO task_links VALUES ('swarm_root','worker1');
"""


class TestMapKanbanDb:
    def test_basic_db(self, tmp_path):
        db_path, board = _kanban_test_db(tmp_path, extra_sql=BASIC_KANBAN_SQL)
        tasks, runs, trs, rrs, events, errors = proj.map_kanban_db(db_path, board)
        assert len(tasks) == 1
        assert tasks[0].id == "kanban:default:task:t1"
        assert tasks[0].status == "running"
        assert len(runs) == 1
        assert runs[0].status == "running"
        assert runs[0].outcome is None
        assert len(events) == 3
        assert len(errors) == 0

    def test_deterministic(self, tmp_path):
        db_path, board = _kanban_test_db(tmp_path, extra_sql=BASIC_KANBAN_SQL)
        r1 = proj.map_kanban_db(db_path, board)
        r2 = proj.map_kanban_db(db_path, board)
        assert len(r1[0]) == len(r2[0])

    def test_readonly_no_modification(self, tmp_path):
        import hashlib
        db_path, board = _kanban_test_db(tmp_path, extra_sql=BASIC_KANBAN_SQL)
        before = hashlib.sha256(open(db_path, "rb").read()).hexdigest()
        proj.map_kanban_db(db_path, board)
        after = hashlib.sha256(open(db_path, "rb").read()).hexdigest()
        assert before == after, "mode=ro must not modify database"

    def test_empty_db(self, tmp_path):
        db_path, board = _kanban_test_db(tmp_path)
        tasks, runs, trs, rrs, events, errors = proj.map_kanban_db(db_path, board)
        assert len(tasks) == 0
        assert len(errors) == 0

    def test_completed_run(self, tmp_path):
        sql = """
            INSERT INTO tasks VALUES ('t_done','Done',NULL,NULL,'done',0,NULL,1000,NULL,1100,'scratch',NULL,NULL,NULL,NULL,NULL,NULL);
            INSERT INTO task_runs VALUES (1,'t_done','claude','done',1000,1100,'completed','OK',NULL,NULL);
            INSERT INTO task_events VALUES (1,'t_done',1,'completed','{}',1100);
        """
        db_path, board = _kanban_test_db(tmp_path, extra_sql=sql)
        tasks, runs, trs, rrs, events, errors = proj.map_kanban_db(db_path, board)
        assert tasks[0].status == "done"
        assert runs[0].status == "completed"
        assert runs[0].outcome == "completed"

    def test_timeout_run(self, tmp_path):
        sql = """
            INSERT INTO tasks VALUES ('t_to','Timeout',NULL,NULL,'running',0,NULL,1000,NULL,NULL,'scratch',NULL,NULL,NULL,NULL,NULL,NULL);
            INSERT INTO task_runs VALUES (1,'t_to','claude','done',1000,2000,'timed_out',NULL,NULL,'timeout');
        """
        db_path, board = _kanban_test_db(tmp_path, extra_sql=sql)
        tasks, runs, trs, rrs, events, errors = proj.map_kanban_db(db_path, board)
        assert runs[0].status == "failed"
        assert runs[0].outcome == "timeout"

    def test_task_links_parent_child(self, tmp_path):
        db_path, board = _kanban_test_db(tmp_path, extra_sql=LINK_SQL)
        tasks, runs, trs, rrs, events, errors = proj.map_kanban_db(db_path, board)
        assert len(trs) == 1
        assert trs[0].relation_type == "parent_child"

    def test_task_links_swarm(self, tmp_path):
        db_path, board = _kanban_test_db(tmp_path, extra_sql=SWARM_SQL)
        tasks, runs, trs, rrs, events, errors = proj.map_kanban_db(db_path, board)
        assert any(tr.relation_type == "swarm" for tr in trs), "swarm task should have swarm relation"

    def test_diagnostic_events_unsupported(self, tmp_path):
        sql = """
            INSERT INTO tasks VALUES ('t_hb','HB',NULL,NULL,'running',0,NULL,1000,NULL,NULL,'scratch',NULL,NULL,NULL,NULL,NULL,NULL);
            INSERT INTO task_runs VALUES (1,'t_hb','claude','running',1000,NULL,NULL,NULL,NULL,NULL);
            INSERT INTO task_events VALUES (1,'t_hb',1,'heartbeat','{}',1000);
        """
        db_path, board = _kanban_test_db(tmp_path, extra_sql=sql)
        tasks, runs, trs, rrs, events, errors = proj.map_kanban_db(db_path, board)
        assert len(events) == 0
        assert any("heartbeat" in str(e) for e in errors if hasattr(e, "reason"))

    def test_unknown_event_kind_unsupported(self, tmp_path):
        sql = """
            INSERT INTO tasks VALUES ('t_x','X',NULL,NULL,'running',0,NULL,1000,NULL,NULL,'scratch',NULL,NULL,NULL,NULL,NULL,NULL);
            INSERT INTO task_runs VALUES (1,'t_x','claude','running',1000,NULL,NULL,NULL,NULL,NULL);
            INSERT INTO task_events VALUES (1,'t_x',1,'future_kind','{}',1000);
        """
        db_path, board = _kanban_test_db(tmp_path, extra_sql=sql)
        tasks, runs, trs, rrs, events, errors = proj.map_kanban_db(db_path, board)
        unsupported = [e for e in errors if isinstance(e, proj.UnsupportedRecord)]
        assert len(unsupported) >= 1

    def test_broken_link(self, tmp_path):
        sql = """
            INSERT INTO tasks VALUES ('t1','Task',NULL,NULL,'running',0,NULL,1000,NULL,NULL,'scratch',NULL,NULL,NULL,NULL,NULL,NULL);
            INSERT INTO task_runs VALUES (1,'t1','claude','running',1000,NULL,NULL,NULL,NULL,NULL);
            INSERT INTO task_links VALUES ('t1','nonexistent_child');
        """
        db_path, board = _kanban_test_db(tmp_path, extra_sql=sql)
        tasks, runs, trs, rrs, events, errors = proj.map_kanban_db(db_path, board)
        assert len(trs) == 0
        assert len(errors) >= 1

    def test_missing_table(self, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "bare.db"))
        conn.execute("CREATE TABLE tasks (id TEXT)")
        conn.commit(); conn.close()
        db_path = str(tmp_path / "bare.db")
        tasks, runs, trs, rrs, events, errors = proj.map_kanban_db(db_path, "bare")
        assert len(errors) == 0  # graceful: missing tables → empty results

    def test_corrupt_db(self, tmp_path):
        db_path = str(tmp_path / "corrupt.db")
        with open(db_path, "wb") as f:
            f.write(b"not a sqlite database")
        tasks, runs, trs, rrs, events, errors = proj.map_kanban_db(db_path, "corrupt")
        assert len(errors) >= 1
        assert len(tasks) == 0

    def test_unknown_status(self, tmp_path):
        sql = """
            INSERT INTO tasks VALUES ('t_bad','Bad',NULL,NULL,'future_status',0,NULL,1000,NULL,NULL,'scratch',NULL,NULL,NULL,NULL,NULL,NULL);
        """
        db_path, board = _kanban_test_db(tmp_path, extra_sql=sql)
        tasks, runs, trs, rrs, events, errors = proj.map_kanban_db(db_path, board)
        unsupported = [e for e in errors if isinstance(e, proj.UnsupportedRecord)]
        assert len(unsupported) >= 1
        assert len(tasks) == 0

    def test_run_with_metadata(self, tmp_path):
        sql = """
            INSERT INTO tasks VALUES ('t_m','Meta',NULL,NULL,'done',0,NULL,1000,NULL,1100,'scratch',NULL,NULL,NULL,NULL,NULL,NULL);
            INSERT INTO task_runs VALUES (1,'t_m','claude','done',1000,1100,'completed','OK','{"changed_files":["a.py"],"tests_run":5}',NULL);
        """
        db_path, board = _kanban_test_db(tmp_path, extra_sql=sql)
        tasks, runs, trs, rrs, events, errors = proj.map_kanban_db(db_path, board)
        assert len(runs) == 1
        assert runs[0].summary == "OK"

    def test_wal_mode_readonly_consistent(self, tmp_path):
        """mode=ro reader produces same result twice (consistent within connection)."""
        db_path = str(tmp_path / "wal.db")
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript("""
            CREATE TABLE tasks (id TEXT PRIMARY KEY, title TEXT, status TEXT, created_at INTEGER, workspace_kind TEXT DEFAULT 'scratch');
            CREATE TABLE task_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, profile TEXT, status TEXT, started_at INTEGER, ended_at INTEGER, outcome TEXT, summary TEXT, metadata TEXT, error TEXT);
            CREATE TABLE task_events (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, run_id INTEGER, kind TEXT, payload TEXT, created_at INTEGER);
            CREATE TABLE task_links (parent_id TEXT, child_id TEXT, PRIMARY KEY(parent_id, child_id));
            INSERT INTO tasks VALUES ('t1','WAL','running',1000,'scratch');
            INSERT INTO task_runs VALUES (1,'t1','claude','running',1000,NULL,NULL,NULL,NULL,NULL);
            INSERT INTO task_events VALUES (1,'t1',1,'created','{}',1000);
        """)
        conn.commit(); conn.close()
        # Two mode=ro reads produce identical results
        tasks1, runs1, _, _, events1, _ = proj.map_kanban_db(db_path, "wal")
        tasks2, runs2, _, _, events2, _ = proj.map_kanban_db(db_path, "wal")
        assert len(tasks1) == len(tasks2) == 1
        assert len(events1) == len(events2) == 1
        # Connection-level consistency within a single call
        assert tasks1[0].id == tasks2[0].id, "deterministic ID across calls"
