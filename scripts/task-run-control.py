#!/usr/bin/env python3
"""Phase 4B — Kanban-only Unified Task/Run Control Interface.

Implements §2-§6 of docs/architecture/unified-task-run-control-phase4.md.

Supports:
  - approve → kanban_db.complete_task() with expected_run_id CAS
  - reject  → kanban_db.archive_task() (no CAS)

Crash recovery via three-window command log + Kanban authoritative state pre-check.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import secrets
import sqlite3
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_COMMANDS_DIR_DEFAULT = str(Path.home() / ".hermes" / "commands")
_SUPPORTED_COMMANDS = frozenset({"approve", "reject"})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _command_id(
    target_task_id: str, command_type: str, requested_at: str, nonce: str,
) -> str:
    raw = f"control:{target_task_id}:{command_type}:{requested_at}:{nonce}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class CommandEnvelope:
    command_id: str
    command_type: str
    target_task_id: str
    requested_by: str
    requested_at: str
    target_run_id: Optional[str] = None
    reason: Optional[str] = None
    expected_version: Optional[str] = None


@dataclass
class CommandResult:
    command_id: str
    status: str  # accepted | rejected | completed | failed_unavailable
    accepted_at: Optional[str] = None
    completed_at: Optional[str] = None
    source_event_id: Optional[str] = None
    error: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


@dataclass
class CommandConflict:
    command_id: str
    existing_status: str
    message: str


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


import re as _re

_BOARD_RE = _re.compile(r"^[a-zA-Z0-9][-a-zA-Z0-9_]*[a-zA-Z0-9]$|^[a-zA-Z0-9]$")


def _parse_kanban_id(task_id: str) -> Tuple[Optional[str], Optional[str]]:
    """Parse kanban:{board}:task:{id} → (board, task_pk) or (None, None)."""
    if not task_id.startswith("kanban:"):
        return None, None
    parts = task_id.split(":", 3)
    if len(parts) < 4 or parts[2] != "task":
        return None, None
    board = parts[1]
    task_pk = parts[3]
    # Validate board slug — prevents path traversal
    if not _BOARD_RE.match(board):
        return None, None
    if not task_pk or not task_pk.strip():
        return None, None
    return board, task_pk


def _resolve_kanban_db(board: str) -> Optional[str]:
    """Resolve a board slug to its SQLite database path.

    Board slug is already validated by _parse_kanban_id against
    _BOARD_RE — safe for filesystem path construction.
    """
    home = Path.home()
    # Multi-board directory
    board_db = home / ".hermes" / "kanban" / "boards" / board / "kanban.db"
    if board_db.is_file():
        return str(board_db)
    # Default board
    db = home / ".hermes" / "kanban.db"
    if db.is_file():
        return str(db)
    return None


def validate_envelope(env: CommandEnvelope) -> Optional[str]:
    """Return error string if envelope is invalid, None if valid."""
    if not env.command_id:
        return "command_id is required"
    if env.command_type not in _SUPPORTED_COMMANDS:
        return f"unsupported command_type: {env.command_type!r}"
    if not env.target_task_id:
        return "target_task_id is required"
    if not env.requested_by or not str(env.requested_by).strip():
        return "requested_by is required"
    if not env.requested_at:
        return "requested_at is required"
    board, task_pk = _parse_kanban_id(env.target_task_id)
    if board is None:
        return f"unsupported namespace: {env.target_task_id!r}"
    if env.command_type == "reject" and env.expected_version is not None:
        return "reject does not support expected_version"
    return None


def _kanban_task_status(db_path: str, task_pk: str) -> Optional[str]:
    """Read current task status from Kanban SQLite (authoritative pre-check)."""
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT status FROM tasks WHERE id = ?", (task_pk,)
        ).fetchone()
        conn.close()
        if row:
            return row["status"]
        return None
    except sqlite3.Error:
        return None


def _kanban_current_run_id(db_path: str, task_pk: str) -> Optional[int]:
    """Read current_run_id for expected_version CAS."""
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT current_run_id FROM tasks WHERE id = ?", (task_pk,)
        ).fetchone()
        conn.close()
        if row and row["current_run_id"] is not None:
            return int(row["current_run_id"])
        return None
    except sqlite3.Error:
        return None


# ---------------------------------------------------------------------------
# Command log (flock + O_APPEND + fsync)
# ---------------------------------------------------------------------------


def _command_log_dir(commands_dir: Optional[str] = None) -> Path:
    return Path(commands_dir or _COMMANDS_DIR_DEFAULT)


def _command_log_path(commands_dir: Optional[str] = None) -> Path:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return _command_log_dir(commands_dir) / f"{today}.jsonl"


def read_command_log(
    command_id: str, commands_dir: Optional[str] = None,
) -> Optional[CommandResult]:
    """Read existing command result by command_id from today's log."""
    path = _command_log_path(commands_dir)
    if not path.is_file():
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    record = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                if record.get("command_id") == command_id:
                    return CommandResult(
                        command_id=record.get("command_id", ""),
                        status=record.get("status", "unknown"),
                        accepted_at=record.get("accepted_at"),
                        completed_at=record.get("completed_at"),
                        source_event_id=record.get("source_event_id"),
                        error=record.get("error"),
                        details=record.get("details"),
                    )
    except (OSError, json.JSONDecodeError):
        pass
    return None


def append_command_log(
    result: CommandResult, commands_dir: Optional[str] = None,
) -> None:
    """Append one command result to today's log with flock+fsync."""
    path = _command_log_path(commands_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(asdict(result), ensure_ascii=False, default=str) + "\n"
    data = line.encode("utf-8")
    try:
        with open(path, "ab") as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                os.write(fh.fileno(), data)
                os.fsync(fh.fileno())
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass  # log failure should not block command


# ---------------------------------------------------------------------------
# Kanban Adapter
# ---------------------------------------------------------------------------


def _execute_approve(
    board: str, task_pk: str, expected_version: Optional[str] = None,
) -> Tuple[str, Optional[str], Optional[str]]:
    """Execute approve via Kanban complete_task. Returns (status, error, source_event_id)."""
    db_path = _resolve_kanban_db(board)
    if not db_path:
        return "failed_unavailable", "kanban database not found", None

    # Authoritative pre-check (crash window 2)
    current_status = _kanban_task_status(db_path, task_pk)
    if current_status is None:
        return "rejected", "task not found", None
    if current_status == "done":
        return "completed", None, None  # already succeeded silently
    if current_status == "archived":
        return "completed", None, None  # already archived (but approve shouldn't hit this)
    if current_status not in ("running", "ready", "blocked"):
        return "rejected", f"invalid status for approve: {current_status!r}", None

    # Resolve expected_run_id
    expected_run_id = None
    if expected_version is not None:
        try:
            expected_run_id = int(expected_version)
        except (TypeError, ValueError):
            return "rejected", f"invalid expected_version: {expected_version!r}", None

    try:
        from hermes_cli.kanban_db import complete_task

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        ok = complete_task(conn, task_pk, expected_run_id=expected_run_id)
        if ok:
            # Read last event id for source_event_id
            row = conn.execute(
                "SELECT MAX(id) FROM task_events WHERE task_id = ?", (task_pk,)
            ).fetchone()
            source_event_id = str(row[0]) if row and row[0] else None
            conn.close()
            return "completed", None, source_event_id
        else:
            # Could be CAS failure or already done
            current_status_after = _kanban_task_status(db_path, task_pk)
            if current_status_after == "done":
                conn.close()
                return "completed", None, None  # completed by another path
            conn.close()
            return "rejected", "expected_version_mismatch or task state changed", None
    except ImportError:
        return "failed_unavailable", "kanban_db module not available", None
    except Exception as e:
        return "failed_unavailable", str(e), None


def _execute_reject(
    board: str, task_pk: str,
) -> Tuple[str, Optional[str], Optional[str]]:
    """Execute reject via Kanban archive_task. Returns (status, error, source_event_id)."""
    db_path = _resolve_kanban_db(board)
    if not db_path:
        return "failed_unavailable", "kanban database not found", None

    # Authoritative pre-check (crash window 2)
    current_status = _kanban_task_status(db_path, task_pk)
    if current_status is None:
        return "rejected", "task not found", None
    if current_status == "archived":
        return "completed", None, None  # already succeeded silently
    if current_status == "done":
        return "rejected", "cannot archive a completed task (approve first)", None

    try:
        from hermes_cli.kanban_db import archive_task

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        ok = archive_task(conn, task_pk)
        if ok:
            row = conn.execute(
                "SELECT MAX(id) FROM task_events WHERE task_id = ?", (task_pk,)
            ).fetchone()
            source_event_id = str(row[0]) if row and row[0] else None
            conn.close()
            return "completed", None, source_event_id
        else:
            current_status_after = _kanban_task_status(db_path, task_pk)
            if current_status_after == "archived":
                conn.close()
                return "completed", None, None
            conn.close()
            return "rejected", "archive failed (concurrent modification)", None
    except ImportError:
        return "failed_unavailable", "kanban_db module not available", None
    except Exception as e:
        return "failed_unavailable", str(e), None


# ---------------------------------------------------------------------------
# Command dispatch
# ---------------------------------------------------------------------------


def execute_command(
    env: CommandEnvelope, commands_dir: Optional[str] = None,
) -> CommandResult:
    """Execute a single command with full crash recovery."""
    # 1. Validate
    validation_error = validate_envelope(env)
    if validation_error:
        return CommandResult(
            command_id=env.command_id, status="rejected",
            error=validation_error,
        )

    # 2. Idempotency check
    existing = read_command_log(env.command_id, commands_dir)
    if existing is not None:
        if existing.status == "completed":
            return existing
        if existing.status == "accepted":
            # Crash window 1 or 2 — will re-check authoritative state below
            pass

    # 3. Accept
    board, task_pk = _parse_kanban_id(env.target_task_id)
    if board is None or task_pk is None:
        return CommandResult(
            command_id=env.command_id, status="rejected",
            error="invalid kanban target_task_id",
        )

    accepted_result = CommandResult(
        command_id=env.command_id, status="accepted",
        accepted_at=_now_iso(),
    )
    append_command_log(accepted_result, commands_dir)

    # 4. Execute
    status: str
    error: Optional[str] = None
    source_event_id: Optional[str] = None

    if env.command_type == "approve":
        status, error, source_event_id = _execute_approve(
            board, task_pk, env.expected_version,
        )
    elif env.command_type == "reject":
        status, error, source_event_id = _execute_reject(board, task_pk)
    else:
        status = "rejected"
        error = f"unsupported command: {env.command_type}"

    # 5. Finalize
    result = CommandResult(
        command_id=env.command_id, status=status,
        accepted_at=accepted_result.accepted_at,
        completed_at=_now_iso() if status == "completed" else None,
        source_event_id=source_event_id,
        error=error,
    )
    append_command_log(result, commands_dir)
    return result
