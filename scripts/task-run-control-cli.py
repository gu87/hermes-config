#!/usr/bin/env python3
"""Phase 4B — Kanban Control CLI (minimal entry point)."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

import task_run_control as ctrl


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
    args = parser.parse_args(argv)

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