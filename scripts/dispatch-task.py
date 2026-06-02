#!/usr/bin/env python3
"""
Hermes v2.8 Task Card dispatcher.

Reads a v2.8 inbox task card and asks the live Hermes runtime to delegate it to
the selected named agent via delegate_task(agent_id=...).
"""
import argparse
import json
import os
import shlex
import subprocess
import sys
import importlib.util
from pathlib import Path


HERMES_ROOT = Path(__file__).resolve().parents[1]
TEAMS_DIR = Path.home() / ".claude" / "teams"
DEFAULT_HERMES_BIN = HERMES_ROOT / "hermes-agent" / "venv" / "bin" / "hermes"
HERMES_BIN = os.environ.get(
    "HERMES_BIN",
    str(DEFAULT_HERMES_BIN) if DEFAULT_HERMES_BIN.exists() else "hermes",
)
DEFAULT_SKILLS = "hermes-subagent-delegation,verification-loop"
DEFAULT_TOOLSETS = "delegation,file,terminal"
OUTBOX_TEMPLATE = HERMES_ROOT / "templates" / "outbox_v2_8.json"
RUN_LEDGER_SCRIPT = HERMES_ROOT / "scripts" / "run-ledger.py"
DEFAULT_DISPATCH_TIMEOUT = float(os.environ.get("HERMES_DISPATCH_TIMEOUT", "600"))


def load_run_ledger():
    spec = importlib.util.spec_from_file_location("hermes_run_ledger", RUN_LEDGER_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_json(path):
    with open(Path(path).expanduser(), "r", encoding="utf-8") as f:
        return json.load(f)


def agent_id_from(task_card):
    execution_plan = task_card.get("execution_plan")
    if isinstance(execution_plan, dict):
        primary = execution_plan.get("primary_agent")
        if primary:
            return str(primary)
        agents = execution_plan.get("agents")
        if isinstance(agents, list) and agents:
            return str(agents[0])
    for key in ("agent_id", "agent", "preferred_agent"):
        value = task_card.get(key)
        if value:
            return str(value)
    compiled = task_card.get("compiled_intent")
    if isinstance(compiled, dict) and compiled.get("preferred_agent"):
        return str(compiled["preferred_agent"])
    return "claude"


def outbox_path_from(task_card):
    contract = task_card.get("output_contract")
    if isinstance(contract, dict) and contract.get("path"):
        return str(Path(contract["path"]).expanduser())
    task_id = task_card.get("task_card_id") or task_card.get("task_id") or "unknown"
    return str(Path.home() / ".claude" / "teams" / "staam" / "outbox" / f"{task_id}_result.json")


def infer_team_dir(inbox_path):
    inbox_path = Path(inbox_path).expanduser()
    if inbox_path.parent.name == "inbox":
        return inbox_path.parent.parent
    return inbox_path.parent


def run_ledger_path(inbox_path):
    return infer_team_dir(inbox_path) / "runs" / "ledger.jsonl"


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
    task_id = expected_task_id(task_card)
    if "_" in task_id:
        return _valid_project_name(task_id.split("_", 1)[0])
    return None


def default_run_ledger_path(task_card, inbox_path):
    project = project_from_task_card(task_card)
    if project:
        return TEAMS_DIR / project / "runs" / "ledger.jsonl"
    return run_ledger_path(inbox_path)


def outbox_contract_text():
    template = load_json(OUTBOX_TEMPLATE)
    required_fields = [
        "schema_version",
        "task_id",
        "agent_id",
        "status",
        "summary",
        "changed_files",
        "changed_files_source",
        "verification",
        "evidence",
        "known_risks",
        "errors",
        "error_taxonomy",
        "needs_human_review",
        "notes",
    ]
    compact_template = json.dumps(template, ensure_ascii=False, indent=2)
    return (
        "\n\nOutbox v2.8 contract:\n"
        "You MUST write a valid JSON object to the required outbox path.\n"
        "Required top-level fields:\n"
        + "\n".join(f"- {field}" for field in required_fields)
        + "\n\nMinimum JSON example:\n"
        f"{compact_template}\n"
        "Rules:\n"
        "- status must be \"waiting_for_verification\".\n"
        "- changed_files must list every actual changed file.\n"
        "- evidence.verification_commands and evidence.verification_output_summary must be specific.\n"
        "- errors must be [] when successful; otherwise include concrete errors and set needs_human_review=true.\n"
        "- Do not reply only in natural language; the outbox file is the deliverable."
    )


def expected_task_id(task_card):
    return str(task_card.get("task_card_id") or task_card.get("task_id") or "unknown")


def candidate_dirs_from(task_card):
    paths = []
    allowed_files = task_card.get("allowed_files")
    if isinstance(allowed_files, list):
        paths.extend(str(path) for path in allowed_files if path)
    compiled = task_card.get("compiled_intent")
    if isinstance(compiled, dict):
        for key in ("allowed_files", "relevant_files"):
            values = compiled.get(key)
            if isinstance(values, list):
                paths.extend(str(path) for path in values if path)

    dirs = []
    for raw_path in paths:
        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        candidate = path if path.is_dir() else path.parent
        while candidate and not candidate.exists() and candidate != candidate.parent:
            candidate = candidate.parent
        if candidate.exists():
            dirs.append(candidate)
    return dirs


def git_root_from(path):
    completed = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode == 0 and completed.stdout.strip():
        return Path(completed.stdout.strip())
    return None


def workspace_cwd_from(task_card):
    candidate_dirs = candidate_dirs_from(task_card)
    for candidate in candidate_dirs:
        root = git_root_from(candidate)
        if root is not None:
            return root
    if candidate_dirs:
        try:
            return Path(os.path.commonpath([str(path) for path in candidate_dirs]))
        except ValueError:
            return candidate_dirs[0]
    return None


def build_delegate_prompt(task_card, inbox_path):
    agent_id = agent_id_from(task_card)
    outbox_path = outbox_path_from(task_card)
    task_id = expected_task_id(task_card)
    revision = task_card.get("revision_brief")
    revision_text = ""
    if isinstance(revision, dict):
        instructions = revision.get("instructions") or []
        revision_text = (
            "\n\nRevision instructions:\n"
            + "\n".join(f"- {item}" for item in instructions)
        )

    goal = (
        "Execute this Hermes v2.8 Task Card. "
        f"Read inbox: {Path(inbox_path).expanduser()}. "
        f"Write the child-agent outbox exactly to: {outbox_path}. "
        f"The outbox task_id MUST be exactly {task_id!r}; do not add suffixes or timestamps. "
        "Respect allowed_files, safety, acceptance_criteria, and output_contract. "
        "Return a compact summary after the outbox is written."
    )
    context = (
        f"Task card path: {Path(inbox_path).expanduser()}\n"
        f"Exact outbox task_id: {task_id}\n"
        f"Required outbox path: {outbox_path}\n"
        "Use the injected outbox v2.8 contract exactly. "
        "Do not mark final completion yourself; the parent gate will verify and review."
        f"{outbox_contract_text()}"
        f"{revision_text}"
    )
    return (
        "Call the delegation tool exactly once with:\n"
        f"delegate_task(agent_id={agent_id!r}, goal={goal!r}, context={context!r})\n"
        "After the child returns, report only the child summary and outbox path."
    )


def build_command(task_card, inbox_path):
    return [
        HERMES_BIN,
        "-z",
        build_delegate_prompt(task_card, inbox_path),
        "--skills",
        DEFAULT_SKILLS,
        "--toolsets",
        DEFAULT_TOOLSETS,
    ]


def main():
    parser = argparse.ArgumentParser(description="Dispatch a Hermes v2.8 Task Card")
    parser.add_argument("--inbox", required=True, help="Inbox task card JSON path")
    parser.add_argument("--dry-run", action="store_true", help="Print command without executing it")
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_DISPATCH_TIMEOUT,
        help="Seconds to wait for external dispatch before marking timeout",
    )
    parser.add_argument("--run-ledger", help="Optional run ledger JSONL path")
    args = parser.parse_args()

    task_card = load_json(args.inbox)
    command = build_command(task_card, args.inbox)
    cwd = workspace_cwd_from(task_card)
    if args.dry_run:
        rendered = " ".join(shlex.quote(part) for part in command)
        if cwd is not None:
            rendered = f"cd {shlex.quote(str(cwd))} && {rendered}"
        print(rendered)
        return 0

    ledger = load_run_ledger()
    result = ledger.run_with_ledger(
        command,
        ledger_path=args.run_ledger or default_run_ledger_path(task_card, args.inbox),
        task_id=expected_task_id(task_card),
        agent_id=agent_id_from(task_card),
        run_type="dispatch",
        cwd=cwd,
        timeout=max(1.0, args.timeout),
    )
    if result.get("stdout"):
        print(result["stdout"], end="" if result["stdout"].endswith("\n") else "\n")
    if result.get("stderr"):
        print(result["stderr"], file=sys.stderr, end="" if result["stderr"].endswith("\n") else "\n")
    if result.get("timed_out"):
        print(
            f"dispatch timeout: run_id={result['run_id']} timeout={max(1.0, args.timeout)}s",
            file=sys.stderr,
        )
        return 124
    return result["exit_code"] if result["exit_code"] is not None else 1


if __name__ == "__main__":
    sys.exit(main())
