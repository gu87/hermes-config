#!/usr/bin/env python3
"""Phase 4B — Kanban Control CLI.

Usage:
  python scripts/task-run-control-cli.py --command approve --target kanban:default:task:t6 --by user
  python scripts/task-run-control-cli.py --command reject  --target kanban:default:task:t6 --by user
  python scripts/task-run-control-cli.py --command-id <id> ...  # idempotent retry
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

# ── Import sibling module ──────────────────────────────────────────────
# task-run-control.py uses hyphens in its filename (cannot import directly).
# Uses __file__ (resolved absolute) — never depends on cwd.
_SCRIPTS_DIR = Path(__file__).resolve().parent
_HERMES_AGENT = _SCRIPTS_DIR.parent / "hermes-agent"
sys.path.insert(0, str(_HERMES_AGENT))

import importlib.util as _iu
try:
    _spec = _iu.spec_from_file_location(
        "task_run_control", str(_SCRIPTS_DIR / "task-run-control.py")
    )
    if _spec is None or _spec.loader is None:
        print(json.dumps({"status": "failed_unavailable", "error": "cannot load task-run-control.py"}, ensure_ascii=False))
        raise SystemExit(2)
    ctrl = _iu.module_from_spec(_spec)
    ctrl.__module__ = "task_run_control"
    sys.modules["task_run_control"] = ctrl
    _spec.loader.exec_module(ctrl)
except Exception as exc:
    print(json.dumps({"status": "failed_unavailable", "error": f"import failed: {exc}"}, ensure_ascii=False))
    raise SystemExit(2)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Kanban Task/Run Control (Phase 4B)")
    parser.add_argument("--command", required=True, choices=["approve", "reject"])
    parser.add_argument("--target", required=True, help="Unified Task ID (kanban:{board}:task:{id})")
    parser.add_argument("--run", default=None, help="Optional target Run ID")
    parser.add_argument("--by", required=True, help="Requested by (user/codex/ambrosini/...)")
    parser.add_argument("--reason", default=None, help="Optional reason")
    parser.add_argument("--expected-version", default=None, help="expected_run_id for approve CAS")
    parser.add_argument("--command-id", default=None, help="Reuse existing command_id for retry")
    parser.add_argument("--commands-dir", default=None, help="Command log directory")
    parser.add_argument("--kanban-boards-dir", default=None,
                        help="[TEST ONLY] Override kanban boards directory. "
                             "Must point to a directory containing boards/{slug}/kanban.db subdirs.")
    args = parser.parse_args(argv)

    # [TEST ONLY] Override board resolution.
    if args.kanban_boards_dir:
        override = Path(args.kanban_boards_dir).resolve()
        if not override.is_dir():
            print(json.dumps({"status": "failed_unavailable",
                "error": f"--kanban-boards-dir is not a directory: {override}"}, ensure_ascii=False))
            return 2
        ctrl._resolve_kanban_db = lambda board, _od=override: (
            str(_od / "boards" / board / "kanban.db")
            if (_od / "boards" / board / "kanban.db").is_file() else None
        )

    import secrets
    cid = args.command_id or ctrl._command_id(
        args.target, args.command, ctrl._now_iso(), secrets.token_hex(8))
    env = ctrl.CommandEnvelope(
        command_id=cid,
        command_type=args.command,
        target_task_id=args.target,
        target_run_id=args.run,
        requested_by=args.by,
        requested_at=ctrl._now_iso(),
        reason=args.reason,
        expected_version=args.expected_version,
    )
    result = ctrl.execute_command(env, args.commands_dir)
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    if result.status == "completed":
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())