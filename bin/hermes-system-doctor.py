#!/usr/bin/env python3
"""Hermes system doctor.

This script is intentionally conservative:
- logs are treated as historical signals, not current failures;
- current failures require a live check or a machine-readable config mismatch;
- secrets are never printed.
"""

from __future__ import annotations

import argparse
import datetime as dt
import http.client
import json
import os
import socket
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml
except Exception:  # pragma: no cover - handled at runtime
    yaml = None


ROOT = Path.home() / ".hermes"
AGENT_ROOT = ROOT / "hermes-agent"


@dataclass
class Check:
    name: str
    status: str
    detail: str
    evidence: str
    command: str


def _now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def _read_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def _load_yaml(path: Path) -> Any:
    if yaml is None:
        raise RuntimeError("PyYAML is not available")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True, timeout=10)


def _file_chars(path: Path) -> int:
    if not path.exists():
        return 0
    return len(path.read_text(encoding="utf-8", errors="replace"))


def _can_connect(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _http_status(path: str, key: str | None = None) -> int | None:
    try:
        conn = http.client.HTTPConnection("127.0.0.1", 8642, timeout=3)
        headers = {}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        conn.request("GET", path, headers=headers)
        resp = conn.getresponse()
        resp.read()
        conn.close()
        return resp.status
    except OSError:
        return None


def check_memory(config: dict[str, Any]) -> Check:
    mem_cfg = config.get("memory") if isinstance(config.get("memory"), dict) else {}
    memory_limit = int(mem_cfg.get("memory_char_limit") or 3000)
    user_limit = int(mem_cfg.get("user_char_limit") or 1375)
    memory_path = ROOT / "memories" / "MEMORY.md"
    user_path = ROOT / "memories" / "USER.md"
    legacy_user_path = ROOT / "memories" / "user-profile.md"
    memory_chars = _file_chars(memory_path)
    user_chars = _file_chars(user_path)
    legacy_chars = _file_chars(legacy_user_path)

    status = "OK"
    problems = []
    if memory_chars == 0:
        problems.append("MEMORY.md is empty")
    if user_chars == 0:
        problems.append("USER.md is empty")
    if memory_chars > memory_limit:
        problems.append(f"MEMORY.md exceeds limit {memory_chars}/{memory_limit}")
    if user_chars > user_limit:
        problems.append(f"USER.md exceeds limit {user_chars}/{user_limit}")
    if problems:
        status = "WARN"

    detail = (
        f"MEMORY.md={memory_chars}/{memory_limit} chars; "
        f"USER.md={user_chars}/{user_limit} chars; "
        f"user-profile.md legacy/extra={legacy_chars} chars"
    )
    if problems:
        detail += "; " + "; ".join(problems)
    return Check(
        "Built-in memory",
        status,
        detail,
        "authoritative files: ~/.hermes/memories/MEMORY.md and ~/.hermes/memories/USER.md",
        "wc -m ~/.hermes/memories/MEMORY.md ~/.hermes/memories/USER.md",
    )


def check_processes() -> Check:
    proc = _run(["ps", "aux"])
    text = proc.stdout
    expected = {
        "gateway": "hermes_cli.main gateway run",
        "dashboard_9119": "hermes_cli.main dashboard --port 9119",
        "openchronicle": "openchronicle start",
        "codegraph_mcp": "codegraph.js serve --mcp",
    }
    missing = [name for name, needle in expected.items() if needle not in text]
    status = "OK" if not missing else "WARN"
    detail = "running: " + ", ".join(name for name in expected if name not in missing)
    if missing:
        detail += "; missing: " + ", ".join(missing)
    return Check(
        "Core processes",
        status,
        detail,
        "process table",
        "ps aux | rg 'hermes_cli.main gateway|dashboard --port 9119|openchronicle start|codegraph.js serve --mcp'",
    )


def check_ports() -> Check:
    ports = {
        "api_server": 8642,
        "dashboard": 9119,
        "openchronicle": 8742,
        "clash_proxy": 7890,
    }
    states = {name: _can_connect("127.0.0.1", port) for name, port in ports.items()}
    missing = [f"{name}:{ports[name]}" for name, ok in states.items() if not ok and name != "clash_proxy"]
    optional_missing = [f"{name}:{ports[name]}" for name, ok in states.items() if not ok and name == "clash_proxy"]
    status = "OK" if not missing else "WARN"
    detail = ", ".join(f"{name}:{ports[name]}={'open' if ok else 'closed'}" for name, ok in states.items())
    if optional_missing:
        detail += "; optional closed: " + ", ".join(optional_missing)
    return Check(
        "Local ports",
        status,
        detail,
        "127.0.0.1 TCP connect",
        "python socket.create_connection for 8642/9119/8742/7890",
    )


def check_api_auth(env: dict[str, str]) -> Check:
    key = env.get("API_SERVER_KEY") or os.getenv("API_SERVER_KEY")
    no_key_status = _http_status("/v1/models")
    keyed_status = _http_status("/v1/models", key) if key else None
    if no_key_status is None:
        status = "WARN"
        detail = "API server not reachable on 127.0.0.1:8642"
    elif not key:
        status = "WARN"
        detail = f"API server reachable but API_SERVER_KEY is not configured; no-key status={no_key_status}"
    elif no_key_status == 401 and keyed_status == 200:
        status = "OK"
        detail = "auth enforced: no-key=401, keyed=200"
    else:
        status = "FAIL"
        detail = f"unexpected auth behavior: no-key={no_key_status}, keyed={keyed_status}"
    return Check(
        "API server auth",
        status,
        detail,
        "~/.hermes/.env API_SERVER_KEY and live /v1/models call",
        "curl -i http://127.0.0.1:8642/v1/models; curl -H 'Authorization: Bearer <redacted>' ...",
    )


def _registry_profile(agent: dict[str, Any]) -> dict[str, Any]:
    profile = agent.get("subagent_profile")
    return profile if isinstance(profile, dict) else {}


def check_agents_and_models() -> list[Check]:
    registry_path = ROOT / "config" / "agent-registry.json"
    agents_path = AGENT_ROOT / "configs" / "managed_agents" / "agents.yaml"
    mirror_path = ROOT / "config" / "managed-agents.yaml"
    models_path = ROOT / "config" / "models.yaml"
    if not registry_path.exists() or not agents_path.exists() or not models_path.exists():
        return [
            Check(
                "Agent/model config",
                "FAIL",
                "one or more authoritative files are missing",
                f"{registry_path}, {agents_path}, {models_path}",
                "test -f <path>",
            )
        ]

    registry = _load_json(registry_path)
    agents_yaml = _load_yaml(agents_path)
    models_yaml = _load_yaml(models_path)
    registry_agents = registry.get("agents") if isinstance(registry.get("agents"), dict) else {}
    yaml_agents_list = agents_yaml.get("agents") if isinstance(agents_yaml.get("agents"), list) else []
    yaml_agents = {str(a.get("agent_id")): a for a in yaml_agents_list if isinstance(a, dict)}
    models = models_yaml.get("models") if isinstance(models_yaml.get("models"), dict) else {}

    checks: list[Check] = []
    if mirror_path.exists():
        mirror_yaml = _load_yaml(mirror_path)
        mirror_agents_list = mirror_yaml.get("agents") if isinstance(mirror_yaml.get("agents"), list) else []
        mirror_agents = {str(a.get("agent_id")): a for a in mirror_agents_list if isinstance(a, dict)}
        missing_in_mirror = sorted(set(yaml_agents) - set(mirror_agents))
        extra_in_mirror = sorted(set(mirror_agents) - set(yaml_agents))
        checks.append(
            Check(
                "Managed agents mirror",
                "OK" if agents_yaml == mirror_yaml else "FAIL",
                (
                    "config/managed-agents.yaml mirrors agents.yaml"
                    if agents_yaml == mirror_yaml
                    else (
                        f"mirror drift: source={len(yaml_agents)} agents; "
                        f"mirror={len(mirror_agents)} agents"
                        + (f"; missing_in_mirror={missing_in_mirror}" if missing_in_mirror else "")
                        + (f"; extra_in_mirror={extra_in_mirror}" if extra_in_mirror else "")
                    )
                ),
                f"{agents_path} and {mirror_path}",
                "cmp hermes-agent/configs/managed_agents/agents.yaml config/managed-agents.yaml",
            )
        )
    else:
        checks.append(
            Check(
                "Managed agents mirror",
                "WARN",
                "config/managed-agents.yaml mirror is missing; runtime source still exists",
                f"{agents_path} and {mirror_path}",
                "cp hermes-agent/configs/managed_agents/agents.yaml config/managed-agents.yaml",
            )
        )
    missing_in_yaml = sorted(set(registry_agents) - set(yaml_agents))
    missing_in_registry = sorted(set(yaml_agents) - set(registry_agents))
    checks.append(
        Check(
            "Agent registry coverage",
            "OK" if not missing_in_yaml and not missing_in_registry else "FAIL",
            (
                f"registry={len(registry_agents)} agents; agents.yaml={len(yaml_agents)} agents"
                + (f"; missing_in_yaml={missing_in_yaml}" if missing_in_yaml else "")
                + (f"; missing_in_registry={missing_in_registry}" if missing_in_registry else "")
            ),
            f"{registry_path} and {agents_path}",
            "python compare agent IDs in agent-registry.json and agents.yaml",
        )
    )

    mismatches: list[str] = []
    unknown_refs: list[str] = []
    deprecated_refs: list[str] = []
    for agent_id in sorted(set(registry_agents) & set(yaml_agents)):
        reg_agent = registry_agents[agent_id]
        yaml_agent = yaml_agents[agent_id]
        profile = _registry_profile(reg_agent)
        comparisons = [
            ("model_ref", reg_agent.get("model_ref") or profile.get("model_ref"), yaml_agent.get("model_ref")),
            ("tools", profile.get("toolsets") or [], yaml_agent.get("tools") or []),
            ("skills", profile.get("skills") or [], yaml_agent.get("skills") or []),
            ("permission", profile.get("permission_mode"), yaml_agent.get("permission")),
        ]
        for field, left, right in comparisons:
            if left != right:
                mismatches.append(f"{agent_id}.{field}")
        model_ref = str(yaml_agent.get("model_ref") or "").strip()
        if model_ref and model_ref not in models:
            unknown_refs.append(f"{agent_id}:{model_ref}")
        elif model_ref and isinstance(models.get(model_ref), dict):
            status = str(models[model_ref].get("status") or "").strip()
            if status == "deprecated":
                deprecated_refs.append(f"{agent_id}:{model_ref}")

    checks.append(
        Check(
            "Agent registry consistency",
            "OK" if not mismatches else "FAIL",
            "no field mismatches" if not mismatches else "mismatches: " + ", ".join(mismatches[:20]),
            f"{registry_path} and {agents_path}",
            "compare model_ref/toolsets/skills/permission per agent",
        )
    )
    checks.append(
        Check(
            "Agent model_refs",
            "OK" if not unknown_refs and not deprecated_refs else "FAIL",
            (
                "all agent model_ref values exist and are not deprecated"
                if not unknown_refs and not deprecated_refs
                else f"unknown={unknown_refs}; deprecated={deprecated_refs}"
            ),
            f"{agents_path} and {models_path}",
            "resolve every agents.yaml model_ref in config/models.yaml",
        )
    )
    return checks


def check_logs() -> Check:
    log_dir = ROOT / "logs"
    files = sorted(log_dir.glob("gateway*.log")) + sorted(log_dir.glob("errors.log"))
    if not files:
        return Check("Historical log signals", "OK", "no gateway/errors logs found", str(log_dir), "ls ~/.hermes/logs")
    patterns = {
        "auth": ("401", "Bad credentials", "AuthenticationError"),
        "opencode_404": ("opencode", "HTTP 404"),
        "playwright_missing": ("Executable doesn't exist", "ms-playwright"),
        "api_key_warning": ("No API key configured", "API_SERVER_KEY"),
    }
    counts = {name: 0 for name in patterns}
    for path in files[-5:]:
        tail = path.read_text(encoding="utf-8", errors="replace").splitlines()[-500:]
        joined = "\n".join(tail)
        for name, needles in patterns.items():
            if all(needle in joined for needle in needles):
                counts[name] += 1
    signals = [f"{k}={v}" for k, v in counts.items() if v]
    detail = "no matching historical signals in latest log tails" if not signals else "historical signals only: " + ", ".join(signals)
    return Check(
        "Historical log signals",
        "STALE" if signals else "OK",
        detail + "; logs are not treated as current faults without a live check",
        ", ".join(str(p) for p in files[-5:]),
        "tail latest gateway/errors logs and classify as historical signal",
    )


def check_git_clean() -> Check:
    proc = _run(["git", "-C", str(ROOT), "status", "--short"])
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    status = "OK" if not lines else "WARN"
    return Check(
        "Hermes config git state",
        status,
        "clean" if not lines else f"{len(lines)} changed/untracked entries",
        str(ROOT / ".git"),
        "git -C ~/.hermes status --short",
    )


def print_report(checks: list[Check]) -> int:
    order = {"FAIL": 3, "WARN": 2, "STALE": 1, "OK": 0}
    worst = max((order.get(c.status, 2) for c in checks), default=0)
    print(f"Hermes System Doctor — {_now()}")
    print(f"root: {ROOT}")
    print()
    for check in checks:
        print(f"[{check.status}] {check.name}")
        print(f"  detail: {check.detail}")
        print(f"  evidence: {check.evidence}")
        print(f"  verify: {check.command}")
    print()
    if worst >= 3:
        print("Summary: FAIL — at least one current config/live check failed.")
        return 2
    if worst >= 2:
        print("Summary: WARN — current system is usable but has warnings.")
        return 0
    if worst == 1:
        print("Summary: OK with historical signals — live checks passed; inspect logs only if symptoms recur.")
        return 0
    print("Summary: OK — live checks passed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a conservative Hermes system health check.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    args = parser.parse_args()

    env = _read_env(ROOT / ".env")
    config_path = ROOT / "config.yaml"
    config = _load_yaml(config_path) if config_path.exists() else {}

    checks: list[Check] = [
        check_processes(),
        check_ports(),
        check_api_auth(env),
        check_memory(config),
        *check_agents_and_models(),
        check_logs(),
        check_git_clean(),
    ]

    if args.json:
        print(json.dumps({"timestamp": _now(), "root": str(ROOT), "checks": [c.__dict__ for c in checks]}, ensure_ascii=False, indent=2))
        return 0
    return print_report(checks)


if __name__ == "__main__":
    sys.exit(main())
