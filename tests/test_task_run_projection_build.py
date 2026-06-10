"""Tests for Phase 1B — shadow projection builder.

Covers full-rebuild, atomic write, determinism, error handling,
and safety boundaries.
"""

import hashlib
import importlib.util
import json
import os
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

# Load Phase 1A
_spec_a = importlib.util.spec_from_file_location(
    "task_run_projection", str(SCRIPTS / "task-run-projection.py")
)
_proj = importlib.util.module_from_spec(_spec_a)
sys.modules["task_run_projection"] = _proj
assert _spec_a.loader is not None
_spec_a.loader.exec_module(_proj)

# Load Phase 1B build tool
_spec_b = importlib.util.spec_from_file_location(
    "task_run_projection_build", str(SCRIPTS / "task-run-projection-build.py")
)
_build = importlib.util.module_from_spec(_spec_b)
sys.modules["task_run_projection_build"] = _build
assert _spec_b.loader is not None
_spec_b.loader.exec_module(_build)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _write_jsonl(path: Path, records: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(r, ensure_ascii=False) + "\n" for r in records]
    path.write_text("".join(lines), encoding="utf-8")


def _make_minimal_team(tmp_path: Path, project: str = "staam") -> Path:
    """Construct a minimal Pipeline team directory with inbox, review, and ledger."""
    team = tmp_path / ".claude" / "teams" / project
    team.mkdir(parents=True, exist_ok=True)
    (team / "inbox").mkdir(exist_ok=True)
    (team / "outbox").mkdir(exist_ok=True)
    (team / "review").mkdir(exist_ok=True)
    (team / "runs").mkdir(exist_ok=True)
    (team / "tasks").mkdir(exist_ok=True)
    return team


@pytest.fixture
def team_dir(tmp_path):
    return _make_minimal_team(tmp_path)


@pytest.fixture
def team_with_data(team_dir):
    """Team dir with one Task Card, one gate record, two ledger lines."""
    # Task Card
    _write_json(team_dir / "inbox" / "staam_t6.json", {
        "task_card_id": "staam_t6",
        "goal": "Add API endpoint",
        "created_at": "2026-03-07T15:00:00Z",
        "compiled_intent": {
            "interpreted_intent": "Add REST API endpoint for users",
            "real_task": "Implement GET /users endpoint",
            "task_category": "feature",
            "risk_level": "R2",
            "preferred_agent": "claude",
        },
        "execution_plan": {
            "mode": "single_agent",
            "primary_agent": "claude",
        },
    })
    # Gate record
    _write_json(team_dir / "review" / "staam_t6_gate.json", {
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
    })
    # Ledger
    _write_jsonl(team_dir / "runs" / "ledger.jsonl", [
        {
            "schema_version": "2.8",
            "event": "lifecycle_event",
            "event_id": "life_staam_t6_20260307",
            "task_id": "staam_t6",
            "phase": "compiled",
            "status": "completed",
            "started_at": "2026-03-07T15:00:00Z",
        },
        {
            "schema_version": "2.8",
            "event": "run_started",
            "run_id": "run_t6_20260307_152200_123456",
            "task_id": "staam_t6",
            "agent_id": "claude",
            "run_type": "main",
            "started_at": "2026-03-07T15:22:00Z",
            "command": "hermes -z 'delegate_task(...)'",
            "cwd": "/home/user/projects/staam",
            "timeout_seconds": 600,
        },
        {
            "schema_version": "2.8",
            "event": "run_finished",
            "run_id": "run_t6_20260307_152200_123456",
            "task_id": "staam_t6",
            "agent_id": "claude",
            "run_type": "main",
            "started_at": "2026-03-07T15:22:00Z",
            "finished_at": "2026-03-07T15:23:45Z",
            "exit_code": 0,
            "classification": "ok",
            "duration_seconds": 104.877,
            "stdout_tail": "outbox written successfully",
            "stderr_tail": "",
        },
    ])
    return team_dir


# ============================================================================
# 1.  Full Rebuild
# ============================================================================

class TestBuildProjection:
    def test_build_returns_records(self, team_with_data):
        records = _build.build_projection("staam", team_with_data)
        assert len(records) > 0

    def test_output_contains_task(self, team_with_data):
        records = _build.build_projection("staam", team_with_data)
        tasks = [r for r in records if r.get("projection_type") == "Task"]
        assert len(tasks) >= 1
        t = tasks[0]
        assert t["id"] == "pipeline:staam:task:staam_t6"

    def test_output_contains_task_spec(self, team_with_data):
        records = _build.build_projection("staam", team_with_data)
        specs = [r for r in records if r.get("projection_type") == "TaskSpec"]
        assert len(specs) >= 1
        assert specs[0]["task_id"] == "pipeline:staam:task:staam_t6"

    def test_output_contains_run(self, team_with_data):
        records = _build.build_projection("staam", team_with_data)
        runs = [r for r in records if r.get("projection_type") == "Run"]
        # run_started + run_finished each produce a Run (same id)
        assert len(runs) >= 1
        assert any(r["id"] == "pipeline:staam:run:run_t6_20260307_152200_123456" for r in runs)

    def test_output_contains_review_decision(self, team_with_data):
        records = _build.build_projection("staam", team_with_data)
        rds = [r for r in records if r.get("projection_type") == "ReviewDecision"]
        assert len(rds) >= 1
        assert rds[0]["decision"] == "approve"

    def test_output_contains_domain_event_envelope(self, team_with_data):
        records = _build.build_projection("staam", team_with_data)
        events = [r for r in records if r.get("projection_type") == "DomainEventEnvelope"]
        assert len(events) >= 1
        types = {e["event_type"] for e in events}
        assert "pipeline.compiled" in types
        assert "pipeline.run_started" in types
        assert "pipeline.run_finished" in types
        # gate_checked comes from events.jsonl (not present in team_with_data)

    def test_every_record_has_projection_type(self, team_with_data):
        records = _build.build_projection("staam", team_with_data)
        for r in records:
            assert "projection_type" in r, f"missing projection_type: {list(r.keys())[:5]}"


# ============================================================================
# 2.  Error Handling — Explicit, Never Silent
# ============================================================================

class TestErrorHandling:
    def test_invalid_json_in_inbox_is_mapping_error(self, team_dir):
        (team_dir / "inbox" / "bad.json").write_text("not json{{{", encoding="utf-8")
        records = _build.build_projection("staam", team_dir)
        errors = [r for r in records if r.get("projection_type") == "MappingError"]
        assert len(errors) >= 1
        assert "JSON decode error" in errors[0]["error"]

    def test_unsupported_ledger_record_present(self, team_dir):
        _write_jsonl(team_dir / "runs" / "ledger.jsonl", [
            {"event": "weird_event_type", "task_id": "staam_t6"}
        ])
        records = _build.build_projection("staam", team_dir)
        unsupported = [r for r in records if r.get("projection_type") == "UnsupportedRecord"]
        assert len(unsupported) >= 1

    def test_empty_team_dir_produces_empty_output(self, team_dir):
        records = _build.build_projection("staam", team_dir)
        assert records == []


# ============================================================================
# 3.  Determinism — Byte-Identical Output
# ============================================================================

class TestDeterminism:
    def test_repeated_build_produces_byte_identical_output(self, team_with_data, tmp_path):
        out1 = tmp_path / "out1.jsonl"
        out2 = tmp_path / "out2.jsonl"

        records1 = _build.build_projection("staam", team_with_data)
        _build.write_projection(records1, out1)

        records2 = _build.build_projection("staam", team_with_data)
        _build.write_projection(records2, out2)

        assert out1.read_bytes() == out2.read_bytes()

    def test_repeated_build_produces_same_sha256(self, team_with_data, tmp_path):
        out = tmp_path / "out.jsonl"
        records = _build.build_projection("staam", team_with_data)
        _build.write_projection(records, out)
        h1 = hashlib.sha256(out.read_bytes()).hexdigest()

        records2 = _build.build_projection("staam", team_with_data)
        _build.write_projection(records2, out)
        h2 = hashlib.sha256(out.read_bytes()).hexdigest()

        assert h1 == h2


# ============================================================================
# 4.  Atomic Write
# ============================================================================

class TestAtomicWrite:
    def test_write_uses_os_replace(self, team_with_data, tmp_path, monkeypatch):
        """Verify that write_projection creates a temp file and replaces."""
        out = tmp_path / "output.jsonl"
        records = _build.build_projection("staam", team_with_data)

        seen_temp = []
        seen_replace = []
        _real_replace = os.replace
        _real_open = open

        def _track_replace(src, dst):
            seen_replace.append((str(src), str(dst)))
            return _real_replace(src, dst)

        monkeypatch.setattr(os, "replace", _track_replace)
        _build.write_projection(records, out)

        assert len(seen_replace) == 1
        assert str(out) in seen_replace[0][1]
        assert out.exists()

    def test_build_failure_does_not_overwrite_existing(self, team_with_data, tmp_path, monkeypatch):
        """If write fails mid-way, the existing output is untouched."""
        out = tmp_path / "output.jsonl"
        # Pre-write existing content
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("existing content", encoding="utf-8")

        # Force os.replace to raise
        def _failing_replace(src, dst):
            raise OSError("simulated failure")

        monkeypatch.setattr(os, "replace", _failing_replace)

        records = _build.build_projection("staam", team_with_data)
        with pytest.raises(OSError, match="simulated failure"):
            _build.write_projection(records, out)

        # Existing file unchanged
        assert out.read_text() == "existing content"


# ============================================================================
# 5.  Original Files Untouched
# ============================================================================

class TestOriginalFilesUntouched:
    def test_inbox_files_unchanged_after_build(self, team_with_data):
        inbox_file = team_with_data / "inbox" / "staam_t6.json"
        before = inbox_file.read_bytes()
        _build.build_projection("staam", team_with_data)
        assert inbox_file.read_bytes() == before

    def test_review_files_unchanged_after_build(self, team_with_data):
        review_file = team_with_data / "review" / "staam_t6_gate.json"
        before = review_file.read_bytes()
        _build.build_projection("staam", team_with_data)
        assert review_file.read_bytes() == before

    def test_ledger_unchanged_after_build(self, team_with_data):
        ledger_file = team_with_data / "runs" / "ledger.jsonl"
        before = ledger_file.read_bytes()
        _build.build_projection("staam", team_with_data)
        assert ledger_file.read_bytes() == before


# ============================================================================
# 6.  Default Paths
# ============================================================================

class TestDefaultPaths:
    def test_default_team_dir(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        expected = tmp_path / ".claude" / "teams" / "staam"
        assert _build._default_team_dir("staam") == expected

    def test_default_output_path(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        expected = (
            tmp_path / ".hermes" / "projections" / "task-card-pipeline" / "staam" / "events.jsonl"
        )
        assert _build._default_output("staam") == expected


# ============================================================================
# 7.  Source Coverage — Only Supported Sources
# ============================================================================

class TestSourceCoverage:
    def test_does_read_outbox(self, team_dir, monkeypatch):
        """Verify the builder now reads outbox files (Phase 1B slice 2)."""
        _write_json(team_dir / "outbox" / "out.json", {"task_id": "x"})
        _write_json(team_dir / "inbox" / "card.json", {
            "task_card_id": "staam_t1", "goal": "test", "created_at": "2026-01-01T00:00:00Z",
        })
        import builtins
        original_open = builtins.open
        opened_paths = []

        def _track_open(*args, **kwargs):
            opened_paths.append(str(args[0]) if args else "")
            return original_open(*args, **kwargs)

        monkeypatch.setattr(builtins, "open", _track_open)
        _build.build_projection("staam", team_dir)

        outbox_paths = [p for p in opened_paths if "/outbox/" in p.replace("\\", "/")]
        assert len(outbox_paths) >= 1, f"Builder should read outbox: {outbox_paths}"

    def test_does_read_events_jsonl(self, team_dir, monkeypatch):
        """Verify the builder now reads events.jsonl (Phase 1B events dedup slice)."""
        _write_jsonl(team_dir / "events.jsonl", [{"event": "gate_checked", "task_id": "t1", "timestamp": "2026-01-01T00:00:00Z"}])
        _write_json(team_dir / "inbox" / "card.json", {
            "task_card_id": "staam_t1", "goal": "test", "created_at": "2026-01-01T00:00:00Z",
        })
        import builtins
        original_open = builtins.open
        opened_paths = []

        def _track_open(*args, **kwargs):
            opened_paths.append(str(args[0]) if args else "")
            return original_open(*args, **kwargs)

        monkeypatch.setattr(builtins, "open", _track_open)
        _build.build_projection("staam", team_dir)

        events_paths = [p for p in opened_paths if "events.jsonl" in p]
        assert len(events_paths) >= 1, f"Builder should read events.jsonl: {events_paths}"

    def test_does_not_read_tasks_index(self, team_dir, monkeypatch):
        """Verify the builder does not open tasks/index.jsonl."""
        (team_dir / "tasks").mkdir(parents=True, exist_ok=True)
        _write_jsonl(team_dir / "tasks" / "index.jsonl", [{"event": "gate_checked"}])
        _write_json(team_dir / "inbox" / "card.json", {
            "task_card_id": "staam_t1", "goal": "test", "created_at": "2026-01-01T00:00:00Z",
        })
        import builtins
        original_open = builtins.open
        opened_paths = []

        def _track_open(*args, **kwargs):
            opened_paths.append(str(args[0]) if args else "")
            return original_open(*args, **kwargs)

        monkeypatch.setattr(builtins, "open", _track_open)
        _build.build_projection("staam", team_dir)

        index_paths = [p for p in opened_paths if "index.jsonl" in p]
        assert len(index_paths) == 0, f"Builder read tasks/index.jsonl: {index_paths}"

    def test_tasks_index_never_changes_projection_bytes(self, team_dir, tmp_path):
        """Absent, unique, corrupt, or changed index data must not affect output."""
        _write_json(team_dir / "inbox" / "card.json", {
            "task_card_id": "staam_t1", "goal": "test", "created_at": "2026-01-01T00:00:00Z",
        })
        index_path = team_dir / "tasks" / "index.jsonl"
        index_path.parent.mkdir(parents=True, exist_ok=True)

        def _build_bytes(name):
            output = tmp_path / name
            _build.write_projection(_build.build_projection("staam", team_dir), output)
            return output.read_bytes()

        baseline = _build_bytes("absent.jsonl")

        _write_jsonl(index_path, [{
            "event": "unique_index_only_event",
            "task_id": "index_only_task",
            "timestamp": "2099-01-01T00:00:00Z",
        }])
        assert _build_bytes("unique.jsonl") == baseline

        index_path.write_text("not valid json{{{\n", encoding="utf-8")
        assert _build_bytes("corrupt.jsonl") == baseline

        _write_jsonl(index_path, [{"event": "completely_changed", "task_id": "other"}])
        assert _build_bytes("changed.jsonl") == baseline


# ============================================================================
# 8.  CLI
# ============================================================================

class TestCLI:
    def test_cli_with_minimal_data(self, team_with_data, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        out = tmp_path / "out.jsonl"
        # Override team dir so we don't depend on real HOME
        rc = _build.main(["--project", "staam", "--team-dir", str(team_with_data), "--output", str(out)])
        assert rc == 0
        assert out.exists()
        lines = out.read_text().strip().splitlines()
        assert len(lines) > 0
        for line in lines:
            obj = json.loads(line)
            assert "projection_type" in obj

    def test_cli_missing_team_dir(self, tmp_path):
        rc = _build.main(["--project", "staam", "--team-dir", str(tmp_path / "nope")])
        assert rc == 1

    def test_cli_empty_project(self):
        rc = _build.main(["--project", ""])
        assert rc == 2


# ============================================================================
# 9.  Non-Object JSONL Records → MappingError (Fix 1)
# ============================================================================

class TestNonObjectJsonl:
    def test_array_in_jsonl_becomes_mapping_error(self, team_dir):
        _write_jsonl(team_dir / "runs" / "ledger.jsonl", [
            [1, 2, 3],
            {"event": "lifecycle_event", "event_id": "ev1", "task_id": "t1",
             "phase": "compiled", "started_at": "2026-01-01T00:00:00Z"},
        ])
        records = _build.build_projection("staam", team_dir)
        errors = [r for r in records if r.get("projection_type") == "MappingError"]
        assert len(errors) >= 1
        assert any("list" in e.get("error", "").lower() for e in errors)

    def test_string_in_jsonl_becomes_mapping_error(self, team_dir):
        _write_jsonl(team_dir / "runs" / "ledger.jsonl", ["just a string"])
        records = _build.build_projection("staam", team_dir)
        errors = [r for r in records if r.get("projection_type") == "MappingError"]
        assert len(errors) >= 1

    def test_number_in_jsonl_becomes_mapping_error(self, team_dir):
        _write_jsonl(team_dir / "runs" / "ledger.jsonl", [42])
        records = _build.build_projection("staam", team_dir)
        errors = [r for r in records if r.get("projection_type") == "MappingError"]
        assert len(errors) >= 1

    def test_null_in_jsonl_becomes_mapping_error(self, team_dir):
        _write_jsonl(team_dir / "runs" / "ledger.jsonl", [None])
        records = _build.build_projection("staam", team_dir)
        errors = [r for r in records if r.get("projection_type") == "MappingError"]
        assert len(errors) >= 1

    def test_non_object_jsonl_does_not_abort_other_records(self, team_dir):
        """Non-object lines produce MappingError but don't prevent valid lines from projecting."""
        _write_jsonl(team_dir / "runs" / "ledger.jsonl", [
            "not an object",
            {"event": "lifecycle_event", "event_id": "ev1", "task_id": "t1",
             "phase": "compiled", "started_at": "2026-01-01T00:00:00Z"},
        ])
        records = _build.build_projection("staam", team_dir)
        errors = [r for r in records if r.get("projection_type") == "MappingError"]
        events = [r for r in records if r.get("projection_type") == "DomainEventEnvelope"]
        assert len(errors) >= 1
        assert len(events) >= 1  # valid record still projected


# ============================================================================
# 10. Deterministic Ordering (Fix 2)
# ============================================================================

class TestDeterministicOrdering:
    def test_sort_key_determines_order(self, team_with_data):
        """Output order: inbox sources before review before ledger (by _sort_key)."""
        records = _build.build_projection("staam", team_with_data)
        sources = []
        for r in records:
            loc = r.get("source_location", "")
            if "/inbox/" in loc.replace("\\", "/"):
                sources.append("inbox")
            elif "/review/" in loc.replace("\\", "/"):
                sources.append("review")
            elif "/ledger.jsonl" in loc.replace("\\", "/") or "/runs/" in loc.replace("\\", "/"):
                sources.append("ledger")
            else:
                # MappingError from parse — source_location carries file path
                sloc = str(r.get("source_location", ""))
                if "/inbox/" in sloc.replace("\\", "/"):
                    sources.append("inbox")
                elif "/review/" in sloc.replace("\\", "/"):
                    sources.append("review")
                elif "/ledger.jsonl" in sloc.replace("\\", "/"):
                    sources.append("ledger")
                else:
                    sources.append("unknown")
        # Verify: inbox before review before ledger (stable order)
        first_inbox = next((i for i, s in enumerate(sources) if s == "inbox"), None)
        first_review = next((i for i, s in enumerate(sources) if s == "review"), None)
        first_ledger = next((i for i, s in enumerate(sources) if s == "ledger"), None)
        if first_inbox is not None and first_review is not None:
            assert first_inbox < first_review, "inbox records must come before review"
        if first_review is not None and first_ledger is not None:
            assert first_review < first_ledger, "review records must come before ledger"

    def test_repeated_sort_produces_identical_order(self, team_with_data):
        """Calling sort twice produces the same result."""
        records1 = _build.build_projection("staam", team_with_data)
        records2 = _build.build_projection("staam", team_with_data)
        assert len(records1) == len(records2)
        for i, (r1, r2) in enumerate(zip(records1, records2)):
            assert r1.get("projection_type") == r2.get("projection_type"), f"order mismatch at index {i}"


# ============================================================================
# 11. Concurrent-Safe Temp Files (Fix 3)
# ============================================================================

class TestConcurrentTempFiles:
    def test_two_writes_use_different_temp_paths(self, team_with_data, tmp_path, monkeypatch):
        """Two sequential write_projection calls must use different temp file names."""
        out = tmp_path / "output.jsonl"
        records = _build.build_projection("staam", team_with_data)

        temp_paths = []
        _real_open = open

        def _track_open(file, *args, **kwargs):
            fname = str(file) if hasattr(file, '__fspath__') or isinstance(file, (str,)) else str(getattr(file, 'name', file))
            if ".tmp." in str(fname):
                temp_paths.append(str(fname))
            return _real_open(file, *args, **kwargs)

        monkeypatch.setattr("builtins.open", _track_open)
        # The write uses open() with the tmp_path; we intercept that
        _build.write_projection(list(records), out)
        temp1 = list(temp_paths)

        temp_paths.clear()
        _build.write_projection(list(records), out)
        temp2 = list(temp_paths)

        # The temp files must be different across calls
        assert temp1 != temp2, f"Temp paths should differ: {temp1} vs {temp2}"


# ============================================================================
# 12. Outbox Integration (Phase 1B slice 2)
# ============================================================================

OUTBOX_DATA = {
    "schema_version": "2.8",
    "task_id": "staam_t6",
    "agent_id": "claude",
    "status": "success",
    "summary": "Added GET /users endpoint",
    "changed_files": ["src/api/users.py", "tests/test_users.py"],
    "changed_files_source": "git_diff",
    "verification": {
        "commands_run": ["pytest tests/test_users.py -q"],
        "output_summary": "2 passed",
    },
    "evidence": {
        "verification_commands": ["pytest tests/test_users.py -q"],
        "verification_output_summary": "2 passed",
        "known_risks": [],
    },
    "known_risks": [],
    "errors": [],
    "error_taxonomy": [],
    "needs_human_review": False,
    "timestamp": "2026-03-07T15:23:00Z",
}


@pytest.fixture
def team_with_outbox(team_dir):
    """Team dir with one outbox file."""
    _write_json(team_dir / "outbox" / "staam_t6_result.json", OUTBOX_DATA)
    return team_dir


class TestOutboxBuilderIntegration:
    def test_builder_reads_outbox(self, team_with_outbox):
        records = _build.build_projection("staam", team_with_outbox)
        arts = [r for r in records if r.get("projection_type") == "Artifact"]
        evs = [r for r in records if r.get("projection_type") == "Evidence"]
        assert len(arts) >= 1
        assert len(evs) >= 1

    def test_outbox_artifacts_have_correct_types(self, team_with_outbox):
        records = _build.build_projection("staam", team_with_outbox)
        arts = [r for r in records if r.get("projection_type") == "Artifact"]
        types = {a["artifact_type"] for a in arts}
        assert "outbox" in types
        assert "changed_file" in types

    def test_outbox_no_run_created(self, team_with_outbox):
        records = _build.build_projection("staam", team_with_outbox)
        # No Run should come from outbox (only from ledger, which is absent here)
        runs = [r for r in records if r.get("projection_type") == "Run"]
        assert len(runs) == 0

    def test_outbox_run_id_is_none(self, team_with_outbox):
        records = _build.build_projection("staam", team_with_outbox)
        arts = [r for r in records if r.get("projection_type") == "Artifact"]
        for a in arts:
            assert a.get("run_id") is None

    def test_invalid_outbox_json_produces_mapping_error(self, team_dir):
        (team_dir / "outbox").mkdir(exist_ok=True)
        (team_dir / "outbox" / "bad.json").write_text("not json{{{", encoding="utf-8")
        records = _build.build_projection("staam", team_dir)
        errors = [r for r in records if r.get("projection_type") == "MappingError"]
        assert len(errors) >= 1

    def test_outbox_does_not_block_other_sources(self, team_with_outbox):
        """Single broken outbox doesn't prevent other sources from projecting."""
        _write_json(team_with_outbox / "inbox" / "card.json", {
            "task_card_id": "staam_t1", "goal": "test", "created_at": "2026-01-01T00:00:00Z",
        })
        _write_json(team_with_outbox / "outbox" / "bad.json", "not json")
        records = _build.build_projection("staam", team_with_outbox)
        tasks = [r for r in records if r.get("projection_type") == "Task"]
        errors = [r for r in records if r.get("projection_type") == "MappingError"]
        assert len(tasks) >= 1
        assert len(errors) >= 1

    def test_repeated_outbox_build_deterministic(self, team_with_outbox, tmp_path):
        out1 = tmp_path / "out1.jsonl"
        out2 = tmp_path / "out2.jsonl"
        _build.write_projection(_build.build_projection("staam", team_with_outbox), out1)
        _build.write_projection(_build.build_projection("staam", team_with_outbox), out2)
        assert out1.read_bytes() == out2.read_bytes()

    def test_outbox_sort_order_stable(self, team_with_outbox):
        """Multiple outbox files maintain stable order across rebuilds."""
        _write_json(team_with_outbox / "outbox" / "aaa_result.json", dict(OUTBOX_DATA, task_id="t1"))
        _write_json(team_with_outbox / "outbox" / "zzz_result.json", dict(OUTBOX_DATA, task_id="t2"))
        r1 = _build.build_projection("staam", team_with_outbox)
        r2 = _build.build_projection("staam", team_with_outbox)
        assert len(r1) == len(r2)
        for i in range(len(r1)):
            assert r1[i].get("projection_type") == r2[i].get("projection_type")


# ============================================================================
# 13. Events.jsonl Integration (Phase 1B events dedup slice)
# ============================================================================

EVENTS_JSONL_RECORDS = [
    {"event": "gate_checked", "task_id": "staam_t6", "decision": "approved",
     "timestamp": "2026-03-07T15:30:00Z"},
    {"event": "revision_created", "task_id": "staam_t6",
     "revision_task_id": "staam_t6_rev1", "attempt": 1,
     "timestamp": "2026-03-07T15:31:00Z"},
]


@pytest.fixture
def team_with_events(team_dir):
    """Team dir with events.jsonl."""
    _write_jsonl(team_dir / "events.jsonl", EVENTS_JSONL_RECORDS)
    return team_dir


class TestEventsJsonlBuilderIntegration:
    def test_builder_reads_events_jsonl(self, team_with_events):
        records = _build.build_projection("staam", team_with_events)
        events = [r for r in records if r.get("projection_type") == "DomainEventEnvelope"]
        assert len(events) >= 2

    def test_events_produce_gate_checked(self, team_with_events):
        records = _build.build_projection("staam", team_with_events)
        types = {e["event_type"] for e in records if e.get("projection_type") == "DomainEventEnvelope"}
        assert "pipeline.gate_checked" in types

    def test_events_ledger_dedup_skips_duplicate(self, team_with_events):
        """When ledger has same lifecycle_event, events.jsonl is skipped (not UnsupportedRecord)."""
        _write_jsonl(team_with_events / "runs" / "ledger.jsonl", [
            {"event": "lifecycle_event", "event_id": "life_staam_t6_gate",
             "task_id": "staam_t6", "phase": "gate_checked", "decision": "approved",
             "started_at": "2026-03-07T15:30:00Z"},
        ])
        records = _build.build_projection("staam", team_with_events)
        gate_events = [e for e in records
                       if e.get("projection_type") == "DomainEventEnvelope"
                       and e.get("event_type") == "pipeline.gate_checked"]
        # ledger produces the lifecycle event; events.jsonl is deduped → exactly 1
        assert len(gate_events) == 1

    def test_events_revision_dispatched_task_id(self, team_dir):
        _write_jsonl(team_dir / "events.jsonl", [
            {"event": "revision_dispatched", "task_id": "staam_t6",
             "revision_task_id": "staam_t6_rev1",
             "run_id": "run_rev1_20260307",
             "timestamp": "2026-03-07T15:32:00Z"},
        ])
        records = _build.build_projection("staam", team_dir)
        events = [e for e in records if e.get("projection_type") == "DomainEventEnvelope"]
        assert len(events) == 1
        assert events[0]["task_id"] == "pipeline:staam:task:staam_t6_rev1"
        assert events[0]["event_scope"] == "run"

    def test_invalid_jsonl_line_is_mapping_error(self, team_dir):
        (team_dir / "events.jsonl").write_text("not json{{{", encoding="utf-8")
        records = _build.build_projection("staam", team_dir)
        errors = [r for r in records if r.get("projection_type") == "MappingError"]
        assert len(errors) >= 1

    def test_non_object_jsonl_line_is_mapping_error(self, team_dir):
        _write_jsonl(team_dir / "events.jsonl", ["just a string"])
        records = _build.build_projection("staam", team_dir)
        errors = [r for r in records if r.get("projection_type") == "MappingError"]
        assert len(errors) >= 1

    def test_repeated_events_build_deterministic(self, team_with_events, tmp_path):
        out1 = tmp_path / "out1.jsonl"
        out2 = tmp_path / "out2.jsonl"
        _build.write_projection(_build.build_projection("staam", team_with_events), out1)
        _build.write_projection(_build.build_projection("staam", team_with_events), out2)
        assert out1.read_bytes() == out2.read_bytes()


# ============================================================================
# 14.  Builder-Level Real-Structure Dedup Integration Tests (Phase 1D)
# ============================================================================
# These tests exercise the full build_projection() pipeline with fixtures
# that match real run_ledger.py output (lifecycle run_id=lifecycle ID,
# related_run_id=execution run).  They verify that ledger + events.jsonl
# dedup produces exactly one DomainEventEnvelope — not just that keys match.

_REAL_LEDGER_GATE_CHECKED = {
    "event": "lifecycle_event",
    "event_id": "life_staam_t6_gate_001",
    "run_id": "life_staam_t6_gate_001",       # lifecycle's own ID
    "task_id": "staam_t6",
    "phase": "gate_checked",
    "decision": "revision_needed",
    "started_at": "2026-03-07T15:30:00Z",
}

_REAL_EVENTS_GATE_CHECKED = {
    "event": "gate_checked",
    "task_id": "staam_t6",
    "decision": "revision_needed",
    "timestamp": "2026-03-07T15:30:00Z",
}

_REAL_LEDGER_REVISION_CREATED = {
    "event": "lifecycle_event",
    "event_id": "life_staam_t6_rev_created_001",
    "run_id": "life_staam_t6_rev_created_001",  # lifecycle's own ID
    "task_id": "staam_t6",
    "phase": "revision_created",
    "revision_task_id": "staam_t6_rev1",
    "attempt": 1,
    "started_at": "2026-03-07T15:31:00Z",
}

_REAL_EVENTS_REVISION_CREATED = {
    "event": "revision_created",
    "task_id": "staam_t6",
    "revision_task_id": "staam_t6_rev1",
    "attempt": 1,
    "timestamp": "2026-03-07T15:31:00Z",
}

_REAL_LEDGER_REVISION_DISPATCHED = {
    "event": "lifecycle_event",
    "event_id": "life_staam_t6_rev_dispatched_001",
    "run_id": "life_staam_t6_rev_dispatched_001",     # lifecycle's own ID
    "related_run_id": "run_rev1_20260307",             # real execution run
    "task_id": "staam_t6",
    "revision_task_id": "staam_t6_rev1",
    "phase": "revision_dispatched",
    "status": "ok",
    "started_at": "2026-03-07T15:32:00Z",
}

_REAL_EVENTS_REVISION_DISPATCHED = {
    "event": "revision_dispatched",
    "task_id": "staam_t6",
    "revision_task_id": "staam_t6_rev1",
    "run_id": "run_rev1_20260307",   # in events.jsonl, run_id IS the execution run
    "timestamp": "2026-03-07T15:32:00Z",
}


@pytest.fixture
def team_all_three_events(team_dir):
    """Team dir with 3 real-structure ledger lifecycle events + matching
    events.jsonl records.  Dedup should eliminate all 3 events.jsonl records."""
    _write_jsonl(team_dir / "runs" / "ledger.jsonl", [
        dict(_REAL_LEDGER_GATE_CHECKED),
        dict(_REAL_LEDGER_REVISION_CREATED),
        dict(_REAL_LEDGER_REVISION_DISPATCHED),
    ])
    _write_jsonl(team_dir / "events.jsonl", [
        dict(_REAL_EVENTS_GATE_CHECKED),
        dict(_REAL_EVENTS_REVISION_CREATED),
        dict(_REAL_EVENTS_REVISION_DISPATCHED),
    ])
    return team_dir


class TestBuilderRealStructureDedup:
    """Integration tests that build_projection() with real-structure ledger
    + events.jsonl fixtures produces exactly one event per lifecycle."""

    def test_gate_checked_dedup_single_event(self, team_all_three_events):
        records = _build.build_projection("staam", team_all_three_events)
        gate_events = [
            e for e in records
            if e.get("projection_type") == "DomainEventEnvelope"
            and e.get("event_type") == "pipeline.gate_checked"
        ]
        assert len(gate_events) == 1, (
            f"expected exactly 1 gate_checked event after dedup, got {len(gate_events)}"
        )

    def test_revision_created_dedup_single_event(self, team_all_three_events):
        records = _build.build_projection("staam", team_all_three_events)
        rc_events = [
            e for e in records
            if e.get("projection_type") == "DomainEventEnvelope"
            and e.get("event_type") == "pipeline.revision_created"
        ]
        assert len(rc_events) == 1, (
            f"expected exactly 1 revision_created event after dedup, got {len(rc_events)}"
        )

    def test_revision_dispatched_dedup_single_event(self, team_all_three_events):
        records = _build.build_projection("staam", team_all_three_events)
        rd_events = [
            e for e in records
            if e.get("projection_type") == "DomainEventEnvelope"
            and e.get("event_type") == "pipeline.revision_dispatched"
        ]
        assert len(rd_events) == 1, (
            f"expected exactly 1 revision_dispatched event after dedup, got {len(rd_events)}"
        )

    def test_revision_dispatched_uses_related_run_id(self, team_all_three_events):
        """The unified run_id must come from related_run_id, not lifecycle's own ID."""
        records = _build.build_projection("staam", team_all_three_events)
        rd_events = [
            e for e in records
            if e.get("projection_type") == "DomainEventEnvelope"
            and e.get("event_type") == "pipeline.revision_dispatched"
        ]
        assert len(rd_events) == 1
        ev = rd_events[0]
        assert ev["run_id"] == "pipeline:staam:run:run_rev1_20260307", (
            f"expected run_id from related_run_id, got {ev['run_id']}"
        )
        assert ev["event_scope"] == "run"

    def test_lifecycle_own_id_not_execution_run(self, team_all_three_events):
        """The lifecycle's own run_id (life_xxx) must NOT appear as a unified run_id
        for any event that lacks a related_run_id."""
        records = _build.build_projection("staam", team_all_three_events)
        for r in records:
            if r.get("projection_type") == "DomainEventEnvelope":
                rid = r.get("run_id")
                if rid is not None:
                    assert "life_" not in rid, (
                        f"lifecycle own ID leaked into unified run_id: {rid} "
                        f"(event_type={r.get('event_type')})"
                    )

    def test_gate_checked_run_id_is_none(self, team_all_three_events):
        """gate_checked has no related_run_id → unified run_id must be None."""
        records = _build.build_projection("staam", team_all_three_events)
        gate_events = [
            e for e in records
            if e.get("projection_type") == "DomainEventEnvelope"
            and e.get("event_type") == "pipeline.gate_checked"
        ]
        assert len(gate_events) == 1
        assert gate_events[0]["run_id"] is None
        assert gate_events[0]["event_scope"] == "task"

    def test_revision_created_run_id_is_none(self, team_all_three_events):
        """revision_created has no related_run_id → unified run_id must be None."""
        records = _build.build_projection("staam", team_all_three_events)
        rc_events = [
            e for e in records
            if e.get("projection_type") == "DomainEventEnvelope"
            and e.get("event_type") == "pipeline.revision_created"
        ]
        assert len(rc_events) == 1
        assert rc_events[0]["run_id"] is None
        assert rc_events[0]["event_scope"] == "task"

    def test_all_domain_events_are_unique_by_type(self, team_all_three_events):
        """After dedup, each pipeline lifecycle event_type appears at most once."""
        records = _build.build_projection("staam", team_all_three_events)
        event_type_counts = {}
        for r in records:
            if r.get("projection_type") == "DomainEventEnvelope":
                et = r["event_type"]
                event_type_counts[et] = event_type_counts.get(et, 0) + 1
        lifecycle_types = [
            "pipeline.gate_checked",
            "pipeline.revision_created",
            "pipeline.revision_dispatched",
        ]
        for et in lifecycle_types:
            assert event_type_counts.get(et, 0) <= 1, (
                f"{et} appears {event_type_counts.get(et, 0)} times, expected ≤1"
            )


# ============================================================================
# 15.  Phase 2B — Delegation Builder CLI Wrapper Tests
# ============================================================================

DELEG_STARTED = {
    "schema_version": "delegate_v1", "phase": "run_started",
    "parent_session_id": "uuid-S0", "delegate_call_id": "toolu_abc",
    "task_index": 0, "subagent_session_id": "uuid-S1",
    "parent_delegate_task_id": None, "parent_delegate_run_id": None,
    "root_task_id": None, "depth": 1, "role": "leaf",
    "goal": "CLI wrapper test", "toolsets": ["read"],
    "model": "claude-sonnet-4-6",
    "started_at": "2026-06-10T15:00:00.000000+00:00",
}

DELEG_TERMINAL = {
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


class TestDelegationCLI:
    """CLI wrapper tests exercising the --delegation flag through main()."""

    def test_delegation_flag_with_data(self, team_dir, tmp_path):
        """--delegation with a populated journal dir produces output."""
        deleg_dir = tmp_path / "delegations"
        deleg_dir.mkdir()
        (deleg_dir / "uuid-S0.jsonl").write_text(
            json.dumps(DELEG_STARTED) + "\n" + json.dumps(DELEG_TERMINAL) + "\n"
        )
        out = tmp_path / "out.jsonl"
        rc = _build.main([
            "--project", "staam",
            "--team-dir", str(team_dir),
            "--delegation",
            "--delegations-dir", str(deleg_dir),
            "--delegation-output", str(out),
        ])
        assert rc == 0
        assert out.exists()
        lines = out.read_text().strip().splitlines()
        assert len(lines) > 0

    def test_delegation_flag_empty_dir(self, team_dir, tmp_path):
        """--delegation with an empty delegations dir produces empty output."""
        deleg_dir = tmp_path / "empty_deleg"
        deleg_dir.mkdir()
        out = tmp_path / "out.jsonl"
        rc = _build.main([
            "--project", "staam",
            "--team-dir", str(team_dir),
            "--delegation",
            "--delegations-dir", str(deleg_dir),
            "--delegation-output", str(out),
        ])
        assert rc == 0
        # Empty dir → 0 records written
        lines = [l for l in out.read_text().strip().splitlines() if l.strip()] if out.exists() else []
        assert len(lines) == 0

    def test_without_delegation_flag_pipeline_unchanged(self, team_with_data, tmp_path):
        """Without --delegation flag, Phase 1 pipeline output is byte-identical."""
        out1 = tmp_path / "out1.jsonl"
        out2 = tmp_path / "out2.jsonl"

        # Build without delegation flag twice
        rc1 = _build.main([
            "--project", "staam",
            "--team-dir", str(team_with_data),
            "--output", str(out1),
        ])
        rc2 = _build.main([
            "--project", "staam",
            "--team-dir", str(team_with_data),
            "--output", str(out2),
        ])
        assert rc1 == 0
        assert rc2 == 0
        assert out1.read_bytes() == out2.read_bytes()

    def test_delegation_missing_dir_returns_gracefully(self, team_dir, tmp_path):
        """--delegation with nonexistent delegations dir returns 0 with empty output."""
        out = tmp_path / "out.jsonl"
        rc = _build.main([
            "--project", "staam",
            "--team-dir", str(team_dir),
            "--delegation",
            "--delegations-dir", str(tmp_path / "nonexistent"),
            "--delegation-output", str(out),
        ])
        assert rc == 0


# ============================================================================
# 16.  Phase 3B — Kanban Builder CLI Wrapper Tests
# ============================================================================

def _make_kanban_db(tmp_path, board="default", extra_sql=""):
    """Create a test Kanban SQLite database."""
    db_path = str(tmp_path / f"{board}.db")
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY, title TEXT NOT NULL, status TEXT NOT NULL,
            created_at INTEGER NOT NULL, workspace_kind TEXT DEFAULT 'scratch'
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
    return db_path


BASIC_KANBAN = """
    INSERT INTO tasks VALUES ('t1','Test','running',1000,'scratch');
    INSERT INTO task_runs VALUES (1,'t1','claude','running',1000,NULL,NULL,NULL,NULL,NULL);
    INSERT INTO task_events VALUES (1,'t1',1,'created',NULL,1000);
"""


class TestKanbanCLI:
    def test_kanban_flag_empty(self, team_dir, tmp_path):
        """--kanban with no boards produces empty output."""
        out = tmp_path / "out.jsonl"
        rc = _build.main([
            "--project", "staam", "--team-dir", str(team_dir),
            "--kanban", "--kanban-boards-dir", str(tmp_path / "noboards"),
            "--kanban-output", str(out),
        ])
        assert rc == 0

    def test_kanban_flag_with_board(self, team_dir, tmp_path):
        """--kanban with a real board db."""
        board_dir = tmp_path / "testboard"
        board_dir.mkdir()
        db_path = str(board_dir / "kanban.db")
        conn = sqlite3.connect(db_path)
        conn.executescript("""
            CREATE TABLE tasks (id TEXT PRIMARY KEY, title TEXT, status TEXT, created_at INTEGER, workspace_kind TEXT DEFAULT 'scratch');
            CREATE TABLE task_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, profile TEXT, status TEXT, started_at INTEGER, ended_at INTEGER, outcome TEXT, summary TEXT, metadata TEXT, error TEXT);
            CREATE TABLE task_events (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, run_id INTEGER, kind TEXT, payload TEXT, created_at INTEGER);
            CREATE TABLE task_links (parent_id TEXT, child_id TEXT, PRIMARY KEY(parent_id, child_id));
            INSERT INTO tasks VALUES ('t1','Test','running',1000,'scratch');
            INSERT INTO task_runs VALUES (1,'t1','claude','running',1000,NULL,NULL,NULL,NULL,NULL);
            INSERT INTO task_events VALUES (1,'t1',1,'created','{}',1000);
        """)
        conn.commit(); conn.close()
        out = tmp_path / "out.jsonl"
        rc = _build.main([
            "--project", "staam", "--team-dir", str(team_dir),
            "--kanban", "--kanban-boards-dir", str(tmp_path),
            "--kanban-output", str(out),
        ])
        assert rc == 0
        assert out.exists()

    def test_kanban_does_not_affect_pipeline(self, team_with_data, tmp_path):
        """Pipeline output is unchanged when Kanban data doesn't exist."""
        out1 = tmp_path / "out1.jsonl"
        out2 = tmp_path / "out2.jsonl"
        _build.main(["--project", "staam", "--team-dir", str(team_with_data), "--output", str(out1)])
        _build.main(["--project", "staam", "--team-dir", str(team_with_data), "--output", str(out2)])
        assert out1.read_bytes() == out2.read_bytes()
