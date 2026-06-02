#!/usr/bin/env python3
"""
Hermes v2.8 Gate Policy.

Maps a gate record to the next orchestration action.
"""
import argparse
import json
import sys
from pathlib import Path


AUTO_REVISION_CHECKS = {
    "evidence_quality",
    "changed_files_source",
    "invalid_output_schema",
    "required_fields",
    "must_keep_reflected",
    "must_change_fulfilled",
    "success_criteria_mentioned",
}
HARD_STOP_CHECKS = {
    "allowed_files_check",
    "must_avoid_respected",
}
TIMEOUT_CODES = {"timeout"}
DEFAULT_POLICY_PATH = Path(__file__).resolve().parents[1] / "templates" / "gate_policy_v2_8.json"


def load_json(path):
    if path == "-":
        return json.load(sys.stdin)
    with open(Path(path).expanduser(), "r", encoding="utf-8") as f:
        return json.load(f)


def load_policy_config(path=None):
    config_path = Path(path).expanduser() if path else DEFAULT_POLICY_PATH
    try:
        return load_json(str(config_path))
    except Exception:
        return {}


def policy_sets(config):
    return {
        "auto_revision_checks": set(config.get("auto_revision_checks") or AUTO_REVISION_CHECKS),
        "hard_stop_checks": set(config.get("hard_stop_checks") or HARD_STOP_CHECKS),
        "timeout_error_codes": set(config.get("timeout_error_codes") or TIMEOUT_CODES),
    }


def failed_check_names(record):
    review = record.get("review") if isinstance(record.get("review"), dict) else {}
    checks = review.get("failed_checks") or []
    names = []
    for check in checks:
        if isinstance(check, dict) and check.get("check"):
            names.append(str(check["check"]))
        elif isinstance(check, str):
            names.append(check.split(":", 1)[0])
    instructions = review.get("revision_instructions") or []
    for item in instructions:
        if isinstance(item, str) and ":" in item:
            names.append(item.split(":", 1)[0].strip())
    return set(names)


def error_codes(record):
    codes = set()
    for item in record.get("error_taxonomy") or []:
        if isinstance(item, dict) and item.get("code"):
            codes.add(str(item["code"]))
    return codes


# Taxonomy → action mapping for v2.8.1
_TAXONOMY_POLICY = {
    "approved":                 ("complete",       False, False),
    "quality_failed":           ("auto_revision",  True,  True),
    "scope_violation":          ("reject",         False, False),
    "tool_violation":           ("reject",         False, False),
    "intent_drift":             ("manual_review",  False, False),
    "artifact_missing":         ("auto_revision",  True,  True),
    "schema_invalid":           ("auto_revision",  True,  True),
    "timeout":                  ("switch_agent",   False, False),
    "hard_stop":                ("reject",         False, False),
    "security_risk":            ("reject",         False, False),
    "manual_review_required":   ("manual_review",  False, False),
}


def _taxonomy_codes(record):
    """Collect taxonomy values from failed_checks[].taxonomy and error_taxonomy[].code."""
    codes = set()
    review = record.get("review") if isinstance(record.get("review"), dict) else {}
    for check in review.get("failed_checks") or []:
        if isinstance(check, dict) and check.get("taxonomy"):
            codes.add(str(check["taxonomy"]))
    for item in record.get("error_taxonomy") or []:
        if isinstance(item, dict) and item.get("code"):
            codes.add(str(item["code"]))
    return codes


def policy_for_v2_8_1(record, config=None):
    """Taxonomy-driven policy (v2.8.1). Falls back to policy_for for unknown states."""
    sets = policy_sets(config or {})
    decision = record.get("decision") or record.get("gate_decision")
    tax_codes = _taxonomy_codes(record)

    # Hard precedence: timeout / hard-stop checks override taxonomy
    if error_codes(record) & sets["timeout_error_codes"] or "timeout" in tax_codes:
        return make_policy("switch_agent", "timeout", False, False)

    checks = failed_check_names(record)
    if checks & sets["hard_stop_checks"] or "hard_stop" in tax_codes or "security_risk" in tax_codes:
        return make_policy("reject", f"hard-stop: {sorted(checks & sets['hard_stop_checks'] or tax_codes & {'hard_stop','security_risk'})}", False, False)

    if decision == "approved":
        return make_policy("complete", "gate approved", False, False)

    # revision limit → manual_review
    if record.get("revision_task", {}).get("created") is False:
        reason = record.get("revision_task", {}).get("reason") or "revision was not created"
        if "limit" in reason:
            return make_policy("manual_review", reason, False, False)

    # Taxonomy-driven routing: pick the most severe action
    _severity = ["reject", "manual_review", "switch_agent", "auto_revision", "complete"]
    chosen_action = chosen_reason = None
    chosen_auto_rev = chosen_auto_dis = False
    for code in tax_codes:
        entry = _TAXONOMY_POLICY.get(code)
        if not entry:
            continue
        action, ar, ad = entry
        if chosen_action is None or _severity.index(action) < _severity.index(chosen_action):
            chosen_action, chosen_reason = action, code
            chosen_auto_rev, chosen_auto_dis = ar, ad

    if chosen_action:
        # artifact_missing / schema_invalid → manual_review when revision limit hit
        if chosen_action == "auto_revision" and chosen_reason in ("artifact_missing", "schema_invalid"):
            if record.get("revision_task", {}).get("created") is False:
                return make_policy("manual_review", f"{chosen_reason}: revision limit reached", False, False)
        return make_policy(chosen_action, f"taxonomy:{chosen_reason}", chosen_auto_rev, chosen_auto_dis)

    # Backward-compat: delegate to legacy policy_for
    return policy_for(record, config)


def policy_for(record, config=None):
    sets = policy_sets(config or {})
    decision = record.get("decision") or record.get("gate_decision")
    checks = failed_check_names(record)
    codes = error_codes(record)

    if decision == "approved":
        return make_policy("complete", "gate approved", False, False)

    if codes & sets["timeout_error_codes"]:
        return make_policy("switch_agent", "timeout should switch agent or route", False, False)

    if checks & sets["hard_stop_checks"]:
        return make_policy(
            "reject",
            f"hard-stop failed checks: {sorted(checks & sets['hard_stop_checks'])}",
            False,
            False,
        )

    if record.get("revision_task", {}).get("created") is False:
        reason = record.get("revision_task", {}).get("reason") or "revision was not created"
        if "limit" in reason:
            return make_policy("manual_review", reason, False, False)

    if decision == "revision_needed":
        if not checks or checks & sets["auto_revision_checks"]:
            return make_policy(
                "auto_revision",
                f"recoverable failed checks: {sorted(checks & sets['auto_revision_checks']) or 'unspecified'}",
                True,
                True,
            )
        return make_policy("manual_review", f"unclassified failed checks: {sorted(checks)}", False, False)

    if decision == "rejected":
        return make_policy("reject", "gate rejected", False, False)

    return make_policy("manual_review", f"unknown decision: {decision}", False, False)


def make_policy(action, reason, auto_revision_allowed, auto_dispatch_allowed):
    return {
        "schema_version": "2.8",
        "policy_action": action,
        "policy_reason": reason,
        "auto_revision_allowed": auto_revision_allowed,
        "auto_dispatch_allowed": auto_dispatch_allowed,
    }


def main():
    parser = argparse.ArgumentParser(description="Apply Hermes v2.8 gate policy")
    parser.add_argument("--gate-record", required=True, help="Gate record JSON path, or '-' for stdin")
    parser.add_argument(
        "--policy",
        default=str(DEFAULT_POLICY_PATH),
        help="Gate policy JSON path (default: templates/gate_policy_v2_8.json)",
    )
    args = parser.parse_args()

    record = load_json(args.gate_record)
    print(json.dumps(policy_for(record, load_policy_config(args.policy)), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
