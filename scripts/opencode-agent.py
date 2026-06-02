#!/usr/bin/env python3
"""
Hermes OpenCode adapter.

Runs OpenCode on a narrow, structured task and records both the raw process run
and the collaboration-quality verdict in the Hermes run ledger.
"""
import argparse
import importlib.util
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path


HERMES_ROOT = Path(__file__).resolve().parents[1]
RUN_LEDGER_SCRIPT = HERMES_ROOT / "scripts" / "run-ledger.py"
TEAMS_DIR = Path.home() / ".claude" / "teams"
DEFAULT_TIMEOUT = float(os.environ.get("HERMES_OPENCODE_TIMEOUT", "120"))
DEFAULT_MAX_CONTEXT_CHARS = int(os.environ.get("HERMES_OPENCODE_MAX_CONTEXT_CHARS", "5000"))
DEFAULT_MODEL = os.environ.get("HERMES_OPENCODE_MODEL", "opencode/deepseek-v4-flash-free")
DEFAULT_AGENT = os.environ.get("HERMES_OPENCODE_AGENT", "build")


FINDING_RE = re.compile(
    r"^\s*-\s+[^:\n]+:\d+\s+\|\s+severity=P[0-3]\s+\|\s+issue=.+\|\s+fix=.+$",
    re.MULTILINE,
)


def load_run_ledger():
    spec = importlib.util.spec_from_file_location("hermes_run_ledger", RUN_LEDGER_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ledger_path_from_args(args):
    if args.run_ledger:
        return Path(args.run_ledger).expanduser()
    if args.team_dir:
        return Path(args.team_dir).expanduser() / "runs" / "ledger.jsonl"
    return TEAMS_DIR / args.project / "runs" / "ledger.jsonl"


def run_text(command, cwd):
    completed = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return ""
    return completed.stdout


def truncate_middle(text, max_chars):
    if len(text) <= max_chars:
        return text
    keep_head = max_chars // 2
    keep_tail = max_chars - keep_head
    omitted = len(text) - max_chars
    return (
        text[:keep_head]
        + f"\n\n[... truncated {omitted} chars by opencode-agent ...]\n\n"
        + text[-keep_tail:]
    )


def collect_git_diff(files, cwd, max_chars):
    command = ["git", "diff", "--"]
    command.extend(str(path) for path in files)
    diff = run_text(command, cwd)
    if diff.strip():
        return truncate_middle(diff.strip(), max_chars)
    snapshots = []
    for raw_path in files:
        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            path = Path(cwd) / path
        try:
            if path.is_file():
                content = path.read_text(encoding="utf-8", errors="replace")
                snapshots.append(f"--- file snapshot: {raw_path} ---\n{content}")
        except OSError as exc:
            snapshots.append(f"--- file snapshot unavailable: {raw_path} ({exc}) ---")
    return truncate_middle("\n\n".join(snapshots).strip(), max_chars)


def build_prompt(*, task_id, role, files, task, diff_text, max_context_chars):
    file_lines = "\n".join(f"- {path}" for path in files) if files else "- (none supplied)"
    diff_block = truncate_middle(diff_text.strip(), max_context_chars)
    if not diff_block:
        diff_block = "(no git diff content was available; review only the stated task and files)"
    return f"""Role: {role}
Task ID: {task_id}
Task: {task}

You are one member of a Hermes multi-agent collaboration chain.
Your job is narrow: review the supplied diff for concrete bugs only.

Scope:
- correctness bugs
- safety regressions
- missing verification that would hide a bug
- process/timeout/failure-handling mistakes

Ignore:
- broad architecture advice
- style preferences
- unrelated refactors
- generic praise

Changed files:
{file_lines}

Output contract:
Return exactly one of these forms.

If there are no concrete findings:
NO_FINDINGS

If there are findings:
FINDINGS:
- file:line | severity=P0 | issue=<concrete bug> | fix=<specific fix>
- file:line | severity=P1 | issue=<concrete bug> | fix=<specific fix>

Rules:
- Every finding must include a real file path and line number.
- Severity must be one of P0, P1, P2, P3.
- Do not use markdown fences.
- Do not include chain-of-thought.
- Do not report suggestions without a concrete bug.

Diff:
{diff_block}
"""


def build_command(args, prompt):
    command = [args.opencode_bin, "run"]
    if args.model:
        command.extend(["--model", args.model])
    if args.agent:
        command.extend(["--agent", args.agent])
    if args.pure:
        command.append("--pure")
    command.extend(["--title", f"Hermes OpenCode {args.role} {args.task_id}", prompt])
    return command


def ledger_command(command, prompt):
    return [*command[:-1], f"<prompt redacted: {len(prompt)} chars>"]


def classify_opencode_result(result):
    if result.get("timed_out"):
        return "timeout", "OpenCode exceeded the configured timeout."
    if result.get("exit_code") not in (0, None):
        return "failed", "OpenCode process exited non-zero."
    stdout = str(result.get("stdout") or "").strip()
    if any(line.strip() == "NO_FINDINGS" for line in stdout.splitlines()):
        return "no_findings", "OpenCode returned the required NO_FINDINGS marker."
    if FINDING_RE.search(stdout):
        return "ok", "OpenCode returned structured findings."
    return "ineffective", "OpenCode output did not match the required review contract."


def append_quality_verdict(ledger, ledger_path, *, task_id, role, result, verdict, message):
    ledger.append_lifecycle_event(
        ledger_path,
        task_id=task_id,
        phase="opencode_result_evaluated",
        status=verdict,
        agent_id="opencode",
        run_type=f"opencode_{role}",
        message=message,
        run_id=result.get("run_id"),
        exit_code=result.get("exit_code"),
        duration_seconds=result.get("duration_seconds"),
        timed_out=bool(result.get("timed_out")),
    )


def process_text(value):
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def exit_code_for(verdict, result):
    if verdict == "timeout":
        return 124
    if verdict == "failed":
        return result.get("exit_code") if result.get("exit_code") is not None else 1
    if verdict == "ineffective":
        return 2
    return 0


def main():
    parser = argparse.ArgumentParser(description="Run OpenCode as a narrow Hermes collaboration agent")
    parser.add_argument("--task-id", required=True, help="Task/run identifier for Run Ledger")
    parser.add_argument("--task", required=True, help="Narrow task instruction for OpenCode")
    parser.add_argument("--role", default="reviewer", help="OpenCode role label")
    parser.add_argument("--file", action="append", default=[], dest="files", help="Changed file to include in scope")
    parser.add_argument("--cwd", default=".", help="Workspace directory for git diff and OpenCode")
    parser.add_argument("--run-ledger", help="Explicit run ledger JSONL path")
    parser.add_argument("--team-dir", help="Explicit team directory path")
    parser.add_argument("--project", default="staam", help="Team/project name under ~/.claude/teams")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="Seconds before timeout")
    parser.add_argument("--max-context-chars", type=int, default=DEFAULT_MAX_CONTEXT_CHARS)
    parser.add_argument("--opencode-bin", default=os.environ.get("OPENCODE_BIN", "opencode"))
    parser.add_argument("--model", default=DEFAULT_MODEL, help="OpenCode model, provider/model")
    parser.add_argument("--agent", default=DEFAULT_AGENT, help="OpenCode agent")
    parser.add_argument("--pure", action="store_true", help="Run OpenCode without external plugins")
    parser.add_argument("--dry-run", action="store_true", help="Print the command and prompt without running")
    args = parser.parse_args()

    cwd = Path(args.cwd).expanduser().resolve()
    diff_text = collect_git_diff(args.files, cwd, args.max_context_chars)
    prompt = build_prompt(
        task_id=args.task_id,
        role=args.role,
        files=args.files,
        task=args.task,
        diff_text=diff_text,
        max_context_chars=args.max_context_chars,
    )
    command = build_command(args, prompt)
    if args.dry_run:
        print(" ".join(shlex.quote(part) for part in command))
        return 0

    ledger = load_run_ledger()
    ledger_path = ledger_path_from_args(args)
    result = ledger.run_with_ledger(
        command,
        ledger_path=ledger_path,
        task_id=args.task_id,
        agent_id="opencode",
        run_type=f"opencode_{args.role}",
        cwd=cwd,
        timeout=max(1.0, args.timeout),
        command_for_record=ledger_command(command, prompt),
    )
    verdict, message = classify_opencode_result(result)
    append_quality_verdict(
        ledger,
        ledger_path,
        task_id=args.task_id,
        role=args.role,
        result=result,
        verdict=verdict,
        message=message,
    )
    stdout = process_text(result.get("stdout"))
    stderr = process_text(result.get("stderr"))
    if stdout:
        print(stdout, end="" if stdout.endswith("\n") else "\n")
    if stderr:
        print(stderr, file=sys.stderr, end="" if stderr.endswith("\n") else "\n")
    print(f"OPENCODE_VERDICT: {verdict}", file=sys.stderr)
    return exit_code_for(verdict, result)


if __name__ == "__main__":
    raise SystemExit(main())
