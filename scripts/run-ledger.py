#!/usr/bin/env python3
"""
Hermes v2.8 run ledger.

Append-only JSONL records for external agent/process executions. This is the
watchdog surface used by dispatch and gate revision dispatch.
"""
import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


TEAMS_DIR = Path.home() / ".claude" / "teams"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def short_id(prefix):
    return f"{prefix}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"


def append_jsonl(path, payload):
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def append_lifecycle_event(
    ledger_path,
    *,
    task_id,
    phase,
    status="completed",
    agent_id=None,
    run_type=None,
    message=None,
    **fields,
):
    timestamp = utc_now()
    event_id = short_id(f"life_{task_id}")
    if "run_id" in fields:
        fields["related_run_id"] = fields.pop("run_id")
    append_jsonl(
        ledger_path,
        {
            "schema_version": "2.8",
            "event": "lifecycle_event",
            "event_id": event_id,
            "run_id": event_id,
            "task_id": task_id,
            "agent_id": agent_id,
            "run_type": run_type or phase,
            "phase": phase,
            "status": status,
            "message": message,
            "started_at": timestamp,
            "finished_at": timestamp,
            **fields,
        },
    )
    return event_id


def load_jsonl(path):
    path = Path(path).expanduser()
    if not path.exists():
        return []
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def ledger_path_from_args(args):
    if args.ledger:
        return Path(args.ledger).expanduser()
    if args.team_dir:
        return Path(args.team_dir).expanduser() / "runs" / "ledger.jsonl"
    return TEAMS_DIR / args.project / "runs" / "ledger.jsonl"


def classify_exit(exit_code, timed_out=False, stderr=""):
    if timed_out:
        return "timeout"
    if exit_code == 0:
        return "ok"
    text = stderr.lower()
    if "permission" in text or "denied" in text:
        return "permission_error"
    if "api key" in text or "auth" in text or "unauthorized" in text:
        return "auth_error"
    if "rate limit" in text or "quota" in text:
        return "rate_limited"
    return "process_error"


def run_with_ledger(
    command,
    *,
    ledger_path,
    task_id,
    agent_id=None,
    run_type="process",
    cwd=None,
    timeout=None,
    command_for_record=None,
):
    run_id = short_id(f"run_{task_id}")
    start = time.monotonic()
    started_at = utc_now()
    recorded_command = command_for_record if command_for_record is not None else command
    command_text = " ".join(str(part) for part in recorded_command)
    append_jsonl(
        ledger_path,
        {
            "schema_version": "2.8",
            "event": "run_started",
            "run_id": run_id,
            "task_id": task_id,
            "agent_id": agent_id,
            "run_type": run_type,
            "started_at": started_at,
            "command": command_text,
            "cwd": str(cwd) if cwd else None,
            "timeout_seconds": timeout,
        },
    )
    try:
        completed = subprocess.run(
            [str(part) for part in command],
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        duration = round(time.monotonic() - start, 3)
        classification = classify_exit(completed.returncode, stderr=completed.stderr)
        append_jsonl(
            ledger_path,
            {
                "schema_version": "2.8",
                "event": "run_finished",
                "run_id": run_id,
                "task_id": task_id,
                "agent_id": agent_id,
                "run_type": run_type,
                "started_at": started_at,
                "finished_at": utc_now(),
                "duration_seconds": duration,
                "exit_code": completed.returncode,
                "classification": classification,
                "stdout_tail": completed.stdout.strip()[-2000:],
                "stderr_tail": completed.stderr.strip()[-2000:],
            },
        )
        return {
            "run_id": run_id,
            "exit_code": completed.returncode,
            "classification": classification,
            "duration_seconds": duration,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        duration = round(time.monotonic() - start, 3)
        append_jsonl(
            ledger_path,
            {
                "schema_version": "2.8",
                "event": "run_finished",
                "run_id": run_id,
                "task_id": task_id,
                "agent_id": agent_id,
                "run_type": run_type,
                "started_at": started_at,
                "finished_at": utc_now(),
                "duration_seconds": duration,
                "exit_code": None,
                "classification": "timeout",
                "timeout_seconds": timeout,
                "stdout_tail": (exc.stdout or "").strip()[-2000:] if isinstance(exc.stdout, str) else "",
                "stderr_tail": (exc.stderr or "").strip()[-2000:] if isinstance(exc.stderr, str) else "",
            },
        )
        return {
            "run_id": run_id,
            "exit_code": None,
            "classification": "timeout",
            "duration_seconds": duration,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "timed_out": True,
        }


def latest_finished(records):
    latest = {}
    starts = {}
    for row in records:
        run_id = row.get("run_id")
        if not run_id:
            continue
        if row.get("event") == "run_started":
            starts[run_id] = row
            latest.setdefault(run_id, row)
        elif row.get("event") == "run_finished":
            merged = {**starts.get(run_id, {}), **row}
            latest[run_id] = merged
    return list(latest.values())


def short(text, width):
    text = "" if text is None else str(text)
    if len(text) <= width:
        return text
    return text[: max(0, width - 1)] + "..."


def print_table(rows, limit):
    rows = sorted(rows, key=lambda item: item.get("started_at", ""))
    if limit:
        rows = rows[-limit:]
    if not rows:
        print("No run records found.")
        return
    header = f"{'CLASS':<18} {'RUN_ID':<38} {'TASK':<30} {'AGENT':<14} {'DUR':<8} {'EXIT'}"
    print(header)
    print("-" * len(header))
    for row in rows:
        print(
            f"{short(row.get('classification') or row.get('event'), 18):<18} "
            f"{short(row.get('run_id'), 38):<38} "
            f"{short(row.get('task_id'), 30):<30} "
            f"{short(row.get('agent_id'), 14):<14} "
            f"{short(row.get('duration_seconds'), 8):<8} "
            f"{row.get('exit_code')}"
        )


def main():
    parser = argparse.ArgumentParser(description="Show Hermes run ledger")
    parser.add_argument("--project", default="staam", help="Team/project name under ~/.claude/teams")
    parser.add_argument("--team-dir", help="Explicit team directory path")
    parser.add_argument("--ledger", help="Explicit run ledger JSONL path")
    parser.add_argument("--task-id", help="Show one task only")
    parser.add_argument("--limit", type=int, default=30, help="Number of latest runs to show; 0 means all")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of table")
    args = parser.parse_args()

    rows = latest_finished(load_jsonl(ledger_path_from_args(args)))
    if args.task_id:
        rows = [row for row in rows if row.get("task_id") == args.task_id]
    if args.json:
        selected = sorted(rows, key=lambda item: item.get("started_at", ""))
        print(json.dumps(selected[-args.limit:] if args.limit else selected, ensure_ascii=False, indent=2))
    else:
        print_table(rows, args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
