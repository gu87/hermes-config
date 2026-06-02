#!/usr/bin/env python3
"""
Hermes v2.8 default task gate runner.

Runs verify-task.py first, then review-task.py when structural verification is
not a hard failure. Produces one final approved / revision_needed / rejected
gate decision for the main agent.
"""
import argparse
import importlib.util
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


HERMES_ROOT = Path(__file__).resolve().parents[1]
TEAMS_DIR = Path.home() / ".claude" / "teams"
VERIFY_SCRIPT = HERMES_ROOT / "scripts" / "verify-task.py"
REVIEW_SCRIPT = HERMES_ROOT / "scripts" / "review-task.py"
DISPATCH_SCRIPT = HERMES_ROOT / "scripts" / "dispatch-task.py"
GATE_POLICY_SCRIPT = HERMES_ROOT / "scripts" / "gate-policy.py"
RUN_LEDGER_SCRIPT = HERMES_ROOT / "scripts" / "run-ledger.py"
HERMES_PYTHON = HERMES_ROOT / "hermes-agent" / "venv" / "bin" / "python"

DECISION_EXIT_CODES = {
    "approved": 0,
    "revision_needed": 1,
    "rejected": 2,
}

RECOVERABLE_VERIFY_ERROR_PATTERNS = (
    "task_id 不匹配",
    "缺少必填字段",
    "status=",
    "error_taxonomy",
    "outbox 包含 errors",
)


def load_json(path):
    try:
        with open(Path(path).expanduser(), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def load_run_ledger():
    spec = importlib.util.spec_from_file_location("hermes_run_ledger", RUN_LEDGER_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_json_command(command):
    completed = subprocess.run(
        command,
        cwd=str(HERMES_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    try:
        payload = json.loads(stdout) if stdout else {}
    except json.JSONDecodeError:
        payload = {}
    return {
        "command": " ".join(str(part) for part in command),
        "exit_code": completed.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "json": payload,
    }


def run_text_command(command, cwd=None):
    completed = subprocess.run(
        [str(part) for part in command],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "command": " ".join(str(part) for part in command),
        "exit_code": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def task_id_from(inbox, outbox):
    return (
        inbox.get("task_card_id")
        or inbox.get("task_id")
        or outbox.get("task_id")
        or "unknown"
    )


def decision_from_review(review_result):
    decision = review_result.get("decision") or review_result.get("gate_decision")
    if decision in DECISION_EXIT_CODES:
        return decision
    return "rejected"


def infer_team_dirs(inbox_path):
    inbox_path = Path(inbox_path).expanduser()
    inbox_dir = inbox_path.parent
    if inbox_dir.name == "inbox" and inbox_dir.parent.name:
        team_dir = inbox_dir.parent
    else:
        team_dir = inbox_dir.parent
    return {
        "team_dir": team_dir,
        "inbox_dir": inbox_dir,
        "outbox_dir": team_dir / "outbox",
        "review_dir": team_dir / "review",
    }


def git_root_for_paths(paths):
    for raw_path in paths:
        if not raw_path:
            continue
        path = Path(raw_path).expanduser()
        candidate = path if path.is_dir() else path.parent
        while candidate and not candidate.exists() and candidate != candidate.parent:
            candidate = candidate.parent
        if not candidate.exists():
            continue
        completed = subprocess.run(
            ["git", "-C", str(candidate), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode == 0 and completed.stdout.strip():
            return Path(completed.stdout.strip())
    return None


def build_commit_suggestion(inbox, outbox):
    paths = []
    for value in inbox.get("allowed_files") or []:
        paths.append(value)
    for value in outbox.get("changed_files") or []:
        paths.append(value)
    git_root = git_root_for_paths(paths)
    summary = outbox.get("summary") or inbox.get("goal") or "Hermes task update"
    suggestion = {
        "enabled": True,
        "git_root": str(git_root) if git_root else None,
        "changed_files": outbox.get("changed_files") or [],
        "summary": summary,
        "commit_message": f"chore: {str(summary).strip()[:72]}",
        "diff_stat": None,
        "diff_name_only": None,
        "note": "Suggestion only; no git staging or commit was performed.",
    }
    if git_root is None:
        suggestion["enabled"] = False
        suggestion["note"] = "No git repository found for allowed_files/changed_files."
        return suggestion

    stat = run_text_command(["git", "-C", git_root, "diff", "--stat"])
    names = run_text_command(["git", "-C", git_root, "diff", "--name-only"])
    suggestion["diff_stat"] = stat["stdout"][:4000]
    suggestion["diff_name_only"] = [line for line in names["stdout"].splitlines() if line]
    return suggestion


def revision_attempt_from(inbox):
    revision = inbox.get("revision") if isinstance(inbox.get("revision"), dict) else {}
    try:
        return int(revision.get("attempt", 0) or 0)
    except (TypeError, ValueError):
        return 0


def next_revision_id(original_task_id, attempt):
    root_id = str(original_task_id).split("_rev", 1)[0]
    return f"{root_id}_rev{attempt}"


def event_log_path_from(inbox_path):
    return infer_team_dirs(inbox_path)["team_dir"] / "events.jsonl"


def task_index_path_from_event_log(event_log_path):
    if not event_log_path:
        return None
    return Path(event_log_path).expanduser().parent / "tasks" / "index.jsonl"


def run_ledger_path_from_event_log(event_log_path):
    if not event_log_path:
        return None
    return Path(event_log_path).expanduser().parent / "runs" / "ledger.jsonl"


def _valid_project_name(value):
    if not value:
        return None
    name = str(value).strip()
    if not name or "/" in name or "\\" in name or name in {".", ".."}:
        return None
    return name


def project_from_task_card(task_card):
    has_explicit_project = task_card.get("project") is not None or task_card.get("team") is not None
    project = _valid_project_name(task_card.get("project") or task_card.get("team"))
    if project:
        return project
    context = task_card.get("context")
    if isinstance(context, dict):
        project_context = context.get("project_context")
        if isinstance(project_context, dict):
            project = _valid_project_name(project_context.get("name"))
            if project:
                return project
    output_contract = task_card.get("output_contract")
    if isinstance(output_contract, dict):
        raw_path = str(output_contract.get("path") or "")
        marker = "/.claude/teams/"
        if marker in raw_path:
            tail = raw_path.split(marker, 1)[1]
            return _valid_project_name(tail.split("/", 1)[0])
    if has_explicit_project:
        return None
    return None


def default_run_ledger_path(inbox_path, event_log_path=None):
    event_path = run_ledger_path_from_event_log(event_log_path)
    if event_path is not None:
        return event_path
    project = project_from_task_card(load_json(inbox_path))
    if project:
        return TEAMS_DIR / project / "runs" / "ledger.jsonl"
    return infer_team_dirs(inbox_path)["team_dir"] / "runs" / "ledger.jsonl"


def gate_command(
    inbox_path,
    outbox_path,
    review_record_path,
    event_log_path=None,
    task_index_path=None,
):
    event_arg = f"--event-log {event_log_path} " if event_log_path else ""
    index_arg = f"--task-index {task_index_path} " if task_index_path else ""
    return (
        f"{HERMES_PYTHON} {Path(__file__).resolve()} "
        f"--inbox {inbox_path} "
        f"--outbox {outbox_path} "
        f"--output {review_record_path} "
        f"{event_arg}"
        f"{index_arg}"
        "--summary "
        "--create-revision-inbox"
    )


def dispatch_command(inbox_path):
    return f"{HERMES_PYTHON} {DISPATCH_SCRIPT} --inbox {inbox_path}"


def append_event(event_log_path, event, **fields):
    if not event_log_path:
        return
    path = Path(event_log_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **fields,
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def status_from_event(event, fields):
    if event == "gate_checked":
        decision = fields.get("decision")
        if decision == "approved":
            return "approved"
        if decision == "rejected":
            return "rejected"
        if decision == "revision_needed":
            return "revision_needed"
        return "gate_checked"
    if event == "revision_created":
        return "revision_created"
    if event == "revision_dispatched":
        return "revision_dispatched"
    if event == "revision_dispatch_timeout":
        return "revision_dispatch_timeout"
    if event == "revision_dispatch_skipped":
        return "revision_dispatch_skipped"
    if event == "revision_policy_blocked":
        return "manual_review"
    if event == "revision_limit_reached":
        return "needs_human_review"
    return event


def append_task_index(task_index_path, event, **fields):
    if not task_index_path:
        return
    path = Path(task_index_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "status": status_from_event(event, fields),
        **fields,
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def record_event(event_log_path, task_index_path, event, **fields):
    append_event(event_log_path, event, **fields)
    append_task_index(task_index_path, event, **fields)


def record_lifecycle(run_ledger_path, task_id, phase, status="completed", **fields):
    if not run_ledger_path or not task_id:
        return
    try:
        ledger = load_run_ledger()
        ledger.append_lifecycle_event(
            run_ledger_path,
            task_id=task_id,
            phase=phase,
            status=status,
            agent_id=fields.pop("agent_id", "codex"),
            run_type=fields.pop("run_type", phase),
            message=fields.pop("message", None),
            **fields,
        )
    except Exception:
        return


def build_revision_inbox(inbox, outbox, record, inbox_path, outbox_path, review_path, max_revisions):
    current_attempt = revision_attempt_from(inbox)
    next_attempt = current_attempt + 1
    if next_attempt > max_revisions:
        return None, {
            "reason": f"revision limit reached ({current_attempt}/{max_revisions})",
            "max_revisions": max_revisions,
        }

    task_id = task_id_from(inbox, outbox)
    revision_task_id = next_revision_id(task_id, next_attempt)
    dirs = infer_team_dirs(inbox_path)
    revision_inbox_path = dirs["inbox_dir"] / f"{revision_task_id}.json"
    revision_outbox_path = dirs["outbox_dir"] / f"{revision_task_id}_result.json"
    revision_review_path = dirs["review_dir"] / f"{revision_task_id}_gate.json"
    revision_event_log_path = dirs["team_dir"] / "events.jsonl"
    revision_task_index_path = dirs["team_dir"] / "tasks" / "index.jsonl"

    instructions = (record.get("review") or {}).get("revision_instructions") or []
    now = datetime.now(timezone.utc).isoformat()
    revision_inbox = dict(inbox)
    revision_inbox["task_card_id"] = revision_task_id
    if "task_id" in revision_inbox:
        revision_inbox["task_id"] = revision_task_id
    revision_inbox["created_at"] = now
    revision_inbox["status"] = "created"
    revision_inbox["goal"] = (
        "修复上一轮 Review Gate 指出的返工问题，并重新提交合规 outbox。"
    )
    revision_inbox["revision"] = {
        "of_task_id": task_id,
        "attempt": next_attempt,
        "max_revisions": max_revisions,
        "previous_inbox_path": str(Path(inbox_path).expanduser()),
        "previous_outbox_path": str(Path(outbox_path).expanduser()),
        "previous_gate_record_path": str(Path(review_path).expanduser()) if review_path else None,
        "previous_gate_id": record.get("gate_id"),
        "instructions": instructions,
    }
    revision_inbox["output_contract"] = {
        "path": str(revision_outbox_path),
        "format": "json",
        "schema": "templates/outbox_v2_8.json",
        "dispatch": {
            "required": True,
            "runner": str(DISPATCH_SCRIPT),
            "command": dispatch_command(revision_inbox_path),
        },
        "post_outbox_gate": {
            "required": True,
            "runner": str(Path(__file__).resolve()),
            "record_path": str(revision_review_path),
            "command": gate_command(
                revision_inbox_path,
                revision_outbox_path,
                revision_review_path,
                revision_event_log_path,
                revision_task_index_path,
            ),
            "decisions": ["approved", "revision_needed", "rejected"],
        },
    }
    revision_inbox["revision_brief"] = {
        "source_decision": record.get("decision"),
        "source_summary": record.get("summary"),
        "instructions": instructions,
        "required_behavior": [
            "只修复 revision instructions 指出的具体问题。",
            "保持 allowed_files 范围不变；需要新增文件时先在 outbox notes 说明。",
            "重新运行必要验证，并在 evidence 中写明命令和结果摘要。",
            "输出新的 v2.8 outbox，不要覆盖上一轮 outbox。",
        ],
    }
    return revision_inbox_path, revision_inbox


def write_revision_inbox(inbox_path, revision_inbox):
    inbox_path.parent.mkdir(parents=True, exist_ok=True)
    with open(inbox_path, "w", encoding="utf-8") as f:
        json.dump(revision_inbox, f, indent=2, ensure_ascii=False)


def build_failure_record(inbox, outbox, verify_run, reason):
    task_id = task_id_from(inbox, outbox)
    verify_json = verify_run.get("json", {}) or {}
    errors = verify_json.get("errors") or []
    recoverable = any(
        any(pattern in str(error) for pattern in RECOVERABLE_VERIFY_ERROR_PATTERNS)
        for error in errors
    )
    decision = "revision_needed" if recoverable else "rejected"
    return {
        "schema_version": "2.8",
        "gate_id": f"{task_id}_gate_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
        "task_id": task_id,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "gate_decision": decision,
        "status": "failed",
        "verify_result": verify_run.get("json", {}).get("result", "fail"),
        "review_decision": None,
        "summary": reason,
        "ready_for_user": False,
        "verify": {
            "exit_code": verify_run.get("exit_code"),
            "summary": verify_run.get("json", {}).get("summary") or verify_run.get("stdout") or verify_run.get("stderr"),
        },
        "review": {
            "exit_code": None,
            "semantic_checks_passed": 0,
            "semantic_checks_total": 1,
            "revision_instructions": [
                f"修复 verify-task.py 报错: {error}" for error in errors
            ] or [reason],
            "failed_checks": [
                {
                    "check": "invalid_output_schema",
                    "passed": False,
                    "detail": error,
                }
                for error in errors
            ],
        } if recoverable else None,
        "errors": [reason, *errors],
        "error_taxonomy": [
            {
                "code": "invalid_output_schema" if recoverable else "verification_failed",
                "message": reason,
                "recoverable": recoverable,
            }
        ],
        "known_risks": [],
        "needs_human_review": True,
    }


def run_gate(inbox_path, outbox_path):
    inbox = load_json(inbox_path)
    outbox = load_json(outbox_path)
    task_id = task_id_from(inbox, outbox)

    verify_command = [
        sys.executable,
        str(VERIFY_SCRIPT),
        "--inbox",
        str(inbox_path),
        "--outbox",
        str(outbox_path),
    ]
    verify_run = run_json_command(verify_command)
    verify_result = verify_run["json"]
    verify_status = verify_result.get("result", "fail")

    if verify_run["exit_code"] == 1 or verify_status == "fail":
        return build_failure_record(
            inbox,
            outbox,
            verify_run,
            "verify-task.py returned fail; review-task.py was skipped.",
        )

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as tmp:
        json.dump(verify_result, tmp, ensure_ascii=False, indent=2)
        verify_result_path = tmp.name

    review_command = [
        sys.executable,
        str(REVIEW_SCRIPT),
        "--inbox",
        str(inbox_path),
        "--outbox",
        str(outbox_path),
        "--verify-result",
        verify_result_path,
    ]
    review_run = run_json_command(review_command)
    review_result = review_run["json"]
    decision = decision_from_review(review_result)

    status = "completed" if decision == "approved" else "failed"
    record = {
        "schema_version": "2.8",
        "gate_id": f"{task_id}_gate_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
        "task_id": task_id,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "gate_decision": decision,
        "status": status,
        "verify_result": verify_status,
        "review_decision": decision,
        "summary": review_result.get("verdict_summary") or f"{decision}: gate completed",
        "ready_for_user": decision == "approved",
        "verify": {
            "exit_code": verify_run["exit_code"],
            "summary": verify_result.get("summary"),
            "checks": verify_result.get("checks", []),
        },
        "review": {
            "exit_code": review_run["exit_code"],
            "semantic_checks_passed": review_result.get("semantic_checks_passed"),
            "semantic_checks_total": review_result.get("semantic_checks_total"),
            "revision_instructions": review_result.get("revision_instructions", []),
            "failed_checks": [
                check
                for check in review_result.get("semantic_checks", [])
                if not check.get("passed")
            ],
        },
        "errors": [],
        "error_taxonomy": [],
        "known_risks": [],
        "needs_human_review": decision != "approved",
    }
    if decision == "approved":
        record["commit_suggestion"] = build_commit_suggestion(inbox, outbox)
    return record


def apply_gate_policy(record):
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as tmp:
        json.dump(record, tmp, ensure_ascii=False, indent=2)
        record_path = tmp.name
    policy_run = run_json_command([
        sys.executable,
        str(GATE_POLICY_SCRIPT),
        "--gate-record",
        record_path,
        "--policy",
        str(HERMES_ROOT / "templates" / "gate_policy_v2_8.json"),
    ])
    policy = policy_run.get("json") or {}
    if not policy:
        policy = {
            "schema_version": "2.8",
            "policy_action": "manual_review",
            "policy_reason": policy_run.get("stderr") or "gate policy did not return JSON",
            "auto_revision_allowed": False,
            "auto_dispatch_allowed": False,
        }
    return policy


def format_summary(record):
    lines = [
        f"DECISION: {record['decision']}",
        f"TASK_ID: {record['task_id']}",
        f"VERIFY_RESULT: {record['verify_result']}",
        f"READY_FOR_USER: {str(record['ready_for_user']).lower()}",
        f"SUMMARY: {record['summary']}",
    ]
    policy = record.get("policy") or {}
    if policy:
        lines.append(f"POLICY_ACTION: {policy.get('policy_action')}")
        lines.append(f"POLICY_REASON: {policy.get('policy_reason')}")
    revision = (record.get("review") or {}).get("revision_instructions") or []
    if revision:
        lines.append("REVISION_INSTRUCTIONS:")
        lines.extend(f"- {item}" for item in revision)
    if record.get("errors"):
        lines.append("ERRORS:")
        lines.extend(f"- {item}" for item in record["errors"])
    suggestion = record.get("commit_suggestion") or {}
    if suggestion:
        lines.append(f"COMMIT_SUGGESTION: {suggestion.get('commit_message')}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Hermes v2.8 verify + review gate runner")
    parser.add_argument("--inbox", required=True, help="Inbox task card JSON path")
    parser.add_argument("--outbox", required=True, help="Child-agent outbox JSON path")
    parser.add_argument("--output", help="Optional path to write the gate review record JSON")
    parser.add_argument("--event-log", help="Optional JSONL path for gate lifecycle events")
    parser.add_argument("--task-index", help="Optional JSONL path for task status snapshots")
    parser.add_argument("--run-ledger", help="Optional JSONL path for external run ledger")
    parser.add_argument(
        "--create-revision-inbox",
        action="store_true",
        help="When decision=revision_needed, write the next revision inbox task card",
    )
    parser.add_argument(
        "--auto-dispatch-revision",
        action="store_true",
        help="After creating a revision inbox, immediately run dispatch-task.py for it",
    )
    parser.add_argument(
        "--dispatch-timeout",
        type=float,
        default=600.0,
        help="Seconds to wait for auto-dispatch before marking it failed",
    )
    parser.add_argument(
        "--max-revisions",
        type=int,
        default=2,
        help="Maximum automatic revision inboxes per original task",
    )
    parser.add_argument("--summary", action="store_true", help="Print compact text summary")
    args = parser.parse_args()

    record = run_gate(args.inbox, args.outbox)
    record["policy"] = apply_gate_policy(record)
    task_index_path = args.task_index or task_index_path_from_event_log(args.event_log)
    run_ledger_path = args.run_ledger or default_run_ledger_path(args.inbox, args.event_log)
    record_lifecycle(
        run_ledger_path,
        record.get("task_id"),
        "gate_checked",
        status=record.get("decision") or "unknown",
        decision=record.get("decision"),
        policy_action=record.get("policy", {}).get("policy_action"),
        inbox_path=str(Path(args.inbox).expanduser()),
        outbox_path=str(Path(args.outbox).expanduser()),
        gate_record_path=str(Path(args.output).expanduser()) if args.output else None,
        message=record.get("summary"),
    )
    record_event(
        args.event_log,
        task_index_path,
        "gate_checked",
        task_id=record.get("task_id"),
        decision=record.get("decision"),
        policy_action=record.get("policy", {}).get("policy_action"),
        inbox_path=str(Path(args.inbox).expanduser()),
        outbox_path=str(Path(args.outbox).expanduser()),
        gate_record_path=str(Path(args.output).expanduser()) if args.output else None,
    )
    policy = record.get("policy") or {}
    if (
        args.create_revision_inbox
        and record.get("decision") == "revision_needed"
        and policy.get("auto_revision_allowed") is True
    ):
        inbox = load_json(args.inbox)
        outbox = load_json(args.outbox)
        revision_path, revision_payload = build_revision_inbox(
            inbox,
            outbox,
            record,
            args.inbox,
            args.outbox,
            args.output,
            max(0, args.max_revisions),
        )
        if revision_path is not None:
            write_revision_inbox(revision_path, revision_payload)
            record["revision_task"] = {
                "created": True,
                "inbox_path": str(revision_path),
                "task_id": revision_payload.get("task_card_id") or revision_payload.get("task_id"),
                "attempt": revision_payload.get("revision", {}).get("attempt"),
            }
            record_event(
                args.event_log,
                task_index_path,
                "revision_created",
                task_id=record.get("task_id"),
                revision_task_id=record["revision_task"]["task_id"],
                revision_inbox_path=str(revision_path),
                attempt=record["revision_task"]["attempt"],
            )
            record_lifecycle(
                run_ledger_path,
                record.get("task_id"),
                "revision_created",
                status="created",
                revision_task_id=record["revision_task"]["task_id"],
                revision_inbox_path=str(revision_path),
                attempt=record["revision_task"]["attempt"],
                message="Revision inbox created",
            )
            if args.auto_dispatch_revision and policy.get("auto_dispatch_allowed") is True:
                dispatch_command_list = [
                    sys.executable,
                    str(DISPATCH_SCRIPT),
                    "--inbox",
                    str(revision_path),
                    "--timeout",
                    str(max(1.0, args.dispatch_timeout)),
                ]
                if run_ledger_path:
                    dispatch_command_list.extend(["--run-ledger", str(run_ledger_path)])
                ledger = load_run_ledger()
                run_result = ledger.run_with_ledger(
                    dispatch_command_list,
                    ledger_path=run_ledger_path,
                    task_id=record["revision_task"]["task_id"],
                    agent_id=(load_json(revision_path).get("execution_plan") or {}).get("primary_agent"),
                    run_type="revision_dispatch",
                    timeout=max(1.0, args.dispatch_timeout + 5),
                )
                record["revision_dispatch"] = {
                    "attempted": True,
                    "run_id": run_result["run_id"],
                    "exit_code": run_result["exit_code"],
                    "classification": run_result["classification"],
                    "duration_seconds": run_result["duration_seconds"],
                    "command": " ".join(str(part) for part in dispatch_command_list),
                    "stdout": str(run_result.get("stdout") or "").strip()[:2000],
                    "stderr": str(run_result.get("stderr") or "").strip()[:2000],
                }
                event_name = "revision_dispatch_timeout" if run_result.get("timed_out") else "revision_dispatched"
                record_event(
                    args.event_log,
                    task_index_path,
                    event_name,
                    task_id=record.get("task_id"),
                    revision_task_id=record["revision_task"]["task_id"],
                    run_id=run_result["run_id"],
                    exit_code=run_result["exit_code"],
                    classification=run_result["classification"],
                    duration_seconds=run_result["duration_seconds"],
                )
                record_lifecycle(
                    run_ledger_path,
                    record.get("task_id"),
                    event_name,
                    status=run_result["classification"],
                    revision_task_id=record["revision_task"]["task_id"],
                    run_id=run_result["run_id"],
                    exit_code=run_result["exit_code"],
                    classification=run_result["classification"],
                    duration_seconds=run_result["duration_seconds"],
                    message="Revision dispatch completed",
                )
            elif args.auto_dispatch_revision:
                record["revision_dispatch"] = {
                    "attempted": False,
                    "reason": policy.get("policy_reason") or "policy disallowed auto dispatch",
                }
                record_event(
                    args.event_log,
                    task_index_path,
                    "revision_dispatch_skipped",
                    task_id=record.get("task_id"),
                    revision_task_id=record["revision_task"]["task_id"],
                    reason=record["revision_dispatch"]["reason"],
                )
                record_lifecycle(
                    run_ledger_path,
                    record.get("task_id"),
                    "revision_dispatch_skipped",
                    status="skipped",
                    revision_task_id=record["revision_task"]["task_id"],
                    reason=record["revision_dispatch"]["reason"],
                    message="Revision dispatch skipped",
                )
        else:
            record["revision_task"] = {
                "created": False,
                **revision_payload,
            }
            record_event(
                args.event_log,
                task_index_path,
                "revision_limit_reached",
                task_id=record.get("task_id"),
                max_revisions=revision_payload.get("max_revisions"),
                reason=revision_payload.get("reason"),
            )
            record_lifecycle(
                run_ledger_path,
                record.get("task_id"),
                "revision_limit_reached",
                status="blocked",
                max_revisions=revision_payload.get("max_revisions"),
                reason=revision_payload.get("reason"),
                message="Revision limit reached",
            )
    elif args.create_revision_inbox and record.get("decision") == "revision_needed":
        record["revision_task"] = {
            "created": False,
            "reason": policy.get("policy_reason") or "policy disallowed auto revision",
            "policy_action": policy.get("policy_action"),
        }
        record_event(
            args.event_log,
            task_index_path,
            "revision_policy_blocked",
            task_id=record.get("task_id"),
            policy_action=policy.get("policy_action"),
            reason=record["revision_task"]["reason"],
        )
        record_lifecycle(
            run_ledger_path,
            record.get("task_id"),
            "revision_policy_blocked",
            status="blocked",
            policy_action=policy.get("policy_action"),
            reason=record["revision_task"]["reason"],
            message="Revision policy blocked automatic revision",
        )
    if args.output:
        output_path = Path(args.output).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2, ensure_ascii=False)
    if args.summary:
        print(format_summary(record))
    else:
        print(json.dumps(record, indent=2, ensure_ascii=False))
    sys.exit(DECISION_EXIT_CODES.get(record["decision"], 2))


if __name__ == "__main__":
    main()
