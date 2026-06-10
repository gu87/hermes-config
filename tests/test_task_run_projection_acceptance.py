"""Phase 1C end-to-end acceptance tests."""

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
_spec = importlib.util.spec_from_file_location(
    "task_run_projection_acceptance", str(SCRIPTS / "task-run-projection-acceptance.py")
)
acceptance = importlib.util.module_from_spec(_spec)
sys.modules["task_run_projection_acceptance"] = acceptance
assert _spec.loader is not None
_spec.loader.exec_module(acceptance)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _write_jsonl(path: Path, records: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")


def _complete_lifecycle_team(tmp_path: Path) -> Path:
    team = tmp_path / "staam"
    _write_json(team / "inbox" / "staam_t6.json", {
        "task_card_id": "staam_t6", "goal": "Root task", "created_at": "2026-03-07T15:00:00Z",
    })
    _write_json(team / "inbox" / "staam_t6_rev1.json", {
        "task_card_id": "staam_t6_rev1", "goal": "Revision task", "created_at": "2026-03-07T16:00:00Z",
        "revision": {"of_task_id": "staam_t6", "attempt": 1},
    })
    _write_json(team / "review" / "root_gate.json", {
        "gate_id": "root_gate", "task_id": "staam_t6", "checked_at": "2026-03-07T15:30:00Z",
        "decision": "revision_needed", "summary": "Needs revision",
    })
    _write_json(team / "review" / "revision_gate.json", {
        "gate_id": "revision_gate", "task_id": "staam_t6_rev1", "checked_at": "2026-03-07T16:30:00Z",
        "decision": "approved", "summary": "Approved",
    })
    _write_jsonl(team / "runs" / "ledger.jsonl", [
        {"event": "run_started", "run_id": "run_main", "task_id": "staam_t6", "agent_id": "claude",
         "run_type": "main", "started_at": "2026-03-07T15:05:00Z"},
        {"event": "run_finished", "run_id": "run_main", "task_id": "staam_t6", "agent_id": "claude",
         "run_type": "main", "started_at": "2026-03-07T15:05:00Z", "finished_at": "2026-03-07T15:20:00Z",
         "exit_code": 0, "classification": "ok"},
        {"event": "run_started", "run_id": "run_revision", "task_id": "staam_t6_rev1", "agent_id": "claude",
         "run_type": "revision", "started_at": "2026-03-07T16:05:00Z"},
        {"event": "run_finished", "run_id": "run_revision", "task_id": "staam_t6_rev1", "agent_id": "claude",
         "run_type": "revision", "started_at": "2026-03-07T16:05:00Z", "finished_at": "2026-03-07T16:20:00Z",
         "exit_code": 0, "classification": "ok"},
    ])
    _write_jsonl(team / "events.jsonl", [
        {"event": "gate_checked", "task_id": "staam_t6", "decision": "revision_needed",
         "timestamp": "2026-03-07T15:30:00Z"},
        {"event": "revision_created", "task_id": "staam_t6", "revision_task_id": "staam_t6_rev1", "attempt": 1,
         "timestamp": "2026-03-07T16:00:00Z"},
        {"event": "revision_dispatched", "task_id": "staam_t6", "revision_task_id": "staam_t6_rev1",
         "run_id": "run_revision", "timestamp": "2026-03-07T16:05:00Z"},
        {"event": "gate_checked", "task_id": "staam_t6_rev1", "decision": "approved",
         "timestamp": "2026-03-07T16:30:00Z"},
    ])
    return team


def test_complete_lifecycle_acceptance_passes(tmp_path):
    report = acceptance.run_acceptance("staam", _complete_lifecycle_team(tmp_path), "staam_t6")

    assert report["invariants_passed"] is True
    assert report["complete_lifecycle_covered"] is True
    assert report["byte_identical_rebuild"] is True
    assert report["mapping_error_count"] == 0


def test_incomplete_realistic_data_reports_coverage_gap(tmp_path):
    team = tmp_path / "staam"
    _write_json(team / "inbox" / "root.json", {
        "task_card_id": "root", "goal": "Root only", "created_at": "2026-03-07T15:00:00Z",
    })

    report = acceptance.run_acceptance("staam", team, "root")

    assert report["invariants_passed"] is True
    assert report["complete_lifecycle_covered"] is False


def test_real_review_run_from_ledger_is_not_invented(tmp_path):
    team = tmp_path / "staam"
    _write_jsonl(team / "runs" / "ledger.jsonl", [
        {"event": "run_started", "run_id": "review_run", "task_id": "review_task", "run_type": "review",
         "started_at": "2026-03-07T15:05:00Z"},
    ])

    report = acceptance.run_acceptance("staam", team)

    assert report["invariants_passed"] is True
    assert next(check for check in report["checks"] if check["name"] == "no_invented_runs")["passed"] is True


def test_run_without_ledger_source_is_rejected():
    report = acceptance.validate_projection("staam", [
        {"projection_type": "Run", "id": "pipeline:staam:run:fake_gate", "run_type": "gate"},
    ], ledger_run_ids=set())

    assert report["invariants_passed"] is False
    assert next(check for check in report["checks"] if check["name"] == "no_invented_runs")["passed"] is False
