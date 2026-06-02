import importlib.util
import json
import os
import stat
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "opencode-agent.py"


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _fake_opencode(tmp_path: Path, body: str) -> Path:
    executable = tmp_path / "opencode"
    executable.write_text(body, encoding="utf-8")
    executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
    return executable


def _run_adapter(tmp_path: Path, monkeypatch, fake_body: str, *extra_args: str) -> int:
    module = _load_script(f"opencode_agent_{len(extra_args)}")
    fake = _fake_opencode(tmp_path, fake_body)
    ledger = tmp_path / "team" / "runs" / "ledger.jsonl"
    monkeypatch.chdir(ROOT)
    monkeypatch.setattr(
        "sys.argv",
        [
            str(SCRIPT),
            "--task-id",
            "task_opencode",
            "--task",
            "Review this diff for concrete bugs.",
            "--file",
            "scripts/opencode-agent.py",
            "--cwd",
            str(ROOT),
            "--run-ledger",
            str(ledger),
            "--opencode-bin",
            str(fake),
            "--timeout",
            "2",
            *extra_args,
        ],
    )
    return module.main()


def _ledger_rows(tmp_path: Path):
    path = tmp_path / "team" / "runs" / "ledger.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_classifies_no_findings_and_records_verdict(monkeypatch, tmp_path: Path) -> None:
    fake_body = "#!/bin/sh\nprintf 'NO_FINDINGS\\n'\n"

    assert _run_adapter(tmp_path, monkeypatch, fake_body) == 0

    rows = _ledger_rows(tmp_path)
    assert "--model opencode/deepseek-v4-flash-free" in rows[0]["command"]
    assert "--agent build" in rows[0]["command"]
    assert "<prompt redacted:" in rows[0]["command"]
    assert "Output contract:" not in rows[0]["command"]
    assert rows[-1]["event"] == "lifecycle_event"
    assert rows[-1]["phase"] == "opencode_result_evaluated"
    assert rows[-1]["status"] == "no_findings"
    assert rows[-1]["agent_id"] == "opencode"
    assert rows[-1]["related_run_id"].startswith("run_task_opencode_")


def test_defaults_are_fast_narrow_review_settings() -> None:
    module = _load_script("opencode_agent_defaults")

    assert module.DEFAULT_MODEL == "opencode/deepseek-v4-flash-free"
    assert module.DEFAULT_AGENT == "build"
    assert module.DEFAULT_MAX_CONTEXT_CHARS == 5000


def test_classifies_structured_findings_as_ok(monkeypatch, tmp_path: Path) -> None:
    fake_body = (
        "#!/bin/sh\n"
        "printf 'FINDINGS:\\n"
        "- scripts/opencode-agent.py:12 | severity=P2 | issue=real bug | fix=change it\\n'\n"
    )

    assert _run_adapter(tmp_path, monkeypatch, fake_body) == 0

    rows = _ledger_rows(tmp_path)
    assert rows[-1]["status"] == "ok"


def test_classifies_unstructured_success_as_ineffective(monkeypatch, tmp_path: Path) -> None:
    fake_body = "#!/bin/sh\nprintf 'Looks good overall.\\n'\n"

    assert _run_adapter(tmp_path, monkeypatch, fake_body) == 2

    rows = _ledger_rows(tmp_path)
    assert rows[-1]["status"] == "ineffective"
    assert "did not match" in rows[-1]["message"]


def test_classifies_timeout_and_records_verdict(monkeypatch, tmp_path: Path) -> None:
    fake_body = "#!/bin/sh\nsleep 3\n"

    assert _run_adapter(tmp_path, monkeypatch, fake_body, "--timeout", "1") == 124

    rows = _ledger_rows(tmp_path)
    assert rows[-2]["event"] == "run_finished"
    assert rows[-2]["classification"] == "timeout"
    assert rows[-1]["status"] == "timeout"
    assert rows[-1]["timed_out"] is True


def test_prompt_truncates_large_diff() -> None:
    module = _load_script("opencode_agent_prompt")
    prompt = module.build_prompt(
        task_id="task",
        role="reviewer",
        files=["a.py"],
        task="review",
        diff_text="x" * 100,
        max_context_chars=20,
    )

    assert "truncated 80 chars" in prompt
    assert "Output contract:" in prompt


def test_collect_git_diff_falls_back_to_file_snapshot(tmp_path: Path) -> None:
    module = _load_script("opencode_agent_snapshot")
    target = tmp_path / "ignored.py"
    target.write_text("print('visible')\n", encoding="utf-8")

    context = module.collect_git_diff(["ignored.py"], tmp_path, 1000)

    assert "--- file snapshot: ignored.py ---" in context
    assert "print('visible')" in context


def test_process_text_decodes_timeout_bytes() -> None:
    module = _load_script("opencode_agent_text")

    assert module.process_text(b"timeout stderr") == "timeout stderr"
    assert module.process_text(None) == ""


def test_run_ledger_can_record_redacted_command(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location("run_ledger_redacted", ROOT / "scripts" / "run-ledger.py")
    ledger = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(ledger)
    path = tmp_path / "runs" / "ledger.jsonl"

    result = ledger.run_with_ledger(
        ["printf", "secret prompt"],
        ledger_path=path,
        task_id="task_redacted",
        command_for_record=["printf", "<prompt redacted>"],
    )

    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert result["classification"] == "ok"
    assert rows[0]["command"] == "printf <prompt redacted>"
    assert result["stdout"] == "secret prompt"
