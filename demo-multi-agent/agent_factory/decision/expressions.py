"""Expression evaluator for YAML decision rule conditions.

Parses and evaluates a small, purpose-built expression language used in
``DecisionCondition.expressions``.  This extends the existing observation-code
matching (``all`` / ``any`` lists) with value-based conditions — enabling
decision rules that inspect *values* inside the observations dict rather than
just the presence of a code string.

No ``eval()`` or ``exec()`` is used anywhere in this module.  All evaluation
is implemented through explicit string parsing and a dispatch table.

Syntax
------
Binary (field vs literal)::

    <field_path> <op> <literal_value>

Unary (existence check)::

    <field_path> is_present
    <field_path> is_absent

Supported binary operators
---------------------------
``==``  ``!=``  ``>``  ``>=``  ``<``  ``<=``  ``contains``
``startswith``  ``endswith``

Field path resolution
---------------------
Dot-notation is supported for nested dicts::

    checks.api_check.count > 5
    checks.db_check.stale_hours >= 12
    symptom == API_UNREACHABLE
    affected_region contains us-east

Literal coercion
----------------
``true`` / ``false`` → ``bool``; numeric strings → ``int`` / ``float``;
everything else → ``str``.  Surrounding quotes (single or double) are stripped.

String comparisons use case-insensitive matching for ``==``, ``!=``,
``contains``, ``startswith``, and ``endswith``.  Numeric comparisons are
type-safe.

Error handling
--------------
* Unknown field path → ``False`` (rule does not fire; no exception).
* Parse failure → ``False`` + ``WARNING`` log (never crashes the engine).
* Type mismatch in comparison → ``False`` + ``WARNING`` log.
* Empty expression string → ``True`` (vacuously satisfied, acts as no-op).

Usage
-----
Called by :class:`~agent_factory.decision.engine.YAMLDecisionEngine`::

    from agent_factory.decision.expressions import evaluate_all_expressions

    matched = evaluate_all_expressions(rule.when.expressions, observations)
"""
from __future__ import annotations

import re
from typing import Any

from agent_factory.common.logging import get_logger

logger = get_logger("decision_expressions")

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Unary: "field.path is_present" / "field.path is_absent"
_UNARY_RE = re.compile(
    r"^\s*(?P<field>[\w.]+)\s+(?P<op>is_present|is_absent)\s*$",
    re.IGNORECASE,
)

# Binary: "field.path op literal_value"
# Operators ordered longest-first inside the alternation to prevent ">="
# being partially matched as ">" before the "=" is seen.
_BINARY_RE = re.compile(
    r"^\s*(?P<field>[\w.]+)\s+"
    r"(?P<op>>=|<=|!=|==|>|<|contains|startswith|endswith)"
    r"\s+(?P<value>.+?)\s*$",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate_expression(expr: str, observations: dict[str, Any]) -> bool:
    """Evaluate a single expression string against the observations dict.

    Behaviour on error is always ``False``; a ``WARNING`` is logged so
    pack authors can diagnose misconfigured expressions without crashing
    the decision engine.

    Args:
        expr: Expression string, e.g. ``"checks.api.count > 5"``.
        observations: The run's observation dict produced by diagnostic tools.

    Returns:
        ``True`` if the expression holds, ``False`` otherwise.
    """
    expr = expr.strip()
    if not expr:
        # Empty string is treated as a no-op (always satisfied).
        return True

    # ── Unary operators ────────────────────────────────────────────────
    m = _UNARY_RE.match(expr)
    if m:
        field_path = m.group("field")
        op = m.group("op").lower()
        found, _ = _resolve_field(field_path, observations)
        if op == "is_present":
            return found
        if op == "is_absent":
            return not found

    # ── Binary operators ───────────────────────────────────────────────
    m = _BINARY_RE.match(expr)
    if m:
        field_path = m.group("field")
        op = m.group("op").lower()
        raw_value = m.group("value")

        found, field_val = _resolve_field(field_path, observations)
        if not found:
            # Unknown field → expression is False (not an error; the
            # diagnostic that populates this field may not have run yet).
            return False

        literal = _coerce_literal(raw_value)

        try:
            return _apply_operator(op, field_val, literal)
        except (TypeError, ValueError) as exc:
            logger.warning(
                "Expression '%s': type mismatch evaluating %r %s %r: %s",
                expr, field_val, op, literal, exc,
            )
            return False

    logger.warning(
        "Expression '%s' could not be parsed — treating as False. "
        "Expected: '<field> <op> <value>' or '<field> is_present|is_absent'. "
        "Supported operators: ==, !=, >, >=, <, <=, contains, startswith, endswith.",
        expr,
    )
    return False


def evaluate_all_expressions(
    expressions: list[str],
    observations: dict[str, Any],
) -> bool:
    """Return ``True`` only if **all** expressions in the list hold.

    An empty list is vacuously ``True`` — consistent with how the ``all``
    observation-code list behaves in :class:`~agent_factory.ir.models.DecisionCondition`.

    Args:
        expressions: List of expression strings from a decision rule.
        observations: Current run's observation dict.

    Returns:
        ``True`` when every expression evaluates to ``True``.
    """
    return all(evaluate_expression(expr, observations) for expr in expressions)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _resolve_field(
    field_path: str, observations: dict[str, Any]
) -> tuple[bool, Any]:
    """Traverse a dot-notation path through the observations dict.

    Args:
        field_path: Dot-separated key path, e.g. ``"checks.api_check.count"``.
        observations: The observations dict to traverse.

    Returns:
        ``(found, value)`` — ``found`` is ``False`` when any segment of the
        path is missing or the current node is not a dict.
    """
    node: Any = observations
    for part in field_path.split("."):
        if not isinstance(node, dict):
            return False, None
        if part not in node:
            return False, None
        node = node[part]
    return True, node


def _coerce_literal(raw: str) -> Any:
    """Coerce a raw literal string from an expression to a Python value.

    Conversion order: ``bool`` → ``int`` → ``float`` → ``str`` (strip quotes).
    """
    stripped = raw.strip()

    if stripped.lower() == "true":
        return True
    if stripped.lower() == "false":
        return False

    try:
        return int(stripped)
    except ValueError:
        pass

    try:
        return float(stripped)
    except ValueError:
        pass

    # Strip surrounding single or double quotes
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in ('"', "'"):
        return stripped[1:-1]

    return stripped


def _apply_operator(op: str, field_val: Any, literal: Any) -> bool:
    """Dispatch to the correct comparison for the given operator.

    For ``==`` and ``!=``, string comparisons are case-insensitive.
    For ordering operators (``>``, ``>=``, ``<``, ``<=``), numeric coercion
    of string field values is attempted when the literal is numeric.

    Args:
        op: Lowercase operator string.
        field_val: Value resolved from the observations dict.
        literal: Coerced literal from the expression string.

    Returns:
        Boolean result of the comparison.

    Raises:
        TypeError: Propagated to the caller when types are incompatible
            (e.g. comparing a list to an integer).
    """
    # Attempt numeric coercion: if we're comparing a string field against
    # a numeric literal, cast the field value first.
    if isinstance(literal, (int, float)) and isinstance(field_val, str):
        try:
            field_val = type(literal)(field_val)
        except (ValueError, TypeError):
            pass  # leave field_val as-is; comparison will raise TypeError

    if op == "==":
        if isinstance(field_val, str) and isinstance(literal, str):
            return field_val.casefold() == literal.casefold()
        return field_val == literal

    if op == "!=":
        if isinstance(field_val, str) and isinstance(literal, str):
            return field_val.casefold() != literal.casefold()
        return field_val != literal

    if op == ">":
        return field_val > literal  # type: ignore[operator]

    if op == ">=":
        return field_val >= literal  # type: ignore[operator]

    if op == "<":
        return field_val < literal  # type: ignore[operator]

    if op == "<=":
        return field_val <= literal  # type: ignore[operator]

    if op == "contains":
        if isinstance(field_val, str) and isinstance(literal, str):
            return literal.casefold() in field_val.casefold()
        if isinstance(field_val, (list, tuple, set)):
            return literal in field_val
        return False

    if op == "startswith":
        if isinstance(field_val, str) and isinstance(literal, str):
            return field_val.casefold().startswith(literal.casefold())
        return False

    if op == "endswith":
        if isinstance(field_val, str) and isinstance(literal, str):
            return field_val.casefold().endswith(literal.casefold())
        return False

    # Should be unreachable given the regex gate, but be explicit.
    logger.warning("Unknown operator: %r — treating as False.", op)
    return False
