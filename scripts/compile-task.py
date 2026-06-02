#!/usr/bin/env python3
"""
v2.8 Task Card 组装器 (compile-task.py)

职责：将 Hermes 编译后的意图 + 记忆库 + Agent Registry 合并为完整 Task Card。
注意：意图编译（LLM 判断）由 Hermes Chief of Staff 完成，本脚本只做数据层组装。

用法:
  # 从意图文件组装 Task Card
  compile-task.py --intent intent.json --project staam --output task_card.json

  # 从原始请求生成初始 Task Card（意图字段留空，待 Hermes 填充）
  compile-task.py --request "原始请求" --project staam --output task_card.json

  # 只生成文件，不写入真实 inbox 队列
  compile-task.py --request "原始请求" --project staam --output task_card.json --no-inbox

  # 从 stdin 读取意图 JSON
  echo '{"raw_request":"...","interpreted_intent":"..."}' | compile-task.py --intent - --project staam
"""

import argparse
import importlib.util
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
MEMORIES_DIR = HERMES_HOME / "memories"
CONFIG_DIR = HERMES_HOME / "config"
TEAMS_DIR = Path.home() / ".claude" / "teams"
RUN_LEDGER_SCRIPT = HERMES_HOME / "scripts" / "run-ledger.py"


def load_json(path: Path) -> dict:
    """加载 JSON 文件，不存在时返回空字典，格式错误时打印警告。"""
    try:
        with open(path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        print(f"警告: JSON 解析失败 {path}: {e}", file=sys.stderr)
        return {}


def validate_project_name(project: str) -> str:
    name = str(project or "").strip()
    if not name or "/" in name or "\\" in name or name in {".", ".."}:
        raise ValueError(f"invalid project name: {project!r}")
    return name


def load_run_ledger():
    spec = importlib.util.spec_from_file_location("hermes_run_ledger", RUN_LEDGER_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def append_compile_lifecycle(task_card: dict, inbox_path: Optional[Path] = None) -> None:
    try:
        project = validate_project_name(task_card.get("project") or "staam")
        task_id = task_card.get("task_card_id") or task_card.get("task_id") or "unknown"
        ledger = load_run_ledger()
        ledger.append_lifecycle_event(
            TEAMS_DIR / project / "runs" / "ledger.jsonl",
            task_id=task_id,
            phase="compiled",
            status="completed",
            agent_id="codex",
            run_type="compile",
            message="Task card compiled",
            project=project,
            inbox_path=str(inbox_path) if inbox_path else None,
            outbox_path=(task_card.get("output_contract") or {}).get("path"),
            primary_agent=(task_card.get("execution_plan") or {}).get("primary_agent"),
        )
    except Exception:
        return


def load_user_preferences() -> dict:
    return load_json(MEMORIES_DIR / "user-preferences.json")


def load_project_context(project: str) -> dict:
    all_contexts = load_json(MEMORIES_DIR / "project-context.json")
    project_data = all_contexts.get("projects", {}).get(project, {})
    global_rules = all_contexts.get("_global_must_avoid", [])
    return {
        "project": project,
        "project_data": project_data,
        "global_must_avoid": global_rules
    }


def load_feedback_memory() -> dict:
    return load_json(MEMORIES_DIR / "feedback-memory.json")


def load_agent_registry() -> dict:
    return load_json(CONFIG_DIR / "agent-registry.json")


# Intent Card 格式所需字段（来自 chief-of-staff SKILL.md）
INTENT_REQUIRED_FIELDS = [
    "raw_request", "interpreted_intent", "surface_task", "real_task",
    "task_category", "subjectivity_level", "risk_level",
    "must_keep", "must_change", "must_avoid", "success_criteria",
    "preferred_agent", "task_type", "domain"
]

INTENT_VALID_VALUES = {
    "subjectivity_level": {"low", "medium", "high"},
    "risk_level": {"low", "medium", "high"},
    "task_category": {"code", "content", "data", "creative", "admin", "communication", "research", ""},
    "task_type": {"simple", "single-agent", "multi-agent", ""},
    "domain": {"code", "content", "data", "creative", "admin", ""},
}


def validate_compiled_intent(ci: dict, source: str = "intent file") -> list:
    """验证 compiled_intent 的 schema 完整性。返回问题列表。"""
    issues = []

    # 检查原始请求模式（允许最小意图，跳过严格验证）
    ambiguities = ci.get("ambiguities", [])
    if any("尚未编译" in str(a) for a in ambiguities):
        return issues  # --request 模式，跳过验证

    # 检查必填字段
    for field in INTENT_REQUIRED_FIELDS:
        if field not in ci:
            issues.append(f"缺少必填字段: {field}")
        elif ci[field] is None:
            issues.append(f"必填字段为 null: {field}")

    # 检查枚举字段
    for field, valid in INTENT_VALID_VALUES.items():
        val = ci.get(field, "")
        if val and val not in valid:
            issues.append(f"{field} 值 '{val}' 不在有效范围: {valid}")

    # 检查数组字段
    for arr_field in ["must_keep", "must_change", "must_avoid", "success_criteria"]:
        if arr_field in ci and not isinstance(ci[arr_field], list):
            issues.append(f"{arr_field} 应为数组，实际为 {type(ci[arr_field]).__name__}")

    # 检查 confidence
    conf = ci.get("confidence")
    if conf is not None and not isinstance(conf, (int, float)):
        issues.append(f"confidence 应为数字，实际为 {type(conf).__name__}")

    if issues:
        print(f"警告: {source} 存在 {len(issues)} 个 schema 问题:", file=sys.stderr)
        for issue in issues:
            print(f"  - {issue}", file=sys.stderr)

    return issues


def find_relevant_feedback(compiled_intent: dict, feedback_memory: dict) -> list:
    """从反馈记忆中查找与当前任务相关的历史规则。"""
    task_category = compiled_intent.get("task_category", "")
    domain = compiled_intent.get("domain", "")
    rules = feedback_memory.get("rules", [])
    relevant = []
    for rule in rules:
        apply_to = rule.get("apply_to", [])
        if not apply_to or task_category in apply_to or domain in apply_to or "all" in apply_to:
            relevant.append(rule)
    return relevant


def determine_execution_mode(compiled_intent: dict, agent_registry: dict) -> dict:
    """根据编译后的意图判断执行模式。"""
    task_type = compiled_intent.get("task_type", "simple")
    preferred = compiled_intent.get("preferred_agent", "hermes-internal")
    if preferred == "kimi":
        preferred = "deepseek-tui"
    risk = compiled_intent.get("risk_level", "low")
    subjectivity = compiled_intent.get("subjectivity_level", "low")

    # 高风险 + 高主观 → multi-agent 或人工确认
    if risk == "high" and subjectivity == "high":
        mode = "multi-agent"
    elif task_type == "multi-agent":
        mode = "multi-agent"
    elif preferred in ("claude", "deepseek-tui"):
        mode = "single-agent"
    else:
        mode = "self"

    agents = agent_registry.get("agents", {})
    primary = preferred if preferred in agents else "hermes-internal"

    # 收集 secondary agents
    secondary = []
    routing_rules = agent_registry.get("routing_rules", {})
    if mode == "multi-agent":
        if primary != "claude" and "claude" in agents:
            secondary.append("claude")
        if primary != "deepseek-tui" and "deepseek-tui" in agents:
            secondary.append("deepseek-tui")

    budget_defaults = {
        "self":         {"max_agents": 0, "max_rounds": 6,  "max_revisions": 0},
        "single-agent": {"max_agents": 1, "max_rounds": 12, "max_revisions": 1},
        "multi-agent":  {"max_agents": 3, "max_rounds": 20, "max_revisions": 2},
    }
    b = budget_defaults.get(mode, budget_defaults["self"])
    budget = {
        "max_agents": b["max_agents"],
        "max_rounds": b["max_rounds"],
        "max_revisions": b["max_revisions"],
        "max_duration_seconds": None,
        "max_child_duration_seconds": None,
        "max_files_changed": None,
        "max_lines_changed": None,
    }

    return {
        "mode": mode,
        "primary_agent": primary,
        "secondary_agents": secondary,
        "delegation_reason": f"risk={risk}, subjectivity={subjectivity}, preferred={preferred}",
        "estimated_subtasks": 1 if mode != "multi-agent" else len(secondary) + 1,
        "budget": budget,
    }


def build_acceptance_criteria(compiled_intent: dict, project_context: dict) -> dict:
    """从意图和项目上下文构建验收条件。"""
    auto = [
        "changed files must be within allowed_files",
        "outbox must contain all required fields"
    ]
    human = []
    evidence = [
        "changed_files",
        "verification_commands",
        "verification_output_summary",
        "known_risks"
    ]

    success_criteria = compiled_intent.get("success_criteria", [])
    for sc in success_criteria:
        if "test" in sc.lower() or "lint" in sc.lower() or "error" in sc.lower():
            auto.append(sc)
        else:
            human.append(sc)

    must_avoid = compiled_intent.get("must_avoid", [])
    project_data = project_context.get("project_data", {})
    project_must_avoid = project_data.get("must_avoid", [])
    all_must_avoid = must_avoid + project_must_avoid + project_context.get("global_must_avoid", [])
    for item in all_must_avoid:
        human.append(f"确认未违反: {item}")

    return {
        "auto_checkable": auto,
        "human_review": human,
        "evidence_required": evidence
    }


def extract_allowed_files(compiled_intent: dict, project_context: dict) -> list:
    """从意图中提取允许修改的文件列表。"""
    files = compiled_intent.get("allowed_files", [])
    if not files:
        relevant = compiled_intent.get("relevant_files", [])
        files = relevant
    if not files:
        project_data = project_context.get("project_data", {})
        files = project_data.get("key_files", [])
    # Expand ~ to home directory
    return [os.path.expanduser(f) for f in files]


def build_task_card(
    compiled_intent: dict,
    project: str = "staam",
    task_card_id: Optional[str] = None
) -> dict:
    """组装完整 Task Card。"""

    user_prefs = load_user_preferences()
    project_ctx = load_project_context(project)
    feedback_mem = load_feedback_memory()
    registry = load_agent_registry()

    # 如果没有提供 task_card_id，自动生成
    if task_card_id is None:
        now = datetime.now(timezone.utc)
        seq = now.strftime("%Y%m%d_%H%M%S_%f")
        task_card_id = f"{project}_{seq}"

    execution_plan = determine_execution_mode(compiled_intent, registry)
    acceptance_criteria = build_acceptance_criteria(compiled_intent, project_ctx)
    allowed_files = extract_allowed_files(compiled_intent, project_ctx)
    relevant_feedback = find_relevant_feedback(compiled_intent, feedback_mem)

    # 提取项目上下文中与当前任务相关的偏好
    relevant_prefs = {}
    work_style = user_prefs.get("work_style", {})
    relevant_prefs["work_style"] = {k: v for k, v in work_style.items() if not k.startswith("_")}
    # interaction_preferences 始终包含（所有任务都需要）
    interaction = user_prefs.get("interaction_preferences", {})
    relevant_prefs["interaction"] = {k: v for k, v in interaction.items() if not k.startswith("_")}

    task_category = compiled_intent.get("task_category", "")
    if task_category in ("creative", "content", "visual"):
        visual_prefs = user_prefs.get("visual_preferences", {})
        relevant_prefs["visual"] = {k: v for k, v in visual_prefs.items() if not k.startswith("_")}
    if task_category in ("strategy", "analysis", "decision"):
        strategy_prefs = user_prefs.get("strategy_preferences", {})
        relevant_prefs["strategy"] = {k: v for k, v in strategy_prefs.items() if not k.startswith("_")}

    primary_agent = execution_plan["primary_agent"]
    team = project
    inbox_path = os.path.expanduser(
        f"~/.claude/teams/{team}/inbox/{task_card_id}.json"
    )
    outbox_path = os.path.expanduser(
        f"~/.claude/teams/{team}/outbox/{task_card_id}_result.json"
    )
    review_record_path = os.path.expanduser(
        f"~/.claude/teams/{team}/review/{task_card_id}_gate.json"
    )
    event_log_path = os.path.expanduser(
        f"~/.claude/teams/{team}/events.jsonl"
    )
    task_index_path = os.path.expanduser(
        f"~/.claude/teams/{team}/tasks/index.jsonl"
    )
    gate_runner = HERMES_HOME / "scripts" / "run-task-gate.py"
    dispatch_runner = HERMES_HOME / "scripts" / "dispatch-task.py"
    hermes_python = HERMES_HOME / "hermes-agent" / "venv" / "bin" / "python"

    task_card = {
        "schema_version": "2.8",
        "task_card_id": task_card_id,
        "project": project,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "created",

        "goal": compiled_intent.get("real_task") or compiled_intent.get("interpreted_intent") or compiled_intent.get("raw_request") or compiled_intent.get("raw_user_request", ""),
        "compiled_intent": compiled_intent,

        "context": {
            "user_preferences": relevant_prefs,
            "project_context": {
                "name": project_ctx.get("project", project),
                "data": project_ctx.get("project_data", {}),
                "global_must_avoid": project_ctx.get("global_must_avoid", [])
            },
            "relevant_feedback": relevant_feedback
        },

        "execution_plan": execution_plan,

        "acceptance_criteria": acceptance_criteria,
        "allowed_files": allowed_files,

        "safety": {
            "allowed_paths": [os.path.dirname(f) if os.path.dirname(f) else "." for f in allowed_files] if allowed_files else ["."],
            "denied_commands": ["rm -rf", "sudo", "curl | sh", "chmod -R", "git push --force"]
        },

        "output_contract": {
            "path": outbox_path,
            "format": "json",
            "schema": "templates/outbox_v2_8.json",
            "dispatch": {
                "required": True,
                "runner": str(dispatch_runner),
                "command": f"{hermes_python} {dispatch_runner} --inbox {inbox_path}",
            },
            "post_outbox_gate": {
                "required": True,
                "runner": str(gate_runner),
                "policy_runner": str(HERMES_HOME / "scripts" / "gate-policy.py"),
                "policy_schema": "templates/gate_policy_v2_8.json",
                "record_path": review_record_path,
                "command": (
                    f"{hermes_python} {gate_runner} "
                    f"--inbox {inbox_path} "
                    f"--outbox {outbox_path} "
                    f"--output {review_record_path} "
                    f"--event-log {event_log_path} "
                    f"--task-index {task_index_path} "
                    "--summary "
                    "--create-revision-inbox"
                ),
                "decisions": ["approved", "revision_needed", "rejected"]
            }
        },

        "review_gate_criteria": {
            "must_match_real_intent": compiled_intent.get("real_task", ""),
            "must_avoid": compiled_intent.get("must_avoid", []),
            "user_style_check": user_prefs.get("quality_preferences", {})
        }
    }

    return task_card


def main():
    parser = argparse.ArgumentParser(
        description="v2.8 Task Card 组装器 — 合并意图 + 记忆库 + Agent Registry 为完整 Task Card"
    )
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--intent", type=str, help="意图 JSON 文件路径（'-' 表示 stdin）")
    input_group.add_argument("--request", type=str, help="原始用户请求（意图字段留空，待 Hermes 填充）")
    parser.add_argument("--project", type=str, default="staam", help="项目名（默认: staam）")
    parser.add_argument("--task-id", type=str, default=None, help="Task Card ID（默认自动生成）")
    parser.add_argument("--output", type=str, help="输出文件路径（默认 stdout）")
    parser.add_argument("--no-inbox", action="store_true", help="只写 --output，不同步写入 ~/.claude/teams/<project>/inbox")

    args = parser.parse_args()

    # 加载或创建意图
    if args.intent:
        if args.intent == "-":
            compiled_intent = json.load(sys.stdin)
        else:
            compiled_intent = load_json(Path(os.path.expanduser(args.intent)))
        if not compiled_intent:
            print("错误: 意图文件为空或无效", file=sys.stderr)
            sys.exit(1)
        # 验证 schema
        issues = validate_compiled_intent(compiled_intent, args.intent if args.intent != "-" else "stdin")
        if issues:
            print(f"共 {len(issues)} 个 schema 问题，继续组装（下游工具可能失败）", file=sys.stderr)
    else:
        # --request 模式：创建最小意图，待 Hermes 填充
        compiled_intent = {
            "schema_version": "2.8",
            "raw_request": args.request,
            "interpreted_intent": "",
            "surface_task": "",
            "real_task": args.request,
            "task_category": "",
            "subjectivity_level": "medium",
            "risk_level": "low",
            "task_type": "simple",
            "domain": "",
            "assumptions": [],
            "must_keep": [],
            "must_change": [],
            "must_avoid": [],
            "success_criteria": [],
            "ambiguities": ["意图尚未编译，此为原始请求"],
            "preferred_agent": "",
            "reasoning": "Intent not yet compiled by Chief of Staff"
        }

    try:
        project = validate_project_name(args.project)
    except ValueError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        sys.exit(2)

    task_card = build_task_card(
        compiled_intent,
        project=project,
        task_card_id=args.task_id
    )

    if args.output:
        output_path = Path(os.path.expanduser(args.output))
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            print(f"错误: 无法创建输出目录 {output_path.parent}: {e}", file=sys.stderr)
            sys.exit(1)
        with open(output_path, "w") as f:
            json.dump(task_card, f, ensure_ascii=False, indent=2)
        print(f"Task Card: {output_path}")
        if not args.no_inbox:
            # 同时写入 inbox
            team = project
            inbox_dir = TEAMS_DIR / team / "inbox"
            try:
                inbox_dir.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                print(f"错误: 无法创建 inbox 目录 {inbox_dir}: {e}", file=sys.stderr)
                sys.exit(1)
            inbox_path = inbox_dir / f"{task_card['task_card_id']}.json"
            with open(inbox_path, "w") as f:
                json.dump(task_card, f, ensure_ascii=False, indent=2)
            append_compile_lifecycle(task_card, inbox_path)
            print(f"Inbox:     {inbox_path}")
        else:
            append_compile_lifecycle(task_card, None)
    else:
        json.dump(task_card, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write('\n')
        append_compile_lifecycle(task_card, None)


if __name__ == "__main__":
    main()
