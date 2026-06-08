"""
Deterministic rule evaluator — pure Python, no LLM.

Implements all IMP operator types and evaluates a rule's boolean expression
against resolved fact values. Produces a structured verdict.
"""
from __future__ import annotations

import fnmatch
import json
import re
from datetime import datetime, timezone
from typing import Any

# Fields that cannot be fetched on the REST (interactive) path
BQ_ONLY_FIELDS: set[str] = set()  # hatPathIds now resolved via Product API + Uber Keys
UNSUPPORTED_FIELDS = {
    "SellerType",
    "daysSinceNoInventory",
    "inventoryModificationDate",
    "isComponentDelisted",
    "isInventoryReasonCodePresent",
    "isPreOrder",
    "isPreviewPrice",
}
TRULY_UNSUPPORTED = UNSUPPORTED_FIELDS


# ── Operator logic ────────────────────────────────────────────────────────────

def _is_null(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, (list, dict)) and len(value) == 0:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


def _normalize_pattern(pattern: str) -> str:
    """Normalize SQL-style % wildcard to fnmatch-style * wildcard."""
    return pattern.replace("%", "*")


def _apply_operator(operator: str, value: Any, fact: str, field_type: str = "STRING") -> bool:
    """Apply an IMP operator against a resolved value and expected fact string."""
    op = operator.upper()
    fact = _normalize_pattern(fact)

    if op == "IS_NULL":
        return _is_null(value)

    if op == "NOT_NULL":
        return not _is_null(value)

    # Negation operators with a null value:
    # IMP treats null as "not equal / not matching / not containing any concrete value"
    # So all NOT_* operators PASS when the value is null/missing.
    #   null NOT_EQUALS true     → PASS  (null is not true)
    #   null NOT_IN [a,b,c]      → PASS  (null is not in any list)
    #   null NOT_MATCHES x*      → PASS  (null matches no pattern)
    #   null NOT_MATCHES_IN x*   → PASS  (null matches no pattern)
    #   null NOT_CONTAINS x      → PASS  (null contains nothing)
    NEGATION_OPS = {
        "NOT_EQUALS",
        "NOT_IN",
        "NOT_MATCHES",
        "NOT_MATCHES_IN",
        "NOT_CONTAINS",
        "NOT_CONTAINS_IN",
    }
    if op in NEGATION_OPS and _is_null(value):
        return True

    if _is_null(value):
        # All other non-null operators (EQUALS, IN, MATCHES, MATCHES_IN, CONTAINS,
        # GREATER_THAN, etc.) on a null value fail — null has no concrete value to compare.
        return False

    def _str_val(v: Any) -> str:
        """Normalize value to string for comparison — booleans use lowercase."""
        if isinstance(v, bool):
            return str(v).lower()  # True→"true", False→"false"
        return str(v)

    if op == "EQUALS":
        if isinstance(value, list):
            return any(fnmatch.fnmatch(_str_val(el), fact) for el in value)
        return fnmatch.fnmatch(_str_val(value), fact) if "*" in str(fact) else _str_val(value) == fact

    if op == "NOT_EQUALS":
        if isinstance(value, list):
            return not any(fnmatch.fnmatch(_str_val(el), fact) for el in value)
        return not fnmatch.fnmatch(_str_val(value), fact) if "*" in str(fact) else _str_val(value) != fact

    if op == "IN":
        allowed = [v.strip() for v in fact.split(",")]
        if isinstance(value, list):
            return any(fnmatch.fnmatch(str(el), p) for el in value for p in allowed)
        return any(fnmatch.fnmatch(str(value), p) for p in allowed)

    if op == "NOT_IN":
        allowed = [v.strip() for v in fact.split(",")]
        if isinstance(value, list):
            return not any(fnmatch.fnmatch(str(el), p) for el in value for p in allowed)
        return not any(fnmatch.fnmatch(str(value), p) for p in allowed)

    if op == "MATCHES":
        if isinstance(value, list):
            return any(fnmatch.fnmatch(str(el), fact) for el in value)
        return fnmatch.fnmatch(str(value), fact)

    if op == "NOT_MATCHES":
        if isinstance(value, list):
            return not any(fnmatch.fnmatch(str(el), fact) for el in value)
        return not fnmatch.fnmatch(str(value), fact)

    if op == "MATCHES_IN":
        patterns = [p.strip() for p in fact.split(",")]
        if isinstance(value, list):
            return any(fnmatch.fnmatch(str(el), p) for el in value for p in patterns)
        return any(fnmatch.fnmatch(str(value), p) for p in patterns)

    if op == "NOT_MATCHES_IN":
        patterns = [p.strip() for p in fact.split(",")]
        if isinstance(value, list):
            return not any(fnmatch.fnmatch(str(el), p) for el in value for p in patterns)
        return not any(fnmatch.fnmatch(str(value), p) for p in patterns)

    if op == "CONTAINS":
        if isinstance(value, list):
            return any(fnmatch.fnmatch(str(el), fact) for el in value)
        return fact in str(value)

    if op == "NOT_CONTAINS":
        if isinstance(value, list):
            patterns = [p.strip() for p in fact.split(",")]
            return not any(fnmatch.fnmatch(str(el), p) for el in value for p in patterns)
        return fact not in str(value)

    if op == "NOT_CONTAINS_IN":
        # NOT_CONTAINS_IN: value (or none of its elements) must NOT appear in the
        # comma-separated fact list.  Passes when the value is absent from the list.
        allowed = [p.strip() for p in fact.split(",")]
        if isinstance(value, list):
            return not any(fnmatch.fnmatch(str(el), p) for el in value for p in allowed)
        return not any(fnmatch.fnmatch(str(value), p) for p in allowed)

    if op in ("GREATER_THAN", "LESS_THAN", "GREATER_THAN_OR_EQUALS", "LESS_THAN_OR_EQUALS"):
        # Date comparison: value is epoch ms, fact is "today + N days" or just N (offset in days)
        try:
            fact_str = str(fact).strip()
            if "today" in fact_str.lower():
                m = re.search(r"[+-]?\s*\d+", fact_str.split("today")[-1])
                days_offset = int(m.group().replace(" ", "")) if m else 0
            else:
                days_offset = int(fact_str)
            now_ms = datetime.now(timezone.utc).timestamp() * 1000
            threshold_ms = now_ms + (days_offset * 86400 * 1000)
            val_ms = float(value)
            if op == "GREATER_THAN":
                return val_ms > threshold_ms
            if op == "GREATER_THAN_OR_EQUALS":
                return val_ms >= threshold_ms
            if op == "LESS_THAN_OR_EQUALS":
                return val_ms <= threshold_ms
            return val_ms < threshold_ms
        except (ValueError, TypeError):
            return False

    raise ValueError(f"Unknown operator: {operator}")


# ── Expression evaluator ──────────────────────────────────────────────────────

def _evaluate_expression(expression: str, condition_results: dict[str, bool | None]) -> bool | None:
    """
    Evaluate a boolean expression like '( #condition1 AND #condition2 OR #condition3 )'.

    Returns True/False if fully evaluable, None if undetermined (all relevant conditions skipped).
    Skipped (None) conditions are excluded from the expression and the remaining sub-expression
    is evaluated.
    """
    expr = expression.strip()

    for name, result in condition_results.items():
        if result is None:
            expr = re.sub(rf"#\b{re.escape(name)}\b", "__SKIP__", expr)
        else:
            expr = re.sub(rf"#\b{re.escape(name)}\b", str(result), expr)

    # Clean up SKIP tokens
    while "__SKIP__" in expr:
        expr = re.sub(r"\bAND\s+__SKIP__\b", "", expr)
        expr = re.sub(r"\b__SKIP__\s+AND\b", "", expr)
        expr = re.sub(r"\bOR\s+__SKIP__\b", "", expr)
        expr = re.sub(r"\b__SKIP__\s+OR\b", "", expr)
        expr = re.sub(r"\b__SKIP__\b", "", expr)

    expr = re.sub(r"\(\s*\)", "True", expr)
    expr = re.sub(r"\bAND\s*\)", ")", expr)
    expr = re.sub(r"\bOR\s*\)", ")", expr)
    expr = re.sub(r"\(\s*AND\b", "(", expr)
    expr = re.sub(r"\(\s*OR\b", "(", expr)
    expr = re.sub(r"\s+", " ", expr).strip()

    if not expr or expr in ("()", "( )", ""):
        return None

    try:
        safe_expr = expr.replace("AND", "and").replace("OR", "or").replace("NOT", "not")
        return bool(eval(safe_expr, {"__builtins__": {}}, {}))  # noqa: S307
    except Exception:
        return None


# ── Main evaluation entry point ───────────────────────────────────────────────

def evaluate_rule(
    rule_id: str,
    expression: str,
    conditions: list[dict],
    facts: dict[str, Any],
    engine_said_delist: bool = True,
) -> dict:
    """
    Deterministically evaluate a rule's boolean expression against resolved facts.

    Args:
        rule_id: The rule ID string.
        expression: The boolean expression string, e.g. "( #condition1 AND #condition2 )".
        conditions: List of condition dicts with keys: name, entry, operator, fact, type.
        facts: Dict mapping entry field name → resolved value. Missing = not fetched yet.
        engine_said_delist: Whether the OL engine reported this rule as fired.

    Returns:
        A structured result dict matching the design doc schema.
    """
    per_condition_results = []
    condition_bool_map: dict[str, bool | None] = {}
    cannot_evaluate_fields: list[dict] = []
    skipped_count = 0
    evaluated_count = 0

    for cond in conditions:
        name = cond.get("name", "")
        entry = cond.get("entry", "")
        operator = cond.get("operator", "")
        expected_fact = cond.get("fact", "")
        field_type = cond.get("type", "STRING")

        skip_reason = None
        condition_passed = None
        resolved_value = facts.get(entry)

        if entry in BQ_ONLY_FIELDS:
            skip_reason = f"BQ_ONLY: {entry} has no REST API; cannot evaluate on interactive path"
            cannot_evaluate_fields.append({
                "field": entry,
                "tier": "BQ_ONLY",
                "reason": "No REST API. Re-run in batch mode using BigQuery.",
            })
            skipped_count += 1
        elif entry in UNSUPPORTED_FIELDS:
            skip_reason = f"UNSUPPORTED: no API or BQ source exists for {entry}"
            cannot_evaluate_fields.append({
                "field": entry,
                "tier": "UNSUPPORTED",
                "reason": "No API or BQ source available. Cannot be verified in any mode.",
            })
            skipped_count += 1
        elif entry not in facts and resolved_value is None:
            skip_reason = f"MISSING: {entry} not in facts — relevant tool may not have been called"
            skipped_count += 1
        else:
            try:
                condition_passed = _apply_operator(operator, resolved_value, expected_fact, field_type)
                evaluated_count += 1
            except Exception as exc:
                skip_reason = f"EVAL_ERROR: {exc}"
                skipped_count += 1

        condition_bool_map[name] = condition_passed if skip_reason is None else None

        per_condition_results.append({
            "name": name,
            "entry": entry,
            "operator": operator,
            "expected_fact": expected_fact,
            "resolved_value": resolved_value,
            "condition_passed": condition_passed,
            "skip_reason": skip_reason,
        })

    expression_result = _evaluate_expression(expression, condition_bool_map)

    total = len(conditions)
    if skipped_count == 0:
        local_matches_engine = (expression_result == engine_said_delist)
        verdict = "VALID" if local_matches_engine else "INVALID"
    elif evaluated_count == 0:
        verdict = "CANNOT_EVALUATE"
        local_matches_engine = None
        expression_result = None
    else:
        # Some conditions skipped — check if skipped fields are on the critical path.
        # Evaluate the expression under two assumptions for skipped conditions:
        #   optimistic  → skipped = True  (best case for engine's delist claim)
        #   pessimistic → skipped = False (worst case)
        # If BOTH give the same result, the skipped conditions don't affect the
        # outcome — we can give a definitive INVALID / VALID verdict instead of PARTIAL.
        optimistic_map = {
            name: (True if result is None else result)
            for name, result in condition_bool_map.items()
        }
        pessimistic_map = {
            name: (False if result is None else result)
            for name, result in condition_bool_map.items()
        }
        opt_result = _evaluate_expression(expression, optimistic_map)
        pes_result = _evaluate_expression(expression, pessimistic_map)

        if opt_result is not None and pes_result is not None and opt_result == pes_result:
            expression_result = opt_result
            local_matches_engine = (expression_result == engine_said_delist)
            if local_matches_engine:
                verdict = "VALID"
            else:
                verdict = "INVALID"
        else:
            verdict = "PARTIAL"
            local_matches_engine = None

    return {
        "rule_id": rule_id,
        "per_condition_results": per_condition_results,
        "expression_result": expression_result,
        "engine_said_delist": engine_said_delist,
        "local_matches_engine": local_matches_engine,
        "verdict": verdict,
        "evaluated_count": evaluated_count,
        "skipped_count": skipped_count,
        "total_conditions": total,
        "cannot_evaluate_fields": cannot_evaluate_fields,
    }
