import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_dispatch_default_ledger_uses_task_project(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    dispatch = _load_script("dispatch_task", ROOT / "scripts" / "dispatch-task.py")

    inbox = tmp_path / "scratch" / "inbox" / "task.json"
    task_card = {"project": "staam", "task_card_id": "custom_task"}

    assert dispatch.default_run_ledger_path(task_card, inbox) == (
        tmp_path / ".claude" / "teams" / "staam" / "runs" / "ledger.jsonl"
    )


def test_dispatch_default_ledger_infers_project_from_output_contract(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    dispatch = _load_script("dispatch_task_output_contract", ROOT / "scripts" / "dispatch-task.py")

    inbox = tmp_path / "scratch" / "inbox" / "task.json"
    task_card = {
        "task_card_id": "custom_task",
        "output_contract": {
            "path": str(tmp_path / ".claude" / "teams" / "research" / "outbox" / "custom_task_result.json")
        },
    }

    assert dispatch.default_run_ledger_path(task_card, inbox) == (
        tmp_path / ".claude" / "teams" / "research" / "runs" / "ledger.jsonl"
    )


def test_dispatch_default_ledger_falls_back_to_inbox_team_for_unowned_task(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    dispatch = _load_script("dispatch_task_fallback", ROOT / "scripts" / "dispatch-task.py")

    inbox = tmp_path / "scratch" / "inbox" / "task.json"
    task_card = {"task_card_id": "customtask"}

    assert dispatch.default_run_ledger_path(task_card, inbox) == (
        tmp_path / "scratch" / "runs" / "ledger.jsonl"
    )


def test_dispatch_rejects_traversal_project_for_default_ledger(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    dispatch = _load_script("dispatch_task_invalid_project", ROOT / "scripts" / "dispatch-task.py")

    inbox = tmp_path / "scratch" / "inbox" / "task.json"
    task_card = {"project": "../escape", "task_card_id": "custom_task"}

    assert dispatch.default_run_ledger_path(task_card, inbox) == (
        tmp_path / "scratch" / "runs" / "ledger.jsonl"
    )


def test_gate_default_ledger_uses_task_project_without_event_log(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    gate = _load_script("run_task_gate", ROOT / "scripts" / "run-task-gate.py")

    inbox = tmp_path / "scratch" / "inbox" / "task.json"
    inbox.parent.mkdir(parents=True)
    inbox.write_text(json.dumps({"project": "staam", "task_card_id": "custom_task"}), encoding="utf-8")

    assert gate.default_run_ledger_path(inbox) == (
        tmp_path / ".claude" / "teams" / "staam" / "runs" / "ledger.jsonl"
    )


def test_gate_default_ledger_prefers_event_log_location(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    gate = _load_script("run_task_gate_event_log", ROOT / "scripts" / "run-task-gate.py")

    inbox = tmp_path / "scratch" / "inbox" / "task.json"
    event_log = tmp_path / "explicit-team" / "events.jsonl"
    inbox.parent.mkdir(parents=True)
    inbox.write_text(json.dumps({"project": "staam", "task_card_id": "custom_task"}), encoding="utf-8")

    assert gate.default_run_ledger_path(inbox, event_log) == (
        tmp_path / "explicit-team" / "runs" / "ledger.jsonl"
    )


def test_run_ledger_lifecycle_event_append(tmp_path: Path) -> None:
    ledger = _load_script("run_ledger_lifecycle", ROOT / "scripts" / "run-ledger.py")

    path = tmp_path / "team" / "runs" / "ledger.jsonl"
    event_id = ledger.append_lifecycle_event(
        path,
        task_id="task_life",
        phase="gate_checked",
        status="approved",
        agent_id="codex",
        run_id="run_real_dispatch",
        decision="approved",
    )

    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert event_id.startswith("life_task_life_")
    assert rows[0]["event"] == "lifecycle_event"
    assert rows[0]["run_id"] == event_id
    assert rows[0]["task_id"] == "task_life"
    assert rows[0]["phase"] == "gate_checked"
    assert rows[0]["status"] == "approved"
    assert rows[0]["decision"] == "approved"
    assert rows[0]["run_id"] == event_id
    assert rows[0]["related_run_id"] == "run_real_dispatch"


def test_compile_lifecycle_writes_project_run_ledger(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_HOME", str(ROOT))
    compile_task = _load_script("compile_task_lifecycle", ROOT / "scripts" / "compile-task.py")

    task_card = {
        "project": "staam",
        "task_card_id": "task_compiled",
        "execution_plan": {"primary_agent": "claude-code"},
        "output_contract": {"path": "/tmp/task_compiled_result.json"},
    }
    inbox_path = tmp_path / ".claude" / "teams" / "staam" / "inbox" / "task_compiled.json"

    compile_task.append_compile_lifecycle(task_card, inbox_path)

    ledger_path = tmp_path / ".claude" / "teams" / "staam" / "runs" / "ledger.jsonl"
    rows = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["event"] == "lifecycle_event"
    assert rows[0]["phase"] == "compiled"
    assert rows[0]["task_id"] == "task_compiled"
    assert rows[0]["primary_agent"] == "claude-code"


def test_compile_rejects_invalid_project_name() -> None:
    compile_task = _load_script("compile_task", ROOT / "scripts" / "compile-task.py")

    for project in ("", "../escape", "nested/team", ".", ".."):
        try:
            compile_task.validate_project_name(project)
        except ValueError:
            continue
        raise AssertionError(f"project should be invalid: {project!r}")
