#!/usr/bin/env python3
"""Phase 5B — Agent Fleet Status Aggregator.

Reads managed-agents.yaml, gateway_state.json, gateway.pid, and Unified
projection to build a FleetSnapshot.

Output: ~/.hermes/projections/fleet/snapshot.json (atomic write, deletable).

Usage:
  python scripts/fleet-status-build.py
  python scripts/fleet-status-build.py --output /tmp/fleet.json
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_SCRIPT_DIR = Path(__file__).resolve().parent
_HERMES_ROOT = _SCRIPT_DIR.parent
_HERMES_AGENT = _HERMES_ROOT / "hermes-agent"
sys.path.insert(0, str(_HERMES_AGENT))

# ── Constants ────────────────────────────────────────────────────────────
_SCHEMA_VERSION = "fleet_v1"
_TZ_SHANGHAI = timezone(timedelta(hours=8))
_GATEWAY_STALE_SECONDS = 300  # 5 minutes
_GATEWAY_ORPHANED_SECONDS = 86400  # 24 hours
_ERROR_WINDOW_SECONDS = 3600  # 1 hour
_DAIGNOSTIC_DELEGATE_TIMEOUT_DIR = Path.home() / ".hermes" / "logs"
_OUTPUT_DEFAULT = str(Path.home() / ".hermes" / "projections" / "fleet" / "snapshot.json")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now_utc().isoformat()


def _today_shanghai_start() -> datetime:
    """Start of today in Asia/Shanghai (UTC+8)."""
    now_sh = datetime.now(_TZ_SHANGHAI)
    return now_sh.replace(hour=0, minute=0, second=0, microsecond=0)


# ── Data Models ──────────────────────────────────────────────────────────


@dataclass
class FleetDiagnostic:
    code: str
    message: str


@dataclass
class FleetAgentStatus:
    fleet_agent_id: str
    display_name: str
    role: str
    runtime: Optional[str] = None
    status: str = "offline"  # online | idle | offline
    working: bool = False
    error: bool = False
    current_task_id: Optional[str] = None
    current_run_id: Optional[str] = None
    last_active_at: Optional[str] = None
    today_task_count: int = 0
    today_cost_usd: Optional[float] = None
    session_count: int = 0
    diagnostics: List[FleetDiagnostic] = field(default_factory=list)


@dataclass
class FleetSnapshot:
    schema_version: str
    observed_at: str
    source_watermark: Dict[str, Any]
    agents: List[FleetAgentStatus]
    unassigned: Dict[str, Any]
    summary: Dict[str, int]
    diagnostics: List[FleetDiagnostic]


# ── Source Readers ───────────────────────────────────────────────────────


def _read_managed_agents(path: Optional[str] = None) -> Tuple[List[Dict[str, Any]], List[FleetDiagnostic]]:
    """Parse managed-agents.yaml. Returns (agents_list, diagnostics)."""
    diagnostics: List[FleetDiagnostic] = []
    yaml_path = Path(path) if path else _HERMES_ROOT / "config" / "managed-agents.yaml"
    try:
        import yaml
        with open(yaml_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        agents = config.get("agents") or []
        if not isinstance(agents, list):
            return [], [FleetDiagnostic("config_error", "managed-agents.yaml agents is not a list")]
        return agents, diagnostics
    except FileNotFoundError:
        return [], [FleetDiagnostic("config_missing", f"managed-agents.yaml not found: {yaml_path}")]
    except Exception as e:
        return [], [FleetDiagnostic("config_error", f"managed-agents.yaml parse error: {e}")]


def _read_gateway_state_from_path(path_str: str) -> Tuple[Optional[Dict[str, Any]], List[FleetDiagnostic]]:
    """Read gateway_state.json from a specific path (for testing)."""
    path = Path(path_str)
    diagnostics: List[FleetDiagnostic] = []
    if not path.is_file():
        return None, diagnostics
    try:
        raw = path.read_text(encoding="utf-8").strip()
        if not raw:
            return None, [FleetDiagnostic("gateway_state_empty", "gateway_state.json is empty")]
        state = json.loads(raw)
        if not isinstance(state, dict):
            return None, [FleetDiagnostic("gateway_state_corrupt", "gateway_state.json is not a JSON object")]
        return state, diagnostics
    except json.JSONDecodeError:
        return None, [FleetDiagnostic("gateway_state_corrupt", "gateway_state.json invalid JSON")]
    except OSError:
        return None, diagnostics


def _read_gateway_state() -> Tuple[Optional[Dict[str, Any]], List[FleetDiagnostic]]:
    """Read gateway_state.json from default location."""
    path = str(Path.home() / ".hermes" / "gateway_state.json")
    return _read_gateway_state_from_path(path)


def _verify_pid(pid: int) -> bool:
    """Check if a process with the given PID exists and is accessible."""
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _load_projection() -> Dict[str, Any]:
    """Load projection records from the Unified projection JSONL.
    Returns empty dict on failure — Fleet should not crash on missing projection.
    """
    proj_path = Path.home() / ".hermes" / "projections" / "task-card-pipeline" / "staam" / "events.jsonl"
    if not proj_path.is_file():
        return {}
    try:
        runs: List[Dict] = []
        with open(proj_path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    rec = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                if rec.get("projection_type") in ("Run", "DomainEventEnvelope", "Task"):
                    runs.append(rec)
        return {"records": runs}
    except OSError:
        return {}


# ── Status Computer ──────────────────────────────────────────────────────


def _compute_agent_status(
    agent_cfg: Dict[str, Any],
    gateway_state: Optional[Dict[str, Any]],
    gateway_pid_alive: bool,
    runs: List[Dict[str, Any]],
    observed_at: datetime,
    today_start: datetime,
) -> FleetAgentStatus:
    agent_id = agent_cfg.get("agent_id", "unknown")
    diagnostics: List[FleetDiagnostic] = []

    # ── Base identity ──
    status = FleetAgentStatus(
        fleet_agent_id=agent_id,
        display_name=agent_cfg.get("name", agent_id),
        role=agent_cfg.get("role", "unknown"),
        runtime=agent_cfg.get("runtime"),
    )

    # ── status: online | idle | offline ──
    if gateway_state and gateway_pid_alive:
        gs = gateway_state.get("gateway_state", "")
        updated_raw = gateway_state.get("updated_at", "")
        try:
            updated_at = datetime.fromisoformat(updated_raw)
            delta = (observed_at - updated_at).total_seconds()
            if gs == "running" and delta < _GATEWAY_STALE_SECONDS:
                status.status = "online"
            elif gs == "running":
                status.status = "idle"
                if delta > _GATEWAY_ORPHANED_SECONDS:
                    diagnostics.append(FleetDiagnostic("orphaned_state_file",
                        f"gateway_state not updated for {int(delta)}s"))
            else:
                status.status = "offline"
                if gs == "startup_failed":
                    status.error = True
                    diagnostics.append(FleetDiagnostic("gateway_startup_failed", "Gateway startup failed"))
        except (ValueError, TypeError):
            status.status = "offline"
            diagnostics.append(FleetDiagnostic("gateway_state_corrupt", "invalid updated_at"))
        status.last_active_at = updated_raw if updated_raw else None
    else:
        status.status = "offline"
        if gateway_state and not gateway_pid_alive:
            diagnostics.append(FleetDiagnostic("stale_pid",
                f"gateway_state has pid {gateway_state.get('pid')} but process is dead"))
        if not gateway_state:
            diagnostics.append(FleetDiagnostic("gateway_state_missing", "no gateway_state.json"))

    status.session_count = gateway_state.get("active_agents", 0) if gateway_state else 0

    # ── working: recent non-terminal run assigned to this agent ──
    # Only consider runs started within the last 24 hours.  Stale historical
    # runs from dead processes must not be mistaken for current work.
    # Additionally require gateway active_agents > 0 for confidence.
    _CUTOFF = observed_at.timestamp() - 86400
    recent_runs = [
        r for r in runs
        if r.get("projection_type") == "Run"
        and r.get("status") == "running"
        and (r.get("started_at") or r.get("created_at") or "")
    ]
    # Filter by recency: try to parse ISO timestamp
    non_terminal = []
    for r in recent_runs:
        ts_str = r.get("started_at") or r.get("created_at") or ""
        try:
            ts = datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
            if ts.timestamp() > _CUTOFF:
                non_terminal.append(r)
        except (ValueError, TypeError):
            pass  # unparseable timestamp → skip
    for run in non_terminal:
        run_agent = run.get("agent_id", "")
        if run_agent == agent_id or (run_agent and run_agent in agent_cfg.get("aliases", [])):
            status.working = True
            status.current_task_id = run.get("task_id")
            status.current_run_id = run.get("id")
            break
    if not status.working and non_terminal:
        for run in non_terminal:
            if run.get("agent_id", "").startswith(agent_id):
                status.working = True
                status.current_task_id = run.get("task_id")
                status.current_run_id = run.get("id")
                break
    # Downgrade working confidence if gateway has no active agents
    if status.working and gateway_state and gateway_state.get("active_agents", 0) == 0:
        diagnostics.append(FleetDiagnostic("stale_run",
            "non-terminal Run exists but gateway reports 0 active agents"))

    # ── error: timeout diagnostics or Kanban failures ──
    diag_dir = _DAIGNOSTIC_DELEGATE_TIMEOUT_DIR
    if diag_dir.is_dir():
        cutoff = observed_at.timestamp() - _ERROR_WINDOW_SECONDS
        for f in diag_dir.iterdir():
            if f.name.startswith("delegate_timeout_") and f.stat().st_mtime > cutoff:
                status.error = True
                diagnostics.append(FleetDiagnostic("delegate_timeout", f"recent timeout: {f.name}"))
                break

    # ── today stats ──
    today_runs = [r for r in runs
                  if r.get("projection_type") in ("Run", "DomainEventEnvelope")
                  and r.get("status") in ("completed", "done", "running")]
    # Count unique tasks by task_id
    today_task_ids = set()
    for r in today_runs:
        tid = r.get("task_id")
        if tid:
            today_task_ids.add(tid)
    status.today_task_count = len(today_task_ids)
    # Cost: sum from runs that have cost data
    total_cost = 0.0
    has_cost = False
    for r in today_runs:
        cost = r.get("cost_usd") or (r.get("payload", {}) if isinstance(r.get("payload"), dict) else {}).get("cost_usd")
        if cost is not None:
            try:
                total_cost += float(cost)
                has_cost = True
            except (TypeError, ValueError):
                pass
    status.today_cost_usd = total_cost if has_cost else None

    status.diagnostics = diagnostics
    return status


# ── Snapshot Builder ─────────────────────────────────────────────────────


def build_fleet_snapshot(
    observed_at: Optional[datetime] = None,
    managed_agents_path: Optional[str] = None,
) -> FleetSnapshot:
    if observed_at is None:
        observed_at = _now_utc()
    today_start = _today_shanghai_start()

    # Read sources
    agents_cfg, config_diags = _read_managed_agents(managed_agents_path)
    gateway_state, gw_diags = _read_gateway_state()
    pid_alive = _verify_pid(gateway_state["pid"]) if gateway_state and gateway_state.get("pid") else False
    proj_data = _load_projection()
    runs = proj_data.get("records", [])

    # Compute per-agent status
    fleet_agents: List[FleetAgentStatus] = []
    for cfg in agents_cfg:
        fleet_agents.append(_compute_agent_status(
            cfg, gateway_state, pid_alive, runs, observed_at, today_start,
        ))

    # Sort deterministic
    fleet_agents.sort(key=lambda a: a.fleet_agent_id)

    # Unassigned
    delegate_runs = [r for r in runs if "delegate" in str(r.get("task_id", ""))]
    unassigned: Dict[str, Any] = {
        "unassigned_delegate_runs": len(delegate_runs),
        "unassigned_kanban_assignees": [],
    }

    # Summary
    summary = {
        "total": len(fleet_agents),
        "online": sum(1 for a in fleet_agents if a.status == "online"),
        "idle": sum(1 for a in fleet_agents if a.status == "idle"),
        "offline": sum(1 for a in fleet_agents if a.status == "offline"),
        "working": sum(1 for a in fleet_agents if a.working),
        "error": sum(1 for a in fleet_agents if a.error),
    }

    all_diags = list(config_diags) + list(gw_diags)

    return FleetSnapshot(
        schema_version=_SCHEMA_VERSION,
        observed_at=observed_at.isoformat(),
        source_watermark={
            "gateway_state_updated_at": gateway_state.get("updated_at") if gateway_state else None,
            "gateway_pid_alive": pid_alive,
        },
        agents=fleet_agents,
        unassigned=unassigned,
        summary=summary,
        diagnostics=all_diags,
    )


def write_snapshot(snapshot: FleetSnapshot, output_path: str) -> None:
    """Atomically write FleetSnapshot as JSON."""
    opath = Path(output_path)
    opath.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_hex(8)
    tmp = opath.parent / f"{opath.name}.tmp.{os.getpid()}.{token}"
    try:
        tmp.write_text(
            json.dumps(asdict(snapshot), ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        tmp.replace(opath)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


# ── CLI ──────────────────────────────────────────────────────────────────


def main(argv=None):
    parser = argparse.ArgumentParser(description="Agent Fleet Status Builder (Phase 5B)")
    parser.add_argument("--output", default=_OUTPUT_DEFAULT, help="FleetSnapshot output path")
    parser.add_argument("--managed-agents", default=None, help="Path to managed-agents.yaml")
    args = parser.parse_args(argv)

    snapshot = build_fleet_snapshot(managed_agents_path=args.managed_agents)
    write_snapshot(snapshot, args.output)
    print(f"FleetSnapshot: {snapshot.summary['total']} agents, "
          f"{snapshot.summary['online']} online, "
          f"{snapshot.summary['working']} working, "
          f"{snapshot.summary['error']} error")
    print(f"Written: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
