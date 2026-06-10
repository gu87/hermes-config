#!/usr/bin/env python3
"""Phase 1C end-to-end acceptance for the Task Card Pipeline projection."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional


_ROOT = Path(__file__).resolve().parents[1]
_BUILD_PATH = _ROOT / "scripts" / "task-run-projection-build.py"
_spec = importlib.util.spec_from_file_location("task_run_projection_build", str(_BUILD_PATH))
_build = importlib.util.module_from_spec(_spec)
sys.modules["task_run_projection_build"] = _build
assert _spec.loader is not None
_spec.loader.exec_module(_build)


def _check(name: str, passed: bool, detail: str) -> Dict[str, Any]:
    return {"name": name, "passed": passed, "detail": detail}


def _records_of(records: List[Dict[str, Any]], projection_type: str) -> List[Dict[str, Any]]:
    return [record for record in records if record.get("projection_type") == projection_type]


def _ledger_run_ids(project_id: str, team_dir: Path) -> set[str]:
    ledger = team_dir / "runs" / "ledger.jsonl"
    if not ledger.is_file():
        return set()

    result = set()
    for line in ledger.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if isinstance(record, dict) and record.get("run_id"):
            result.add(f"pipeline:{project_id}:run:{record['run_id']}")
    return result


def validate_projection(
    project_id: str,
    records: List[Dict[str, Any]],
    root_source_task_id: Optional[str] = None,
    ledger_run_ids: Optional[set[str]] = None,
) -> Dict[str, Any]:
    tasks = _records_of(records, "Task")
    relations = _records_of(records, "TaskRelation")
    runs = _records_of(records, "Run")
    run_relations = _records_of(records, "RunRelation")
    events = _records_of(records, "DomainEventEnvelope")
    reviews = _records_of(records, "ReviewDecision")
    mapping_errors = _records_of(records, "MappingError")
    unsupported = _records_of(records, "UnsupportedRecord")

    checks: List[Dict[str, Any]] = []
    checks.append(_check("no_mapping_errors", not mapping_errors, f"{len(mapping_errors)} MappingError records"))
    if ledger_run_ids is not None:
        invented_runs = [run for run in runs if run.get("id") not in ledger_run_ids]
        checks.append(_check(
            "no_invented_runs",
            not invented_runs,
            f"{len(runs) - len(invented_runs)}/{len(runs)} Runs traceable to ledger run_id",
        ))
    checks.append(_check(
        "no_revision_dispatch_run_relation",
        not [relation for relation in run_relations if relation.get("relation_type") == "revision_dispatch"],
        "no RunRelation(type=revision_dispatch)",
    ))

    untraceable = [
        event for event in events
        if event.get("source") != "pipeline"
        or not event.get("source_location")
        or (not event.get("source_event_id") and "events.jsonl:" not in str(event.get("source_location")))
    ]
    checks.append(_check(
        "events_traceable",
        not untraceable,
        f"{len(events) - len(untraceable)}/{len(events)} events traceable",
    ))

    root_id = f"pipeline:{project_id}:task:{root_source_task_id}" if root_source_task_id else None
    if root_id is None:
        revision_roots = {
            task.get("root_task_id")
            for task in tasks
            if task.get("root_task_id") and task.get("root_task_id") != task.get("id")
        }
        if len(revision_roots) == 1:
            root_id = str(next(iter(revision_roots)))

    coverage_checks: List[Dict[str, Any]] = []
    if root_id is None:
        coverage_checks.append(_check("complete_lifecycle_root", False, "no revision lifecycle root found"))
    else:
        root_tasks = [task for task in tasks if task.get("id") == root_id]
        revision_tasks = [
            task for task in tasks
            if task.get("id") != root_id and task.get("root_task_id") == root_id
        ]
        revision_ids = {str(task["id"]) for task in revision_tasks}
        revision_relations = [
            relation for relation in relations
            if relation.get("relation_type") == "revision"
            and relation.get("parent_task_id") == root_id
            and relation.get("child_task_id") in revision_ids
        ]
        run_ids_by_task = {
            task_id: {str(run["id"]) for run in runs if run.get("task_id") == task_id}
            for task_id in {root_id, *revision_ids}
        }
        root_runs = run_ids_by_task.get(root_id, set())
        revision_runs = set().union(*(run_ids_by_task.get(task_id, set()) for task_id in revision_ids))
        root_reviews = [review for review in reviews if review.get("task_id") == root_id]
        revision_reviews = [review for review in reviews if review.get("task_id") in revision_ids]
        gate_events = [event for event in events if event.get("event_type") == "pipeline.gate_checked"]

        coverage_checks.extend([
            _check("root_task_present", len(root_tasks) == 1, f"{len(root_tasks)} root Task records"),
            _check("revision_task_independent", bool(revision_tasks), f"{len(revision_tasks)} revision Task records"),
            _check("revision_root_stable", all(task.get("root_task_id") == root_id for task in revision_tasks),
                   f"root_task_id={root_id}"),
            _check("revision_relation_present", bool(revision_relations), f"{len(revision_relations)} revision relations"),
            _check("dispatch_runs_independent", bool(root_runs) and bool(revision_runs) and root_runs.isdisjoint(revision_runs),
                   f"root_runs={len(root_runs)}, revision_runs={len(revision_runs)}"),
            _check("revision_needed_review_present",
                   any(review.get("decision") == "needs_revision" for review in root_reviews),
                   f"{len(root_reviews)} root review decisions"),
            _check("revision_approved_review_present",
                   any(review.get("decision") == "approve" for review in revision_reviews),
                   f"{len(revision_reviews)} revision review decisions"),
            _check("gate_events_present",
                   any(event.get("task_id") == root_id for event in gate_events)
                   and any(event.get("task_id") in revision_ids for event in gate_events),
                   f"{len(gate_events)} gate_checked events"),
            _check("gate_approved_not_accepted",
                   not any(task.get("status") == "accepted" for task in tasks if task.get("id") in {root_id, *revision_ids}),
                   "no accepted Task status projected"),
        ])

    return {
        "project_id": project_id,
        "root_task_id": root_id,
        "record_count": len(records),
        "mapping_error_count": len(mapping_errors),
        "unsupported_count": len(unsupported),
        "checks": checks,
        "coverage_checks": coverage_checks,
        "invariants_passed": all(check["passed"] for check in checks),
        "complete_lifecycle_covered": bool(coverage_checks) and all(check["passed"] for check in coverage_checks),
    }


def run_acceptance(
    project_id: str,
    team_dir: Path,
    root_source_task_id: Optional[str] = None,
) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="task-run-phase1c-") as tmp:
        first = Path(tmp) / "first.jsonl"
        second = Path(tmp) / "second.jsonl"
        _build.write_projection(_build.build_projection(project_id, team_dir), first)
        _build.write_projection(_build.build_projection(project_id, team_dir), second)
        first_bytes = first.read_bytes()
        second_bytes = second.read_bytes()
        records = [json.loads(line) for line in first_bytes.decode("utf-8").splitlines() if line.strip()]

    report = validate_projection(project_id, records, root_source_task_id, _ledger_run_ids(project_id, team_dir))
    report["byte_identical_rebuild"] = first_bytes == second_bytes
    report["sha256"] = hashlib.sha256(first_bytes).hexdigest()
    report["checks"].append(_check(
        "byte_identical_rebuild",
        report["byte_identical_rebuild"],
        "two clean builds are byte-identical",
    ))
    report["invariants_passed"] = report["invariants_passed"] and report["byte_identical_rebuild"]
    return report


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 1C Task Card Pipeline projection acceptance")
    parser.add_argument("--project", required=True)
    parser.add_argument("--team-dir", default=None)
    parser.add_argument("--root-task-id", default=None, help="Raw Pipeline root task id, for complete lifecycle checks")
    parser.add_argument("--require-complete-lifecycle", action="store_true")
    args = parser.parse_args(argv)

    team_dir = Path(args.team_dir).expanduser() if args.team_dir else Path.home() / ".claude" / "teams" / args.project
    if not team_dir.is_dir():
        print(json.dumps({"error": f"team directory not found: {team_dir}"}, ensure_ascii=False))
        return 2

    report = run_acceptance(args.project, team_dir, args.root_task_id)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    if not report["invariants_passed"]:
        return 1
    if args.require_complete_lifecycle and not report["complete_lifecycle_covered"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
