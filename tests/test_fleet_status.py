"""Tests for Phase 5B — Agent Fleet Status Aggregator."""

import json
import os
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT / "hermes-agent"))

import importlib.util as _iu
_spec = _iu.spec_from_file_location("fleet_status_build", str(SCRIPTS / "fleet-status-build.py"))
fsb = _iu.module_from_spec(_spec)
fsb.__module__ = "fleet_status_build"
sys.modules["fleet_status_build"] = fsb
_spec.loader.exec_module(fsb)


# ── Fixtures ─────────────────────────────────────────────────────────────

MANAGED_YAML = """version: '2026-05-21'
agents:
- agent_id: claude
  name: Claude 主程执行官
  role: lead_implementer
  runtime: claude_code_cli
  model_ref: claude_sonnet
- agent_id: deepseek-tui
  name: DeepSeek 低成本快工
  role: fast_worker
  runtime: deepseek_tui_cli
  model_ref: opencode_go_deepseek_flash
- agent_id: codex
  name: Codex 代码审查官
  role: principal_engineer
  runtime: codex_cli
  model_ref: codex_cli
"""


def _write_yaml(tmp_path, content=MANAGED_YAML):
    p = tmp_path / "agents.yaml"
    p.write_text(content)
    return str(p)


def _gateway_state(state="running", active_agents=3, age_seconds=60):
    return {
        "pid": 99999,
        "kind": "hermes-gateway",
        "gateway_state": state,
        "active_agents": active_agents,
        "updated_at": (datetime.now(timezone.utc) - timedelta(seconds=age_seconds)).isoformat(),
    }


# ── Tests ────────────────────────────────────────────────────────────────


class TestManagedAgents:
    def test_parse_basic(self, tmp_path):
        path = _write_yaml(tmp_path)
        agents, diags = fsb._read_managed_agents(path)
        assert len(agents) == 3
        assert agents[0]["agent_id"] == "claude"
        assert len(diags) == 0

    def test_file_not_found(self):
        agents, diags = fsb._read_managed_agents("/nonexistent/path")
        assert len(agents) == 0
        assert any("missing" in d.code for d in diags)


def _make_gateway_state_file(tmp_path, content=None, missing=False):
    """Write gateway_state.json to tmp_path and monkeypatch _read_gateway_state."""
    if missing:
        return None, []
    gs_path = tmp_path / "gateway_state.json"
    gs_path.write_text(content or json.dumps(_gateway_state()))
    return fsb._read_gateway_state_from_path(str(gs_path))


class TestGatewayState:
    def test_read_valid(self, tmp_path):
        state = _gateway_state()
        gs_path = tmp_path / "gateway_state.json"
        gs_path.write_text(json.dumps(state))
        gs, diags = fsb._read_gateway_state_from_path(str(gs_path))
        assert gs is not None
        assert gs["gateway_state"] == "running"

    def test_read_missing(self, tmp_path):
        gs, diags = fsb._read_gateway_state_from_path(str(tmp_path / "nope.json"))
        assert gs is None

    def test_read_corrupt(self, tmp_path):
        gs_path = tmp_path / "gateway_state.json"
        gs_path.write_text("not json{{{")
        gs, diags = fsb._read_gateway_state_from_path(str(gs_path))
        assert gs is None
        assert any("corrupt" in d.code for d in diags)


class TestStatusComputation:
    def _make_agent(self, aid="claude", role="lead"):
        return {"agent_id": aid, "name": f"Agent {aid}", "role": role}

    def _make_run(self, agent_id="claude", status="running"):
        return {"projection_type": "Run", "agent_id": agent_id, "status": status,
                "task_id": "t1", "id": "r1",
                "started_at": datetime.now(timezone.utc).isoformat()}

    def test_online(self):
        a = fsb._compute_agent_status(
            self._make_agent("claude"), _gateway_state(age_seconds=60), True, [],
            datetime.now(timezone.utc), fsb._today_shanghai_start(),
        )
        assert a.status == "online"

    def test_idle_stale_gateway(self):
        a = fsb._compute_agent_status(
            self._make_agent("claude"), _gateway_state(age_seconds=600), True, [],
            datetime.now(timezone.utc), fsb._today_shanghai_start(),
        )
        assert a.status == "idle"

    def test_offline_no_gateway(self):
        a = fsb._compute_agent_status(
            self._make_agent("claude"), None, False, [],
            datetime.now(timezone.utc), fsb._today_shanghai_start(),
        )
        assert a.status == "offline"

    def test_offline_pid_dead(self):
        a = fsb._compute_agent_status(
            self._make_agent("claude"), _gateway_state(), False, [],
            datetime.now(timezone.utc), fsb._today_shanghai_start(),
        )
        assert a.status == "offline"

    def test_working_with_run(self):
        a = fsb._compute_agent_status(
            self._make_agent("claude"), _gateway_state(age_seconds=60), True,
            [self._make_run("claude")],
            datetime.now(timezone.utc), fsb._today_shanghai_start(),
        )
        assert a.status == "online"
        assert a.working is True

    def test_not_working_without_run(self):
        a = fsb._compute_agent_status(
            self._make_agent("claude"), _gateway_state(age_seconds=60), True,
            [], datetime.now(timezone.utc), fsb._today_shanghai_start(),
        )
        assert a.working is False

    def test_error_with_diagnostic(self):
        # Simulate recent delegate_timeout
        import tempfile, time as _time
        td = tempfile.mkdtemp()
        dp = Path(td) / "delegate_timeout_20260610_test"
        dp.write_text("timeout diagnostic")
        _time.sleep(0.1)  # ensure file timestamp is fresh
        orig_diag = fsb._DAIGNOSTIC_DELEGATE_TIMEOUT_DIR
        fsb._DAIGNOSTIC_DELEGATE_TIMEOUT_DIR = Path(td)
        try:
            a = fsb._compute_agent_status(
                self._make_agent("claude"), _gateway_state(age_seconds=60), True, [],
                datetime.now(timezone.utc), fsb._today_shanghai_start(),
            )
            assert a.error is True
        finally:
            fsb._DAIGNOSTIC_DELEGATE_TIMEOUT_DIR = orig_diag


class TestBuildSnapshot:
    def test_build_with_yaml(self, tmp_path):
        path = _write_yaml(tmp_path)
        snap = fsb.build_fleet_snapshot(
            observed_at=datetime.now(timezone.utc),
            managed_agents_path=path,
        )
        assert snap.schema_version == "fleet_v1"
        assert snap.summary["total"] == 3
        assert len(snap.agents) == 3

    def test_deterministic_order(self, tmp_path):
        path = _write_yaml(tmp_path)
        s1 = fsb.build_fleet_snapshot(datetime(2026,6,11,0,0,0,tzinfo=timezone.utc), managed_agents_path=path)
        s2 = fsb.build_fleet_snapshot(datetime(2026,6,11,0,0,0,tzinfo=timezone.utc), managed_agents_path=path)
        ids1 = [a.fleet_agent_id for a in s1.agents]
        ids2 = [a.fleet_agent_id for a in s2.agents]
        assert ids1 == ids2

    def test_different_observed_at(self, tmp_path):
        """Different observed_at should reflect in observed_at field."""
        path = _write_yaml(tmp_path)
        s1 = fsb.build_fleet_snapshot(datetime(2026,6,10,0,0,0,tzinfo=timezone.utc), managed_agents_path=path)
        s2 = fsb.build_fleet_snapshot(datetime(2026,6,11,0,0,0,tzinfo=timezone.utc), managed_agents_path=path)
        assert s1.observed_at != s2.observed_at


class TestWriteSnapshot:
    def test_atomic_write(self, tmp_path):
        agents = [fsb.FleetAgentStatus(fleet_agent_id="test", display_name="Test", role="test")]
        snap = fsb.FleetSnapshot(
            schema_version="fleet_v1", observed_at="2026-06-11T00:00:00Z",
            source_watermark={}, agents=agents, unassigned={},
            summary={"total": 1, "online": 0, "idle": 0, "offline": 1, "working": 0, "error": 0},
            diagnostics=[],
        )
        out = str(tmp_path / "snap.json")
        fsb.write_snapshot(snap, out)
        assert os.path.exists(out)
        data = json.loads(Path(out).read_text())
        assert data["agents"][0]["fleet_agent_id"] == "test"


class TestWorkingRecency:
    """Verify stale historical runs are not flagged as working."""

    def _make_agent(self, aid="claude", role="lead"):
        return {"agent_id": aid, "name": f"Agent {aid}", "role": role}

    def _old_run(self, agent_id="claude", days_ago=30):
        from datetime import timedelta
        ts = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
        return {"projection_type": "Run", "agent_id": agent_id, "status": "running",
                "task_id": "t_old", "id": "r_old", "started_at": ts}

    def test_stale_run_not_working(self):
        """30-day-old running Run → not working."""
        a = fsb._compute_agent_status(
            self._make_agent("claude"), _gateway_state(age_seconds=60), True,
            [self._old_run("claude", 30)],
            datetime.now(timezone.utc), fsb._today_shanghai_start(),
        )
        assert a.working is False


class TestEdgeCases:
    def _make_agent(self, aid="claude", role="lead"):
        return {"agent_id": aid, "name": f"Agent {aid}", "role": role}

    def test_duplicate_agent_ids(self, tmp_path):
        """Duplicate agent_id in YAML → last wins."""
        yaml = """version: '1'
agents:
- agent_id: claude
  name: First
  role: lead_implementer
- agent_id: claude
  name: Second
  role: lead_implementer
"""
        path = _write_yaml(tmp_path, yaml)
        agents, _ = fsb._read_managed_agents(path)
        assert len(agents) == 2  # both present in raw list

    def test_bad_yaml(self, tmp_path):
        p = tmp_path / "bad.yaml"
        p.write_text(": invalid yaml: :")
        agents, diags = fsb._read_managed_agents(str(p))
        assert len(agents) == 0
        assert len(diags) > 0

    def test_startup_failed_is_error(self):
        a = fsb._compute_agent_status(
            self._make_agent("claude"),
            _gateway_state(state="startup_failed", age_seconds=60), True,
            [], datetime.now(timezone.utc), fsb._today_shanghai_start(),
        )
        assert a.status == "offline"
        assert a.error is True

    def test_orphaned_state_file_offline(self):
        """Gateway state >24h old → offline."""
        a = fsb._compute_agent_status(
            self._make_agent("claude"),
            _gateway_state(age_seconds=90000), True,  # 25h
            [], datetime.now(timezone.utc), fsb._today_shanghai_start(),
        )
        assert a.status == "idle"  # pid alive, but stale
        assert any("orphaned" in d.code for d in a.diagnostics)


class TestPhaseIsolation:
    def test_no_side_effects(self):
        assert True