"""Tests for Phase 4B — Kanban Task/Run Control Interface."""

import json
import os
import secrets
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT / "hermes-agent"))

import importlib.util as _iu
_spec = _iu.spec_from_file_location("task_run_control", str(SCRIPTS / "task-run-control.py"))
ctrl = _iu.module_from_spec(_spec)
ctrl.__module__ = "task_run_control"
sys.modules["task_run_control"] = ctrl
_spec.loader.exec_module(ctrl)


def _cid(target="kanban:default:task:t1", cmd="approve"):
    return ctrl._command_id(target, cmd, ctrl._now_iso(), secrets.token_hex(8))


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class TestValidation:
    def test_valid_approve(self):
        e = ctrl.CommandEnvelope(command_id=_cid(), command_type="approve",
            target_task_id="kanban:default:task:t1", requested_by="user", requested_at=ctrl._now_iso())
        assert ctrl.validate_envelope(e) is None

    def test_unsupported_command(self):
        e = ctrl.CommandEnvelope(command_id=_cid(), command_type="cancel",
            target_task_id="kanban:default:task:t1", requested_by="user", requested_at=ctrl._now_iso())
        assert "unsupported" in ctrl.validate_envelope(e)

    def test_pipeline_namespace(self):
        e = ctrl.CommandEnvelope(command_id=_cid(), command_type="approve",
            target_task_id="pipeline:staam:task:t1", requested_by="user", requested_at=ctrl._now_iso())
        assert "unsupported namespace" in ctrl.validate_envelope(e)

    def test_delegate_namespace(self):
        e = ctrl.CommandEnvelope(command_id=_cid(), command_type="approve",
            target_task_id="delegate:s1:task:tc:0", requested_by="user", requested_at=ctrl._now_iso())
        assert "unsupported namespace" in ctrl.validate_envelope(e)

    def test_empty_requested_by(self):
        e = ctrl.CommandEnvelope(command_id=_cid(), command_type="approve",
            target_task_id="kanban:default:task:t1", requested_by="", requested_at=ctrl._now_iso())
        assert "requested_by" in ctrl.validate_envelope(e)

    def test_reject_with_expected_version(self):
        e = ctrl.CommandEnvelope(command_id=_cid(), command_type="reject",
            target_task_id="kanban:default:task:t1", requested_by="user",
            requested_at=ctrl._now_iso(), expected_version="5")
        assert "expected_version" in ctrl.validate_envelope(e)

    def test_missing_command_id(self):
        e = ctrl.CommandEnvelope(command_id="", command_type="approve",
            target_task_id="kanban:default:task:t1", requested_by="user", requested_at=ctrl._now_iso())
        assert "command_id" in ctrl.validate_envelope(e)


# ---------------------------------------------------------------------------
# ID Parsing
# ---------------------------------------------------------------------------

class TestParseKanbanId:
    def test_valid(self):
        b, p = ctrl._parse_kanban_id("kanban:default:task:t6")
        assert (b, p) == ("default", "t6")

    def test_pipeline(self):
        assert ctrl._parse_kanban_id("pipeline:staam:task:t1") == (None, None)

    def test_delegate(self):
        assert ctrl._parse_kanban_id("delegate:s1:task:tc:0") == (None, None)

    def test_malformed(self):
        assert ctrl._parse_kanban_id("kanban:default") == (None, None)

    def test_path_traversal_rejected(self):
        assert ctrl._parse_kanban_id("kanban:../../../etc:task:id") == (None, None)

    def test_empty_task_pk_rejected(self):
        assert ctrl._parse_kanban_id("kanban:board:task:") == (None, None)


# ---------------------------------------------------------------------------
# Command Log
# ---------------------------------------------------------------------------

class TestCommandLog:
    def test_append_and_read(self, tmp_path):
        cid = _cid()
        ctrl.append_command_log(ctrl.CommandResult(command_id=cid, status="completed"), str(tmp_path))
        found = ctrl.read_command_log(cid, str(tmp_path))
        assert found is not None and found.status == "completed"

    def test_not_found(self, tmp_path):
        assert ctrl.read_command_log("nonexistent", str(tmp_path)) is None

    def test_empty_dir(self, tmp_path):
        assert ctrl.read_command_log("any", str(tmp_path / "nope")) is None


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

class TestIdempotency:
    def test_duplicate_request_returns_cached(self, tmp_path):
        cid = _cid()
        ctrl.append_command_log(ctrl.CommandResult(command_id=cid, status="completed"), str(tmp_path))
        env = ctrl.CommandEnvelope(command_id=cid, command_type="approve",
            target_task_id="kanban:default:task:t1", requested_by="user", requested_at=ctrl._now_iso())
        result = ctrl.execute_command(env, str(tmp_path))
        assert result.status == "completed"

    def test_accepted_replay_dispatches(self, tmp_path):
        """Crash window 1/2: 'accepted' in log → re-dispatches (but task may already be done)."""
        cid = _cid()
        ctrl.append_command_log(ctrl.CommandResult(command_id=cid, status="accepted"), str(tmp_path))
        env = ctrl.CommandEnvelope(command_id=cid, command_type="approve",
            target_task_id="kanban:deadbeef:task:nonexistent", requested_by="user", requested_at=ctrl._now_iso())
        result = ctrl.execute_command(env, str(tmp_path))
        # Task doesn't exist → rejected (not completed)
        assert result.status in ("rejected", "failed_unavailable")


# ---------------------------------------------------------------------------
# Execute via temp SQLite (full round-trip for approve/reject logic)
# ---------------------------------------------------------------------------

def _make_full_db(tmp_path, task_id="t1", status="running", current_run_id=1):
    """Create a db with the full schema that complete_task/archive_task need."""
    db = str(tmp_path / "kb.db")
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    conn.executescript(f"""
        CREATE TABLE tasks (id TEXT PRIMARY KEY, title TEXT, body TEXT,
            assignee TEXT, status TEXT NOT NULL, priority INTEGER DEFAULT 0,
            created_by TEXT, created_at INTEGER NOT NULL, started_at INTEGER,
            completed_at INTEGER, workspace_kind TEXT DEFAULT 'scratch',
            workspace_path TEXT, branch_name TEXT, claim_lock TEXT,
            claim_expires INTEGER, worker_pid INTEGER, result TEXT,
            current_run_id INTEGER, consecutive_failures INTEGER DEFAULT 0,
            last_failure_error TEXT, max_runtime_seconds INTEGER,
            last_heartbeat_at INTEGER, session_id TEXT,
            workflow_template_id TEXT, current_step_key TEXT,
            skills TEXT, model_override TEXT, max_retries INTEGER,
            goal_mode INTEGER DEFAULT 0, goal_max_turns INTEGER,
            idempotency_key TEXT);
        CREATE TABLE task_runs (id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL, profile TEXT, step_key TEXT,
            status TEXT NOT NULL, claim_lock TEXT, claim_expires INTEGER,
            worker_pid INTEGER, max_runtime_seconds INTEGER,
            last_heartbeat_at INTEGER, started_at INTEGER NOT NULL,
            ended_at INTEGER, outcome TEXT, summary TEXT, metadata TEXT,
            error TEXT);
        CREATE TABLE task_events (id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL, run_id INTEGER, kind TEXT NOT NULL,
            payload TEXT, created_at INTEGER NOT NULL);
        CREATE TABLE task_links (parent_id TEXT, child_id TEXT,
            PRIMARY KEY(parent_id, child_id));
    """)
    conn.execute("INSERT INTO tasks(id,title,status,created_at,current_run_id,workspace_kind) VALUES(?,?,?,1000,?,'scratch')",
                 (task_id, "Test", status, current_run_id))
    conn.execute("INSERT INTO task_runs(id,task_id,profile,status,started_at) VALUES(?,?,'claude','running',1000)",
                 (current_run_id, task_id))
    conn.commit()
    conn.close()
    return db


class TestApproveFull:
    def test_approve_success(self, tmp_path):
        db = _make_full_db(tmp_path, "t1", "running", 1)
        ctrl._resolve_kanban_db = lambda b: db
        try:
            env = ctrl.CommandEnvelope(command_id=_cid("kanban:x:task:t1"),
                command_type="approve", target_task_id="kanban:x:task:t1",
                requested_by="user", requested_at=ctrl._now_iso())
            r = ctrl.execute_command(env, str(tmp_path))
            assert r.status == "completed", f"error={r.error}"
        finally:
            del ctrl._resolve_kanban_db

    def test_approve_stale_expected_run_id(self, tmp_path):
        db = _make_full_db(tmp_path, "t1", "running", 1)
        ctrl._resolve_kanban_db = lambda b: db
        try:
            env = ctrl.CommandEnvelope(command_id=_cid("kanban:x:task:t1"),
                command_type="approve", target_task_id="kanban:x:task:t1",
                requested_by="user", requested_at=ctrl._now_iso(),
                expected_version="99")
            r = ctrl.execute_command(env, str(tmp_path))
            assert r.status == "rejected"
        finally:
            del ctrl._resolve_kanban_db

    def test_approve_already_done(self, tmp_path):
        db = _make_full_db(tmp_path, "t1", "done", 1)
        ctrl._resolve_kanban_db = lambda b: db
        try:
            env = ctrl.CommandEnvelope(command_id=_cid("kanban:x:task:t1"),
                command_type="approve", target_task_id="kanban:x:task:t1",
                requested_by="user", requested_at=ctrl._now_iso())
            r = ctrl.execute_command(env, str(tmp_path))
            assert r.status == "completed"  # already done = success
        finally:
            del ctrl._resolve_kanban_db

    def test_approve_idempotent(self, tmp_path):
        db = _make_full_db(tmp_path, "t1", "running", 1)
        cid = _cid("kanban:x:task:t1")
        ctrl._resolve_kanban_db = lambda b: db
        try:
            env = ctrl.CommandEnvelope(command_id=cid, command_type="approve",
                target_task_id="kanban:x:task:t1", requested_by="user", requested_at=ctrl._now_iso())
            r1 = ctrl.execute_command(env, str(tmp_path))
            assert r1.status == "completed"
            r2 = ctrl.execute_command(env, str(tmp_path))
            assert r2.status == "completed"
        finally:
            del ctrl._resolve_kanban_db


class TestRejectFull:
    def test_reject_success(self, tmp_path):
        db = _make_full_db(tmp_path, "t1", "running", 1)
        ctrl._resolve_kanban_db = lambda b: db
        try:
            env = ctrl.CommandEnvelope(command_id=_cid("kanban:x:task:t1", "reject"),
                command_type="reject", target_task_id="kanban:x:task:t1",
                requested_by="user", requested_at=ctrl._now_iso())
            r = ctrl.execute_command(env, str(tmp_path))
            assert r.status == "completed", f"error={r.error}"
        finally:
            del ctrl._resolve_kanban_db

    def test_reject_already_archived(self, tmp_path):
        db = _make_full_db(tmp_path, "t1", "archived", 1)
        ctrl._resolve_kanban_db = lambda b: db
        try:
            env = ctrl.CommandEnvelope(command_id=_cid("kanban:x:task:t1", "reject"),
                command_type="reject", target_task_id="kanban:x:task:t1",
                requested_by="user", requested_at=ctrl._now_iso())
            r = ctrl.execute_command(env, str(tmp_path))
            assert r.status == "completed"
        finally:
            del ctrl._resolve_kanban_db


class TestCrashWindows:
    def test_window2_precheck_already_done(self, tmp_path):
        """Kanban done, log has accepted → return completed."""
        db = _make_full_db(tmp_path, "t1", "done", 1)
        cid = _cid("kanban:x:task:t1")
        ctrl._resolve_kanban_db = lambda b: db
        try:
            ctrl.append_command_log(ctrl.CommandResult(command_id=cid, status="accepted"), str(tmp_path))
            env = ctrl.CommandEnvelope(command_id=cid, command_type="approve",
                target_task_id="kanban:x:task:t1", requested_by="user", requested_at=ctrl._now_iso())
            r = ctrl.execute_command(env, str(tmp_path))
            assert r.status == "completed"
        finally:
            del ctrl._resolve_kanban_db


class TestPhaseIsolation:
    def test_pipeline_rejected(self, tmp_path):
        env = ctrl.CommandEnvelope(command_id=_cid("pipeline:s:task:t"),
            command_type="approve", target_task_id="pipeline:s:task:t",
            requested_by="user", requested_at=ctrl._now_iso())
        assert ctrl.execute_command(env, str(tmp_path)).status == "rejected"

    def test_delegate_rejected(self, tmp_path):
        env = ctrl.CommandEnvelope(command_id=_cid("delegate:s:task:tc:0"),
            command_type="approve", target_task_id="delegate:s:task:tc:0",
            requested_by="user", requested_at=ctrl._now_iso())
        assert ctrl.execute_command(env, str(tmp_path)).status == "rejected"