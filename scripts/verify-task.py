#!/usr/bin/env python3
"""
v2.8 结构+事实验收脚本（可信闭环修复版）

读取 inbox + outbox，检查:
  1. outbox 结构和 JSON 合法性
  2. required_fields 是否齐全
  3. task_id 是否匹配
  4. changed_files 是否超出 inbox.allowed_files 范围
  5. changed_files 中的文件是否真实存在
  6. changed_files 中的文件是否实际被修改（时间戳 / changed_files_source）
  7. errors 是否为空
  8. evidence_required 是否已提交
  9. acceptance_criteria 三分类（auto_checkable / human_review / evidence_required）

v2.7 变化:
  - 支持 Task Card 格式（compiled_intent extraction with schema_version guard）
  - v2.6 三分类 acceptance_criteria 对象
  - evidence_required 项必须能在 outbox.evidence 中找到
  - 检测 format_wrapped_unverified 状态
  - changed_files_source 检查（git_diff 优先于 agent 自述）
  - 向后兼容 v2.5/v2.6 旧格式

v2.8 变化:
  - 标准任务状态机校验
  - 标准 evidence 字段校验
  - 标准错误分类 error_taxonomy 校验

输出: fail (exit 1) / needs_human_review (exit 2) / pass (exit 0)
默认输出完整 JSON；加 `--summary` 输出给主 Agent 分流用的短报告。
"""
import json
import sys
from fnmatch import fnmatch
from datetime import datetime, timezone
from pathlib import Path


HERMES_ROOT = Path(__file__).resolve().parents[1]

TASK_STATUSES = {
    "created",
    "dispatched",
    "running",
    "waiting_for_verification",
    "needs_human_review",
    "completed",
    "discarded",
    "failed",
    "blocked",
}

TERMINAL_TASK_STATUSES = {
    "completed",
    "discarded",
    "failed",
    "blocked",
}

ERROR_CODES = {
    "model_error",
    "tool_permission_error",
    "missing_api_key",
    "timeout",
    "invalid_output_schema",
    "verification_failed",
    "allowed_files_violation",
    "human_input_required",
    "runtime_error",
    "unknown_error",
}

READ_ONLY_AGENTS = {"hermes-internal", "codex", "pirlo", "ambrosini"}

STANDARD_OUTBOX_FIELDS = [
    "task_id", "agent_id", "status", "summary", "artifacts",
    "changed_files", "commands_run", "tests_run", "risks",
    "blocked_by", "error_taxonomy", "next_action",
]

VALID_OUTBOX_STATUSES = {"success", "failed", "blocked"}
VALID_NEXT_ACTIONS = {"complete", "review", "revision", "manual_review"}

STANDARD_EVIDENCE_FIELDS = {
    "changed_files",
    "verification_commands",
    "verification_output_summary",
    "known_risks",
}


def load_json(path):
    path = Path(path).expanduser()
    if not path.exists():
        return None, f"文件不存在: {path}"
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f), None
    except json.JSONDecodeError as e:
        return None, f"JSON 解析失败: {e}"
    except Exception as e:
        return None, f"读取失败: {e}"


def parse_iso_timestamp(ts_str):
    if not ts_str:
        return None
    try:
        ts_str = ts_str.replace("Z", "+00:00")
        return datetime.fromisoformat(ts_str)
    except Exception:
        return None


def normalize_file_path(path):
    candidate = Path(str(path)).expanduser()
    if not candidate.is_absolute():
        candidate = HERMES_ROOT / candidate
    return candidate.resolve(strict=False)


def is_changed_file_allowed(changed_file, allowed_file):
    changed_norm = str(normalize_file_path(changed_file))
    allowed_raw = str(allowed_file)
    allowed_norm = str(normalize_file_path(allowed_raw))

    if "*" in allowed_raw:
        return fnmatch(changed_norm, allowed_norm)

    changed_path = Path(changed_norm)
    allowed_path = Path(allowed_norm)
    if changed_path == allowed_path:
        return True
    try:
        changed_path.relative_to(allowed_path)
        return True
    except ValueError:
        return False


def check_files_exist(changed_files):
    missing = []
    for f in changed_files:
        path = normalize_file_path(f)
        if not path.exists():
            missing.append(f)
    return missing


def check_files_modified(changed_files, task_start_time):
    if not task_start_time:
        return [], "无法获取任务开始时间，跳过时间戳检查"

    not_modified = []
    for f in changed_files:
        path = normalize_file_path(f)
        if path.exists():
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            if mtime < task_start_time:
                not_modified.append(f"{f} (mtime={mtime.isoformat()}, 任务开始={task_start_time.isoformat()})")
    return not_modified, None


def schema_at_least(data, major, minor):
    raw = str(data.get("schema_version", "0") if isinstance(data, dict) else "0")
    try:
        parts = raw.split(".", 1)
        got_major = int(parts[0])
        got_minor = int(parts[1]) if len(parts) > 1 else 0
    except ValueError:
        return False
    return (got_major, got_minor) >= (major, minor)


def get_nested(data, path, default=None):
    cur = data
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def has_nested(data, path):
    cur = data
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return False, None
        cur = cur[key]
    return True, cur


def evidence_value(outbox, item_text):
    evidence = outbox.get("evidence", {})
    item = item_text.strip()
    aliases = {
        "changed_files": [
            ("changed_files",),
            ("evidence", "changed_files"),
            ("evidence", "files_modified"),
        ],
        "verification_commands": [
            ("verification_commands",),
            ("evidence", "verification_commands"),
            ("verification", "commands"),
        ],
        "verification_output_summary": [
            ("verification_output_summary",),
            ("evidence", "verification_output_summary"),
            ("verification", "output_summary"),
            ("verification", "summary"),
        ],
        "known_risks": [
            ("known_risks",),
            ("evidence", "known_risks"),
        ],
    }
    paths = aliases.get(item, [(item,), ("evidence", item)])
    for path in paths:
        found, value = has_nested(outbox, path)
        if not found:
            continue
        if item in {"changed_files", "known_risks"}:
            return {"present": True, "value": value}
        if value not in (None, "", [], {}):
            return value

    # Backward compatible fallback for old outboxes where any evidence block
    # meant "the agent attached supporting material".
    if item not in STANDARD_EVIDENCE_FIELDS and isinstance(evidence, dict):
        if evidence.get("outputs") or evidence.get("files_created") or evidence.get("files_modified"):
            return evidence
    return None


def validate_status(outbox):
    status = outbox.get("status")
    if status in TASK_STATUSES:
        return None
    return f"非法 status: {status!r}；允许值: {sorted(TASK_STATUSES)}"


def validate_error_taxonomy(outbox):
    problems = []
    taxonomy = outbox.get("error_taxonomy", [])
    errors = outbox.get("errors", [])

    if taxonomy in (None, []):
        if errors and schema_at_least(outbox, 2, 8):
            return ["errors 非空时，v2.8 outbox 必须提供 error_taxonomy"]
        return []

    if not isinstance(taxonomy, list):
        return ["error_taxonomy 必须是数组"]

    for idx, item in enumerate(taxonomy):
        if not isinstance(item, dict):
            problems.append(f"error_taxonomy[{idx}] 必须是对象")
            continue
        code = item.get("code")
        if code not in ERROR_CODES:
            problems.append(f"error_taxonomy[{idx}].code 非法: {code!r}")
        if not item.get("message"):
            problems.append(f"error_taxonomy[{idx}] 缺少 message")
        if "recoverable" in item and not isinstance(item["recoverable"], bool):
            problems.append(f"error_taxonomy[{idx}].recoverable 必须是 boolean")
    return problems


def validate_standard_outbox(outbox, inbox):
    """
    校验标准 outbox schema（v2.8 Phase 3）。
    旧格式 outbox（缺少标准字段）只输出 warnings，不报 errors。
    返回 (errors, warnings)
    """
    errors = []
    warnings = []

    # 检测是否为标准格式（含 agent_id 且含 next_action）
    is_standard = "agent_id" in outbox and "next_action" in outbox
    if not is_standard:
        missing = [f for f in STANDARD_OUTBOX_FIELDS if f not in outbox]
        if missing:
            warnings.append(f"旧格式 outbox，缺少标准字段（仅警告）: {missing}")
        return errors, warnings

    # 1. 必填字段存在性
    missing = [f for f in STANDARD_OUTBOX_FIELDS if f not in outbox]
    if missing:
        errors.append(f"标准 outbox 缺少必填字段: {missing}")

    # 2. status 必须在 {success, failed, blocked}
    status = outbox.get("status")
    if status not in VALID_OUTBOX_STATUSES:
        errors.append(f"outbox.status 非法: {status!r}；允许值: {sorted(VALID_OUTBOX_STATUSES)}")

    # 3. next_action 合法性
    next_action = outbox.get("next_action")
    if next_action not in VALID_NEXT_ACTIONS:
        errors.append(f"outbox.next_action 非法: {next_action!r}；允许值: {sorted(VALID_NEXT_ACTIONS)}")

    # 4. 只读 Agent 的 changed_files 必须为空
    agent_id = outbox.get("agent_id", "")
    changed_files = outbox.get("changed_files", [])
    if agent_id in READ_ONLY_AGENTS and changed_files:
        errors.append(f"SCOPE_VIOLATION: 只读 Agent {agent_id!r} 的 changed_files 必须为空，实际: {changed_files}")

    # 5. changed_files 不能超出 inbox.allowed_files
    allowed_files = inbox.get("allowed_files", inbox.get("files", [])) if inbox else []
    if allowed_files and changed_files:
        outside = [cf for cf in changed_files if not any(is_changed_file_allowed(cf, af) for af in allowed_files)]
        if outside:
            errors.append(f"changed_files 超出 inbox.allowed_files 范围: {outside}")

    # 6. error_taxonomy 格式
    taxonomy_errors = validate_error_taxonomy(outbox)
    errors.extend(taxonomy_errors)

    # 7. list 字段类型检查
    for field in ("artifacts", "changed_files", "commands_run", "tests_run", "risks", "error_taxonomy"):
        val = outbox.get(field)
        if val is not None and not isinstance(val, list):
            errors.append(f"outbox.{field} 必须是数组，实际类型: {type(val).__name__}")

    return errors, warnings



def parse_acceptance_criteria(inbox):
    """
    解析 inbox 中的 acceptance_criteria。
    返回 (auto_checkable_items, human_review_items, evidence_required_items)

    兼容三种格式:
      1. v2.6 对象: {"auto_checkable": [...], "human_review": [...], "evidence_required": [...]}
      2. v2.5 列表: [{"item": "...", "check_type": "...", "auto_checkable": true/false}, ...]
      3. v2 字符串列表: ["criterion1", "criterion2"]
    """
    criteria = inbox.get("acceptance_criteria", []) if inbox else []

    auto_checkable = []
    human_review = []
    evidence_required = []

    # v2.7: 仅当 inbox schema_version 为 "2.7" 且 criteria 不是 v2.6 三分类格式时，
    # 才从 compiled_intent 提取。避免 v2.5 旧 inbox 误触发 v2.7 逻辑。
    compiled_intent = inbox.get("compiled_intent", {}) if inbox else {}
    schema_ver = inbox.get("schema_version", "") if inbox else ""
    if compiled_intent and schema_ver == "2.7" and not isinstance(criteria, dict):
        for sc in compiled_intent.get("success_criteria", []):
            human_review.append({"item": sc, "hints": ["来源: Task Card compiled_intent.success_criteria"]})
        for ma in compiled_intent.get("must_avoid", []):
            human_review.append({"item": f"确认未违反: {ma}", "hints": ["来源: Task Card compiled_intent.must_avoid"]})

    # v2.6: 三分类对象
    if isinstance(criteria, dict):
        for item in criteria.get("auto_checkable", []):
            if isinstance(item, str):
                auto_checkable.append({"item": item, "check_type": "auto_checkable", "source": "v2.6_dict"})
            else:
                item["source"] = "v2.6_dict"
                auto_checkable.append(item)
        for item in criteria.get("human_review", []):
            if isinstance(item, str):
                human_review.append({"item": item, "hints": []})
            else:
                human_review.append(item)
        for item in criteria.get("evidence_required", []):
            if isinstance(item, str):
                evidence_required.append({"item": item, "source": "v2.6_dict"})
            else:
                evidence_required.append(item)
        return auto_checkable, human_review, evidence_required

    # v2.5: 列表格式
    if isinstance(criteria, list):
        for criterion in criteria:
            if isinstance(criterion, str):
                human_review.append({"item": criterion, "hints": ["旧格式 acceptance_criteria，需人工核对"]})
                continue

            check_type = criterion.get("check_type", "human_review")
            auto = criterion.get("auto_checkable", False)

            if auto or check_type in ("required_fields", "changed_files_subset", "files_exist_and_modified"):
                auto_checkable.append(criterion)
            else:
                human_review.append({"item": criterion.get("item", ""), "hints": criterion.get("review_hints", [])})

        return auto_checkable, human_review, evidence_required

    return auto_checkable, human_review, evidence_required


# =============================================================================
# v2.6: 自动检查
# =============================================================================
def run_auto_checks(inbox, outbox, evidence_items):
    auto_results = []
    human_review_remaining = []

    criteria = inbox.get("acceptance_criteria", []) if inbox else []
    # 判断是否 v2.6 三分类格式
    is_v26 = isinstance(criteria, dict)

    allowed_files = inbox.get("allowed_files", inbox.get("files", [])) if inbox else []

    # v2.6: 对每个 auto_checkable 项执行检查
    auto_items = []
    if is_v26:
        auto_items = criteria.get("auto_checkable", [])
    else:
        # v2.5 兼容
        for c in criteria if isinstance(criteria, list) else []:
            if isinstance(c, dict) and (c.get("auto_checkable") or c.get("check_type") in ("required_fields", "changed_files_subset", "files_exist_and_modified")):
                auto_items.append(c)

    for criterion in auto_items:
        item_text = criterion.get("item", str(criterion)) if isinstance(criterion, dict) else str(criterion)
        check_type = criterion.get("check_type", "generic") if isinstance(criterion, dict) else "generic"
        passed = True
        detail = ""

        # ── required_fields ──
        if ("required_fields" in check_type or "必填字段" in item_text or
            "outbox 包含" in item_text or "outbox must contain" in item_text.lower() or
            "required field" in item_text.lower()):
            required = inbox.get("expected_output", {}).get("required_fields", []) if inbox else []
            if not required:
                required = ["schema_version", "task_id", "status", "summary", "changed_files", "verification", "errors"]
                if schema_at_least(outbox, 2, 8):
                    required.extend(["agent_id", "changed_files_source", "evidence", "known_risks", "error_taxonomy", "needs_human_review"])
            missing = [f for f in required if f not in outbox]
            if missing:
                passed = False
                detail = f"缺少必填字段: {missing}"
            else:
                detail = f"必填字段齐全: {required}"

        # ── changed_files_subset ──
        elif "changed_files_subset" in check_type or "within allowed_files" in item_text or "只修改了指定文件" in item_text:
            if allowed_files:
                changed = set(outbox.get("changed_files", []))
                if changed:
                    outside = []
                    for cf in changed:
                        in_scope = any(is_changed_file_allowed(cf, af) for af in allowed_files)
                        if not in_scope:
                            outside.append(cf)
                    if outside:
                        passed = False
                        detail = f"changed_files 超出范围: {outside}"
                    else:
                        detail = "changed_files 在允许范围内"
                else:
                    detail = "changed_files 为空"
            else:
                detail = "未配置 allowed_files（无法检查范围）"

        # ── files_exist_and_modified ──
        elif "files_exist_and_modified" in check_type or "changed_files真实存在" in item_text:
            changed_files = outbox.get("changed_files", [])
            # v2.6: 优先使用 changed_files_source
            changed_source = outbox.get("changed_files_source", "")
            if changed_source == "git_diff":
                detail = "changed_files 来自 git diff（系统侧检测，可信）"
                passed = True
            elif changed_files:
                missing = check_files_exist(changed_files)
                task_start = parse_iso_timestamp(inbox.get("created_at")) if inbox else None
                not_modified, skip_reason = check_files_modified(changed_files, task_start)
                if missing:
                    passed = False
                    detail = f"文件不存在: {missing}"
                elif not_modified:
                    passed = False
                    detail = f"文件未被修改: {not_modified}"
                elif skip_reason:
                    detail = f"文件存在，{skip_reason}"
                else:
                    detail = "文件存在且已被修改"
            else:
                detail = "changed_files 为空，无法检查"

        # ── generic auto check（新增） ──
        elif "npm test" in item_text.lower() or "test" in item_text.lower():
            evidence = outbox.get("evidence", {})
            outputs = evidence.get("outputs", []) if isinstance(evidence, dict) else []
            # 检查 evidence 中是否有 test 输出
            test_found = any("test" in str(o).lower() or "pass" in str(o).lower() for o in outputs)
            if not test_found and not any("test" in str(o).lower() for o in outbox.get("summary", [])):
                passed = False
                detail = "outbox.evidence 中未找到 test 输出"
            else:
                detail = "evidence 包含 test 输出"
        elif "lint" in item_text.lower() or "error" in item_text.lower():
            evidence = outbox.get("evidence", {})
            outputs = evidence.get("outputs", []) if isinstance(evidence, dict) else []
            error_found = any("error" in str(o).lower() for o in outputs)
            if error_found:
                passed = False
                detail = "evidence 包含 error 输出"
            else:
                detail = "evidence 无 error 输出"
        else:
            # 未知类型: 标记为通过但附说明
            detail = f"自动检查项（无法自动验证具体内容）: {item_text}"

        auto_results.append({
            "item": item_text,
            "check_type": check_type,
            "passed": passed,
            "detail": detail
        })

    for ev in evidence_items:
        item_text = ev.get("item", str(ev)) if isinstance(ev, dict) else str(ev)
        value = evidence_value(outbox, item_text)

        if value not in (None, "", [], {}):
            auto_results.append({
                "item": f"[evidence] {item_text}",
                "check_type": "evidence_required",
                "passed": True,
                "detail": f"evidence 字段已提交: {item_text}"
            })
        else:
            auto_results.append({
                "item": f"[evidence] {item_text}",
                "check_type": "evidence_required",
                "passed": False,
                "detail": f"缺少 evidence 字段: {item_text}"
            })

    # ── v2.6: format_wrapped_unverified 检测 ──
    verify_status = outbox.get("verification", {}).get("status", "") if isinstance(outbox.get("verification"), dict) else ""
    if verify_status == "format_wrapped_unverified":
        auto_results.append({
            "item": "v2.6: 包装输出检测",
            "check_type": "format_integrity",
            "passed": False,
            "detail": "输出为自动包装 (format_wrapped_unverified)，内容未经 Agent 原生验收"
        })

    if is_v26:
        # human_review 从 criteria 读取
        human_review_remaining = [
            {"item": item if isinstance(item, str) else item.get("item", str(item)), "hints": [] if isinstance(item, str) else item.get("review_hints", [])}
            for item in criteria.get("human_review", [])
        ]

    return auto_results, human_review_remaining


# =============================================================================
# 主验收函数
# =============================================================================
def verify(inbox_path, outbox_path):
    errors = []
    checks = []
    auto_results = []
    human_review_items = []

    # 1. outbox 是否存在
    outbox_file = Path(outbox_path).expanduser()
    if not outbox_file.exists():
        return {
            "result": "fail",
            "checks": checks,
            "errors": [f"outbox 文件不存在: {outbox_path}"],
            "verification": {"passed": False, "auto_checks": [], "human_review_items": []}
        }
    checks.append("outbox_exists")

    # 2. outbox 是否合法 JSON
    outbox, err = load_json(outbox_path)
    if err:
        return {
            "result": "fail",
            "checks": checks,
            "errors": [err],
            "verification": {"passed": False, "auto_checks": [], "human_review_items": []}
        }
    checks.append("outbox_valid_json")

    # 读取 inbox
    inbox, err = load_json(inbox_path)
    if err:
        inbox = {}

    # v2.6: 三分类解析
    auto_items, human_items, evidence_items = parse_acceptance_criteria(inbox)

    # 3. required_fields
    required_fields = inbox.get("expected_output", {}).get("required_fields", []) if inbox else []
    if not required_fields:
        required_fields = ["schema_version", "task_id", "status", "summary", "changed_files", "verification", "errors"]
        if schema_at_least(outbox, 2, 8):
            required_fields.extend(["agent_id", "changed_files_source", "evidence", "known_risks", "error_taxonomy", "needs_human_review"])

    missing_fields = [f for f in required_fields if f not in outbox]
    if missing_fields:
        errors.append(f"缺少必填字段: {missing_fields}")
    else:
        checks.append("required_fields_present")

    # 3a. v2.8: 标准任务状态机
    status_error = validate_status(outbox)
    if status_error:
        errors.append(status_error)
    else:
        checks.append("status_is_canonical")

    if outbox.get("status") in TERMINAL_TASK_STATUSES and outbox.get("needs_human_review") is True:
        errors.append(f"终态 status={outbox.get('status')!r} 不应同时 needs_human_review=true")

    # 3b. v2.8: 标准错误分类
    taxonomy_errors = validate_error_taxonomy(outbox)
    if taxonomy_errors:
        errors.extend(taxonomy_errors)
    else:
        checks.append("error_taxonomy_valid")

    # 3c. v2.8 Phase 3: 标准 outbox schema 校验
    std_errors, std_warnings = validate_standard_outbox(outbox, inbox)
    if std_errors:
        errors.extend(std_errors)
    else:
        checks.append("standard_outbox_schema_valid")
    for w in std_warnings:
        checks.append(f"warning: {w}")

    # 4. task_id 匹配（v2.7: 支持 task_card_id）
    inbox_task_id = inbox.get("task_card_id") or inbox.get("task_id") if inbox else None
    outbox_task_id = outbox.get("task_id")
    if inbox_task_id and outbox_task_id and inbox_task_id != outbox_task_id:
        errors.append(f"task_id 不匹配: inbox={inbox_task_id}, outbox={outbox_task_id}")
    elif outbox_task_id:
        checks.append("task_id_matches")

    # 5. changed_files 范围检查
    allowed_files = inbox.get("allowed_files", inbox.get("files", [])) if inbox else []
    changed_files = set(outbox.get("changed_files", []))
    if allowed_files and changed_files:
        outside_files = set()
        for cf in changed_files:
            in_scope = any(is_changed_file_allowed(cf, af) for af in allowed_files)
            if not in_scope:
                outside_files.add(cf)
        if outside_files:
            errors.append(f"changed_files 超出范围: {list(outside_files)}")
        else:
            checks.append("changed_files_within_scope")
    elif changed_files:
        checks.append("changed_files_within_scope (no allowed_files constraint)")

    # 6. 文件真实存在
    missing = []
    if changed_files:
        missing = check_files_exist(list(changed_files))
        if missing:
            errors.append(f"changed_files 中文件不存在: {missing}")
        else:
            checks.append("changed_files_exist")

    # 7. 文件被修改（git_diff 优先）
    if changed_files and not missing:
        changed_source = outbox.get("changed_files_source", "")
        if changed_source == "git_diff":
            checks.append("changed_files_detected_by_git_diff")
        else:
            task_start = parse_iso_timestamp(inbox.get("created_at")) if inbox else None
            not_modified, skip_reason = check_files_modified(list(changed_files), task_start)
            if not_modified:
                errors.append(f"文件未被任务修改: {not_modified}")
            elif skip_reason:
                checks.append(f"changed_files_modified ({skip_reason})")
            else:
                checks.append("changed_files_modified")

    # 8. errors 检查
    outbox_errors = outbox.get("errors", [])
    if outbox_errors:
        errors.append(f"outbox 包含 errors: {outbox_errors}")
    else:
        checks.append("no_errors")

    # 9. v2.6: 自动检查（三分类）
    auto_results, v26_human_items = run_auto_checks(inbox, outbox, evidence_items)
    human_review_items = v26_human_items if v26_human_items else human_items

    for r in auto_results:
        if r["passed"]:
            checks.append(f"auto_check_passed: {r['check_type']}")
        else:
            msg = f"自动检查失败 [{r['check_type']}]: {r['detail']}"
            # evidence 缺失不算 hard fail，降级为 human_review
            if r['check_type'] == 'evidence_required':
                human_review_items.insert(0, {"item": r['item'], "hints": [r['detail']]})
            else:
                errors.append(msg)

    # v2.5 兼容: 如果旧格式有 non-auto 项且不在 auto_results 中
    if not isinstance(inbox.get("acceptance_criteria"), dict) and inbox.get("acceptance_criteria"):
        old_criteria = inbox["acceptance_criteria"]
        if isinstance(old_criteria, list):
            for c in old_criteria:
                if isinstance(c, dict) and not c.get("auto_checkable", False):
                    already = any(c.get("item", "") == r["item"] for r in human_review_items)
                    if not already:
                        human_review_items.append({"item": c.get("item", ""), "hints": c.get("review_hints", [])})

    # 判定
    all_auto_passed = all(r["passed"] for r in auto_results) if auto_results else True

    # v2.6: format_wrapped_unverified 强制 needs_human_review
    is_format_wrapped = outbox.get("verification", {}).get("status") == "format_wrapped_unverified" if isinstance(outbox.get("verification"), dict) else False

    if errors and not all(e.startswith("自动检查失败 [evidence") for e in errors):
        result = "fail"
        verification_passed = False
    elif is_format_wrapped:
        result = "needs_human_review"
        verification_passed = False
    elif not errors:
        verification_passed = all_auto_passed and len(human_review_items) == 0
        if verification_passed and outbox.get("needs_human_review") is False:
            result = "pass"
        else:
            result = "needs_human_review"
    else:
        result = "needs_human_review"
        verification_passed = False

    verification = {
        "passed": verification_passed,
        "auto_checks": auto_results,
        "human_review_items": human_review_items,
        "format_wrapped": is_format_wrapped,
        "summary": (
            f"自动检查: {sum(1 for r in auto_results if r['passed'])}/{len(auto_results)} 项通过; "
            f"需人工核对: {len(human_review_items)} 项"
            + ("; ⚠️ format_wrapped_unverified" if is_format_wrapped else "")
        ) if (auto_results or human_review_items) else "未配置结构化 acceptance_criteria，运行默认检查"
    }

    return {
        "result": result,
        "task_id": outbox.get("task_id", "unknown"),
        "schema_version": outbox.get("schema_version", inbox.get("schema_version", "unknown")),
        "checks": checks,
        "errors": errors,
        "verification": verification,
        "summary": (
            f"outbox 结构+事实检查{'通过' if result != 'fail' else '失败'}，"
            f"{verification['summary']}"
        )
    }


def format_summary(result):
    """Return a compact routing summary for the main Hermes agent."""
    verification = result.get("verification", {})
    auto_checks = verification.get("auto_checks", [])
    human_items = verification.get("human_review_items", [])
    failed_auto = [r for r in auto_checks if not r.get("passed")]

    route_by_result = {
        "pass": "deliver_to_user",
        "needs_human_review": "send_to_human_or_ambrosini_review",
        "fail": "revise_or_retry_before_delivery",
    }
    lines = [
        f"RESULT: {result.get('result', 'unknown')}",
        f"ROUTE: {route_by_result.get(result.get('result'), 'inspect_manually')}",
        f"TASK_ID: {result.get('task_id', 'unknown')}",
        f"SUMMARY: {result.get('summary', '')}",
    ]

    errors = result.get("errors", [])
    if errors:
        lines.append("ERRORS:")
        lines.extend(f"- {err}" for err in errors[:8])
        if len(errors) > 8:
            lines.append(f"- ... {len(errors) - 8} more")

    if failed_auto:
        lines.append("FAILED_AUTO_CHECKS:")
        for item in failed_auto[:8]:
            lines.append(f"- {item.get('item')}: {item.get('detail')}")
        if len(failed_auto) > 8:
            lines.append(f"- ... {len(failed_auto) - 8} more")

    if human_items:
        lines.append("HUMAN_REVIEW_ITEMS:")
        for item in human_items[:12]:
            lines.append(f"- {item.get('item')}")
        if len(human_items) > 12:
            lines.append(f"- ... {len(human_items) - 12} more")

    return "\n".join(lines)


def main():
    if len(sys.argv) < 4:
        print(f"用法: {sys.argv[0]} --inbox <inbox_path> --outbox <outbox_path> [--summary]")
        sys.exit(1)

    inbox_path = None
    outbox_path = None
    summary_mode = False

    i = 1
    while i < len(sys.argv):
        if sys.argv[i] in ["--inbox", "--inbox-path"] and i + 1 < len(sys.argv):
            inbox_path = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] in ["--outbox", "--outbox-path"] and i + 1 < len(sys.argv):
            outbox_path = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--summary":
            summary_mode = True
            i += 1
        else:
            i += 1

    if not inbox_path or not outbox_path:
        print(f"错误: 需要指定 --inbox 和 --outbox")
        sys.exit(1)

    result = verify(inbox_path, outbox_path)
    if summary_mode:
        print(format_summary(result))
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))

    if result["result"] == "fail":
        sys.exit(1)
    elif result["result"] == "needs_human_review":
        sys.exit(2)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
