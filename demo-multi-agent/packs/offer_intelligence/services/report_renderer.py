"""
Server-side report renderer for OL triage results.

Produces a plain-text condition block for each rule evaluation.
Output is consumed verbatim by the closure template / agent response —
no reconstruction on the LLM side.
"""
from __future__ import annotations

import re
from typing import Any


def _find_or_groups(expression: str) -> dict[str, list[str]]:
    """
    Parse the expression to find all OR groups, including nested ones.
    Returns a map of condition_name -> list of all condition names in the same OR group.
    """
    or_group_map: dict[str, list[str]] = {}

    def _tokenize(expr: str) -> list:
        return re.findall(r"\(|\)|#\w+|\bAND\b|\bOR\b|\w+", expr, re.IGNORECASE)

    def _parse_or_groups(tokens: list, pos: int) -> tuple[list[str], int]:
        direct_children: list[str] = []
        current_segment_conds: list[str] = []
        or_segments: list[list[str]] = []

        while pos < len(tokens):
            tok = tokens[pos]
            if tok == "(":
                sub_conds, pos = _parse_or_groups(tokens, pos + 1)
                current_segment_conds.extend(sub_conds)
                direct_children.extend(sub_conds)
            elif tok == ")":
                or_segments.append(current_segment_conds)
                if len(or_segments) > 1:
                    all_at_level = [c for seg in or_segments for c in seg]
                    for c in all_at_level:
                        or_group_map[c] = all_at_level
                return direct_children, pos + 1
            elif tok.upper() == "OR":
                or_segments.append(current_segment_conds)
                current_segment_conds = []
                pos += 1
            elif tok.upper() == "AND":
                pos += 1
            elif tok.startswith("#"):
                cname = tok[1:]
                current_segment_conds.append(cname)
                direct_children.append(cname)
                pos += 1
            else:
                pos += 1

        return direct_children, pos

    tokens = _tokenize(expression)
    _parse_or_groups(tokens, 0)
    return or_group_map


def render_rule_block(rule_def: dict, eval_result: dict) -> str:
    """Render a single rule's evaluation as a plain-text block."""
    rule_id = rule_def.get("rule_id", "?")
    rule_name = rule_def.get("rule_name", "Unknown")
    rule_group = rule_def.get("rule_group", "")
    reason_code = rule_def.get("reason_code", "")
    expression = rule_def.get("expression", "")

    per_conditions = eval_result.get("per_condition_results", [])
    verdict = eval_result.get("verdict", "CANNOT_EVALUATE")
    expression_result = eval_result.get("expression_result")
    evaluated_count = eval_result.get("evaluated_count", 0)
    skipped_count = eval_result.get("skipped_count", 0)
    total = eval_result.get("total_conditions", len(per_conditions))
    cannot_evaluate_fields = eval_result.get("cannot_evaluate_fields", [])

    or_group_map = _find_or_groups(expression)

    or_group_passed: dict[str, bool] = {}
    for cond in per_conditions:
        name = cond.get("name", "")
        if name in or_group_map and cond.get("condition_passed") is True:
            for member in or_group_map[name]:
                or_group_passed[member] = True

    lines = []
    lines.append(f"Rule {rule_id} — {rule_name}")
    lines.append(f"Reason Code : {reason_code}")
    lines.append(f"Rule Group  : {rule_group}")
    lines.append("")
    lines.append(f"Expression: {expression}")
    lines.append("")
    lines.append("Condition Check:")
    lines.append(
        "  {:<12} | {:<24} | {:<12} | {:<15} | {:<15} | {}".format(
            "#", "entry", "operator", "expected", "actual", "result"
        )
    )
    lines.append("  " + "─" * 95)

    for cond in per_conditions:
        name = cond.get("name", "")
        entry = cond.get("entry", "")
        operator = cond.get("operator", "")
        expected = str(cond.get("expected_fact", ""))
        resolved = cond.get("resolved_value")
        passed = cond.get("condition_passed")
        skip_reason = cond.get("skip_reason")

        if resolved is None:
            actual = "null"
        elif isinstance(resolved, list):
            if len(resolved) == 0:
                actual = "[]"
            elif len(resolved) == 1:
                actual = str(resolved[0])
            else:
                joined = ", ".join(str(v) for v in resolved[:3])
                actual = f"[{joined}{'...' if len(resolved) > 3 else ''}]"
        else:
            actual = str(resolved)

        if len(expected) > 15:
            expected = expected[:13] + ".."
        if len(actual) > 15:
            actual = actual[:13] + ".."

        if skip_reason is not None:
            result = "⚠️ SKIP"
        elif passed is True:
            result = "✅ PASS"
        elif passed is False:
            result = "❌ FAIL"
        else:
            result = "⚠️ SKIP"

        suffix = ""
        if name in or_group_map:
            group_members = or_group_map[name]
            idx = group_members.index(name) + 1
            total_in_group = len(group_members)
            suffix = f"  ← OR group ({idx} of {total_in_group})"
            if or_group_passed.get(name) and passed is True:
                suffix += " ← OR satisfied"

        row = "  {:<12} | {:<24} | {:<12} | {:<15} | {:<15} | {}{}".format(
            name, entry, operator, expected, actual, result, suffix
        )
        lines.append(row)

    lines.append("")

    if verdict == "VALID":
        lines.append(f"Delist Verdict : ✅ VALID DELIST — all {evaluated_count} of {total} conditions evaluated and confirmed")
    elif verdict == "INVALID":
        mismatches = [
            c["entry"]
            for c in per_conditions
            if c.get("condition_passed") is False and c.get("skip_reason") is None
        ]
        mismatch_str = ", ".join(mismatches) if mismatches else "expression evaluates to FALSE"
        lines.append(f"Delist Verdict : ❌ INVALID DELIST — {mismatch_str} did not satisfy rule conditions")
    elif verdict == "CANNOT_EVALUATE":
        lines.append("Delist Verdict : ⚠️ CANNOT EVALUATE — all conditions require unsupported fields")
    else:  # PARTIAL
        skipped_fields = list({f["field"] for f in cannot_evaluate_fields})
        lines.append(
            f"Delist Verdict : ⚠️ PARTIAL — {evaluated_count} of {total} API-verifiable conditions evaluated"
        )
        if skipped_fields:
            lines.append(f"                 Skipped (unsupported): {', '.join(skipped_fields)}")

    return "\n".join(lines)


def render_full_report(
    offer_id: str,
    store_id: str,
    mart_id: str,
    listing_status: str,
    rule_blocks: list[str],
    summary_lines: list[str],
) -> str:
    """Assemble the complete OL Triage Report from pre-rendered rule blocks."""
    if listing_status == "LISTED":
        status_icon = "✅ LISTED"
    elif listing_status in ("UNKNOWN", "NOT_FOUND"):
        status_icon = "⚠️ OL NOT FOUND"
    else:
        status_icon = "❌ DELISTED"

    lines = []
    lines.append("OL Triage Report")
    lines.append("===================================")
    lines.append(f"Offer ID   : {offer_id}")
    lines.append(f"Store ID   : {store_id}")
    lines.append(f"Mart ID    : {mart_id}")
    lines.append(f"Listing Status : {status_icon}")

    if listing_status == "LISTED":
        lines.append("===================================")
        lines.append(f"This offer is correctly listed at store {store_id}.")
    else:
        for block in rule_blocks:
            lines.append("-----------------------------------")
            lines.append(block)
        lines.append("-----------------------------------")
        lines.append("")
        lines.append("Overall Summary:")
        for s in summary_lines:
            lines.append(s)

    return "\n".join(lines)
