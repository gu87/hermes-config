"""Tests for Phase 1A — data models, deterministic IDs, pure mapping functions.

Covers all requirements from docs/architecture/unified-task-run-contract.md §5.2.
"""

import hashlib
import importlib.util
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
