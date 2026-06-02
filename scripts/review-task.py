#!/usr/bin/env python3
"""
Hermes v2.8 semantic Review Gate.

Reads an inbox task card, a child-agent outbox, and an optional verify-task.py
JSON result. Produces a lightweight semantic decision:
approved / revision_needed / rejected.
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


DECISIONS = {"approved", "revision_needed", "rejected"}
HERMES_ROOT = Path(__file__).resolve().parents[1]


def load_json(path):
    try:
        with open(Path(path).expanduser(), "r", encoding="utf-8") as f:
            return json.load(f), None
    except FileNotFoundError:
        return None, f"文件不存在: {path}"
    except json.JSONDecodeError as exc:
        return None, f"JSON 解析失败: {path}: {exc}"
    except OSError as exc:
        return None, f"读取失败: {path}: {exc}"


def text_blob(*parts):
    return json.dumps(parts, ensure_ascii=False, sort_keys=True).lower()


def norm_path(path):
    candidate = Path(str(path)).expanduser()
    if not candidate.is_absolute():
        candidate = HERMES_ROOT / candidate
    return str(candidate.resolve(strict=False))


def basename_set(paths):
    return {Path(p).name.lower() for p in paths if p}


def path_tokens(text):
    if not text:
        return set()
    candidates = re.findall(r"[\w./~:-]+\.[A-Za-z0-9_+-]+", text)
    return {Path(c).name.lower() for c in candidates}


def keyword_tokens(text):
    normalized = re.sub(r"[/_-]+", " ", str(text).lower())
    tokens = re.findall(r"[A-Za-z0-9]{4,}", normalized)
    noisy = {
        "must",
        "should",
        "with",
        "from",
        "that",
        "this",
        "only",
        "then",
        "true",
        "false",
        "json",
        "python",
    }
    return {t for t in tokens if t not in noisy}


def text_covers_item(item, blob, changed_files):
    item_text = str(item).lower()
    file_names = basename_set(changed_files)
    item_paths = path_tokens(item_text)
    if item_paths and item_paths & file_names:
        return True

    tokens = keyword_tokens(item_text)
    if not tokens:
        return True
    hits = sum(1 for token in tokens if token in blob)
    return hits >= max(1, min(3, len(tokens)))


def check_intent_alignment(inbox, outbox, blob):
    intent = inbox.get("goal") or inbox.get("compiled_intent", {}).get("real_task", "")
    if not intent:
        return True, "inbox 未提供 goal，跳过意图匹配"

    intent_tokens = keyword_tokens(intent)
    if not intent_tokens:
        return True, "goal token 太少，跳过意图匹配"

    hits = sum(1 for token in intent_tokens if token in blob)
    ratio = hits / len(intent_tokens)
    if ratio >= 0.25:
        return True, f"summary/outbox 覆盖 goal 关键词 {hits}/{len(intent_tokens)}"
    return False, f"summary/outbox 与 goal 关键词重合过低 {hits}/{len(intent_tokens)}"


def check_allowed_files(inbox, outbox):
    allowed = {norm_path(p) for p in inbox.get("allowed_files", [])}
    changed = {norm_path(p) for p in outbox.get("changed_files", [])}
    if not allowed:
        return False, "inbox.allowed_files 为空，无法确认修改范围"
    extra = sorted(changed - allowed)
    if extra:
        return False, f"changed_files 越界: {extra}"
    return True, "changed_files 均在 allowed_files 范围内"


def check_must_avoid(inbox, outbox, blob):
    must_avoid = inbox.get("compiled_intent", {}).get("must_avoid", [])
    changed_names = basename_set(outbox.get("changed_files", []))
    violations = []

    for item in must_avoid:
        item_text = str(item).lower()
        forbidden_paths = path_tokens(item_text)
        touched_forbidden = sorted(forbidden_paths & changed_names)
        if touched_forbidden:
            violations.append(f"{item} -> touched {touched_forbidden}")
            continue

        if "do not" in item_text or "不要" in item_text or "禁止" in item_text:
            tokens = keyword_tokens(item_text)
            if tokens and len(tokens & changed_names) > 0:
                violations.append(str(item))

    if violations:
        return False, "must_avoid 可能被违反: " + "; ".join(violations)
    return True, "未发现 changed_files 违反 must_avoid"


def check_list_coverage(name, items, blob, changed_files):
    if not items:
        return True, f"{name} 为空，跳过"

    missing = [str(item) for item in items if not text_covers_item(item, blob, changed_files)]
    if missing:
        return False, f"{name} 未充分体现: {missing[:5]}"
    return True, f"{name} 已在 outbox 中体现"


def check_must_keep(items, blob, changed_files):
    if not items:
        return True, "must_keep 为空，跳过"

    missing_hard = []
    soft_items = []
    for item in items:
        item_text = str(item).lower()
        if "v2.8" in item_text and ("v2.8" in blob or '"2.8"' in blob):
            continue
        if path_tokens(item_text) or "v2.8" in item_text or "schema" in item_text:
            if not text_covers_item(item, blob, changed_files):
                missing_hard.append(str(item))
        else:
            soft_items.append(str(item))

    if missing_hard:
        return False, f"must_keep 未充分体现: {missing_hard[:5]}"
    if soft_items:
        return True, f"must_keep 未发现自动违规；主观项需人工确认: {soft_items[:5]}"
    return True, "must_keep 已在 outbox 中体现"


def check_changed_files_source(outbox):
    source = outbox.get("changed_files_source")
    if source == "git_diff":
        return True, "changed_files_source=git_diff"
    return False, f"changed_files_source 不是 git_diff: {source!r}"


def check_evidence_quality(outbox):
    evidence = outbox.get("evidence", {})
    verification = outbox.get("verification", {})
    commands = evidence.get("verification_commands") or verification.get("commands") or []
    summary = evidence.get("verification_output_summary") or verification.get("output_summary") or ""

    if not commands:
        return False, "缺少 verification_commands"
    if not summary or len(str(summary).strip()) < 12:
        return False, "verification_output_summary 过短或缺失"
    return True, "验证命令和输出摘要存在"


def check_verify_result(verify_result):
    if not verify_result:
        return True, "未提供 verify-result，按 outbox 自身证据审查"

    result = verify_result.get("result")
    if result == "fail":
        return False, "verify-task.py result=fail"
    if result == "needs_human_review":
        return True, "verify-task.py result=needs_human_review，需要语义审查"
    if result == "pass":
        return True, "verify-task.py result=pass"
    return False, f"未知 verify-task.py result: {result!r}"


# Maps check name to error_taxonomy category
_CHECK_TAXONOMY = {
    "intent_alignment": "intent_drift",
    "allowed_files_check": "scope_violation",
    "must_avoid_respected": "scope_violation",
    "must_keep_reflected": "quality_failed",
    "must_change_fulfilled": "quality_failed",
    "success_criteria_mentioned": "quality_failed",
    "changed_files_source": "artifact_missing",
    "evidence_quality": "artifact_missing",
    "verify_result": "quality_failed",
    "invalid_output_schema": "schema_invalid",
    "required_fields": "schema_invalid",
}


def make_check(name, passed, detail):
    entry = {"check": name, "passed": bool(passed), "detail": detail}
    if not passed and name in _CHECK_TAXONOMY:
        entry["taxonomy"] = _CHECK_TAXONOMY[name]
    return entry


def decide(checks, verify_result, outbox):
    failed = [check for check in checks if not check["passed"]]
    failed_names = {check["check"] for check in failed}
    revision_instructions = []

    if verify_result and verify_result.get("result") == "fail":
        return "rejected", "结构验收失败，不能进入交付", [
            "先修复 verify-task.py 报告的结构、范围或证据问题，再重新提交 outbox。"
        ]

    if outbox.get("errors"):
        return "rejected", "outbox.errors 非空", [
            "处理 outbox.errors 中的错误并重新提交。"
        ]

    if "must_avoid_respected" in failed_names or "allowed_files_check" in failed_names:
        return "rejected", "存在越权修改或 must_avoid 违规", [
            "停止交付，人工确认是否需要回滚或重新派发。"
        ]

    for check in failed:
        if check["check"] in {
            "intent_alignment",
            "must_keep_reflected",
            "must_change_fulfilled",
            "success_criteria_mentioned",
            "changed_files_source",
            "evidence_quality",
        }:
            revision_instructions.append(f"{check['check']}: {check['detail']}")

    if revision_instructions:
        return "revision_needed", "存在可修正的语义或证据问题", revision_instructions

    return "approved", "结构与语义检查均可接受", []


def review(inbox_path, outbox_path, verify_result_path=None):
    inbox, err = load_json(inbox_path)
    if err:
        return failure_record("rejected", err)

    outbox, err = load_json(outbox_path)
    if err:
        return failure_record("rejected", err)

    verify_result = None
    if verify_result_path:
        verify_result, err = load_json(verify_result_path)
        if err:
            return failure_record("rejected", err)

    compiled_intent = inbox.get("compiled_intent", {})
    changed_files = outbox.get("changed_files", [])
    blob = text_blob(
        outbox.get("summary", ""),
        outbox.get("notes", []),
        outbox.get("verification", {}),
        outbox.get("evidence", {}),
        changed_files,
    )

    checks = []
    checks.append(make_check("intent_alignment", *check_intent_alignment(inbox, outbox, blob)))
    checks.append(make_check("allowed_files_check", *check_allowed_files(inbox, outbox)))
    checks.append(make_check("must_avoid_respected", *check_must_avoid(inbox, outbox, blob)))
    checks.append(make_check(
        "must_keep_reflected",
        *check_must_keep(compiled_intent.get("must_keep", []), blob, changed_files),
    ))
    checks.append(make_check(
        "must_change_fulfilled",
        *check_list_coverage("must_change", compiled_intent.get("must_change", []), blob, changed_files),
    ))
    checks.append(make_check(
        "success_criteria_mentioned",
        *check_list_coverage("success_criteria", compiled_intent.get("success_criteria", []), blob, changed_files),
    ))
    checks.append(make_check("changed_files_source", *check_changed_files_source(outbox)))
    checks.append(make_check("evidence_quality", *check_evidence_quality(outbox)))
    checks.append(make_check("verify_result", *check_verify_result(verify_result)))

    decision, reason, revision_instructions = decide(checks, verify_result, outbox)
    passed_count = sum(1 for check in checks if check["passed"])
    total_count = len(checks)
    task_id = outbox.get("task_id") or inbox.get("task_card_id") or "unknown"

    return {
        "schema_version": "2.8",
        "review_id": f"{task_id}_review_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
        "task_id": task_id,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "reviewed_by": "hermes_review_gate",
        "verify_result": verify_result.get("result") if verify_result else "not_provided",
        "decision": decision,
        "gate_decision": decision,
        "reason": reason,
        "semantic_checks": checks,
        "semantic_checks_passed": passed_count,
        "semantic_checks_total": total_count,
        "revision_instructions": revision_instructions,
        "verdict_summary": f"{decision}: {reason}; semantic checks {passed_count}/{total_count}",
        "ready_for_user": decision == "approved",
    }


def failure_record(decision, reason):
    return {
        "schema_version": "2.8",
        "review_id": f"unknown_review_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
        "task_id": "unknown",
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "reviewed_by": "hermes_review_gate",
        "verify_result": "not_available",
        "decision": decision,
        "gate_decision": decision,
        "reason": reason,
        "semantic_checks": [],
        "semantic_checks_passed": 0,
        "semantic_checks_total": 0,
        "revision_instructions": [reason],
        "verdict_summary": f"{decision}: {reason}",
        "ready_for_user": False,
    }


def format_summary(record):
    lines = [
        f"DECISION: {record['decision']}",
        f"TASK_ID: {record['task_id']}",
        f"READY_FOR_USER: {str(record['ready_for_user']).lower()}",
        f"SUMMARY: {record['verdict_summary']}",
    ]
    if record.get("revision_instructions"):
        lines.append("REVISION_INSTRUCTIONS:")
        lines.extend(f"- {item}" for item in record["revision_instructions"])
    failed = [check for check in record.get("semantic_checks", []) if not check.get("passed")]
    if failed:
        lines.append("FAILED_CHECKS:")
        lines.extend(f"- {item['check']}: {item['detail']}" for item in failed)
    return "\n".join(lines)


def exit_code(decision):
    if decision == "approved":
        return 0
    if decision == "revision_needed":
        return 1
    return 2


def main():
    parser = argparse.ArgumentParser(description="Hermes v2.8 semantic Review Gate")
    parser.add_argument("--inbox", required=True, help="Inbox task card JSON path")
    parser.add_argument("--outbox", required=True, help="Child-agent outbox JSON path")
    parser.add_argument("--verify-result", help="Optional verify-task.py JSON result path")
    parser.add_argument("--summary", action="store_true", help="Print compact text summary")
    args = parser.parse_args()

    record = review(args.inbox, args.outbox, args.verify_result)
    if args.summary:
        print(format_summary(record))
    else:
        print(json.dumps(record, indent=2, ensure_ascii=False))
    sys.exit(exit_code(record["decision"]))


if __name__ == "__main__":
    main()
