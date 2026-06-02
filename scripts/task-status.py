#!/usr/bin/env python3
"""
Hermes v2.8 task status viewer.

Reads the append-only task index JSONL and shows the latest status snapshot for
each task.
"""
import argparse
import json
from pathlib import Path


TEAMS_DIR = Path.home() / ".claude" / "teams"


def load_jsonl(path):
    records = []
    path = Path(path).expanduser()
    if not path.exists():
        return records
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def index_path_from_args(args):
    if args.index:
        return Path(args.index).expanduser()
    if args.team_dir:
        return Path(args.team_dir).expanduser() / "tasks" / "index.jsonl"
    return TEAMS_DIR / args.project / "tasks" / "index.jsonl"


def run_ledger_path_from_args(args):
    if args.run_ledger:
        return Path(args.run_ledger).expanduser()
    if args.index:
        index = Path(args.index).expanduser()
        return index.parent.parent / "runs" / "ledger.jsonl"
    if args.team_dir:
        return Path(args.team_dir).expanduser() / "runs" / "ledger.jsonl"
    return TEAMS_DIR / args.project / "runs" / "ledger.jsonl"


def latest_by_task(records):
    latest = {}
    parents = {}
    for record in records:
        task_id = record.get("task_id")
        if not task_id:
            continue
        if record.get("parent_task_id"):
            parents[task_id] = record.get("parent_task_id")
        latest[task_id] = record
        revision_task_id = record.get("revision_task_id")
        if revision_task_id:
            parents[revision_task_id] = task_id
            latest[revision_task_id] = {
                **record,
                "task_id": revision_task_id,
                "parent_task_id": task_id,
            }
    for task_id, parent_task_id in parents.items():
        if task_id in latest and "parent_task_id" not in latest[task_id]:
            latest[task_id] = {
                **latest[task_id],
                "parent_task_id": parent_task_id,
            }
    return latest


def root_task_id(task_id):
    return str(task_id).split("_rev", 1)[0]


def resolve_root(task_id, parent_by_task):
    seen = set()
    current = task_id
    while current in parent_by_task and current not in seen:
        seen.add(current)
        current = parent_by_task[current]
    return current


def rollup_rows(records):
    latest = latest_by_task(records)
    parent_by_task = {
        task_id: row.get("parent_task_id")
        for task_id, row in latest.items()
        if row.get("parent_task_id")
    }
    grouped = {}
    for row in latest.values():
        task_id = row.get("task_id")
        grouped.setdefault(resolve_root(task_id, parent_by_task), []).append(row)

    rows = []
    for root_id, chain in grouped.items():
        if root_id not in latest:
            continue
        row = latest[root_id]
        chain = sorted(chain, key=lambda item: item.get("timestamp", ""))
        final = chain[-1]
        approved = [item for item in chain if item.get("status") == "approved"]
        if approved:
            final = approved[-1]
        rendered = dict(row)
        rendered["chain_status"] = final.get("status")
        rendered["chain_event"] = final.get("event")
        rendered["final_task_id"] = final.get("task_id")
        rendered["revision_count"] = max(0, len(chain) - 1)
        if final.get("task_id") != root_id:
            rendered["status"] = f"{final.get('status')} via {final.get('task_id')}"
            rendered["event"] = final.get("event")
            rendered["timestamp"] = final.get("timestamp", row.get("timestamp"))
        rows.append(rendered)
    return rows


def latest_runs_by_task(run_records):
    latest = {}
    started = {}
    for row in run_records:
        run_id = row.get("run_id")
        task_id = row.get("task_id")
        if not run_id or not task_id:
            continue
        if row.get("event") == "run_started":
            started[run_id] = row
            latest.setdefault(task_id, row)
        elif row.get("event") == "run_finished":
            latest[task_id] = {**started.get(run_id, {}), **row}
    return latest


def attach_run_info(rows, run_records):
    latest_runs = latest_runs_by_task(run_records)
    enriched = []
    for row in rows:
        run = latest_runs.get(row.get("final_task_id")) or latest_runs.get(row.get("task_id"))
        if run:
            row = {
                **row,
                "last_run_id": run.get("run_id"),
                "last_run_classification": run.get("classification") or run.get("event"),
                "last_run_duration_seconds": run.get("duration_seconds"),
                "last_run_exit_code": run.get("exit_code"),
            }
        enriched.append(row)
    return enriched


def short(text, width):
    text = "" if text is None else str(text)
    if len(text) <= width:
        return text
    return text[: max(0, width - 1)] + "..."


def print_table(records):
    rows = sorted(records, key=lambda item: item.get("timestamp", ""))
    if not rows:
        print("No task status records found.")
        return
    header = f"{'STATUS':<26} {'TASK_ID':<34} {'EVENT':<24} {'RUN':<14} {'UPDATED'}"
    print(header)
    print("-" * len(header))
    for row in rows:
        print(
            f"{short(row.get('status'), 26):<26} "
            f"{short(row.get('task_id'), 34):<34} "
            f"{short(row.get('event'), 24):<24} "
            f"{short(row.get('last_run_classification'), 14):<14} "
            f"{row.get('timestamp', '')}"
        )


def main():
    parser = argparse.ArgumentParser(description="Show Hermes v2.8 task status")
    parser.add_argument("--project", default="staam", help="Team/project name under ~/.claude/teams")
    parser.add_argument("--team-dir", help="Explicit team directory path")
    parser.add_argument("--index", help="Explicit task index JSONL path")
    parser.add_argument("--run-ledger", help="Explicit run ledger JSONL path")
    parser.add_argument("--task-id", help="Show one task only")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of a table")
    parser.add_argument(
        "--no-rollup",
        action="store_true",
        help="Show raw latest task rows instead of folding revision chains",
    )
    args = parser.parse_args()

    records = load_jsonl(index_path_from_args(args))
    rows = list(latest_by_task(records).values()) if args.no_rollup else rollup_rows(records)
    rows = attach_run_info(rows, load_jsonl(run_ledger_path_from_args(args)))
    if args.task_id:
        rows = [
            row
            for row in rows
            if row.get("task_id") == args.task_id
            or row.get("final_task_id") == args.task_id
            or root_task_id(row.get("task_id")) == root_task_id(args.task_id)
        ]
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        print_table(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
