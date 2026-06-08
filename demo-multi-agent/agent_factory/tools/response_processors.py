"""Built-in response processors for declarative tools.

These processors handle the common patterns that appear in API/DB tool
responses — field extraction, outcome derivation, counting, filtering,
and priority matching.  By handling these generically, packs can define
tools entirely in YAML without writing Python.

Each processor takes:
  - data: the raw response data (dict or list)
  - response_config: the ResponseConfig from the tool spec
  - params: the original request parameters (for echo-back)

And returns:
  - dict with "outcome" (if rules matched), extracted fields, and optionally "raw"
"""
from __future__ import annotations

import re
from typing import Any

from agent_factory.common.logging import get_logger

logger = get_logger("response_processor")

# Pre-compiled pattern for array-index path segments: "items[2]"
_ARRAY_INDEX_RE = re.compile(r'^(\w+)\[(\d+)\]$')


def _get_nested(data: Any, path: str) -> Any:
    """Resolve a dot-separated path with optional array indexing.

    Supports:
      - ``"data.records"``         → ``data["data"]["records"]``
      - ``"data.records[0]"``      → ``data["data"]["records"][0]``
      - ``"data.records[0].name"`` → ``data["data"]["records"][0]["name"]``

    Returns ``None`` for any path segment that cannot be resolved (missing
    dict key, out-of-range list index, or wrong intermediate type) rather
    than raising an exception.
    """
    # Split on dots that are NOT inside square brackets
    # e.g. "a.b[0].c" → ["a", "b[0]", "c"]
    parts = re.split(r'\.(?![^\[]*\])', path)
    current = data
    for part in parts:
        if current is None:
            return None
        idx_match = _ARRAY_INDEX_RE.match(part)
        if idx_match:
            key, idx = idx_match.group(1), int(idx_match.group(2))
            if isinstance(current, dict):
                current = current.get(key)
            else:
                return None
            if isinstance(current, list):
                current = current[idx] if idx < len(current) else None
            else:
                return None
        elif isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _extract_field_with_fallbacks(data: dict, source_spec: str) -> Any:
    """Extract a field value using pipe-separated fallback chain.

    Example: "footage|totalFootage" → try data["footage"], then data["totalFootage"]
    """
    for field_name in source_spec.split("|"):
        field_name = field_name.strip()
        value = _get_nested(data, field_name)
        if value is not None:
            return value
    return None


def _apply_extract_fields(data: dict, extract_fields: dict[str, str]) -> dict[str, Any]:
    """Apply field extraction mappings to response data."""
    extracted = {}
    if not isinstance(data, dict):
        return extracted
    for target_name, source_spec in extract_fields.items():
        extracted[target_name] = _extract_field_with_fallbacks(data, source_spec)
    return extracted


def _resolve_context_field(field: str, context: dict[str, Any]) -> Any:
    """Resolve a field name from the condition context.

    Supports both flat keys (``"count"``) and dot-path keys
    (``"checks.api.error_count"``).
    """
    if "." in field or "[" in field:
        return _get_nested(context, field)
    return context.get(field)


def _evaluate_condition(condition: str, context: dict[str, Any]) -> bool:
    """Evaluate a simple condition expression against a context dict.

    Supported patterns:
      - ``""``                           → True (default / fallback rule)
      - ``"field_name"``                 → truthy check
      - ``"field1 OR field2"``           → any truthy (no short-circuit)
      - ``"field1 AND field2"``          → all truthy (no short-circuit)
      - ``"count > 1"``                  → numeric comparison (``>``, ``<``, ``>=``, ``<=``, ``==``, ``!=``)
      - ``"field IN [val1, val2]"``      → case-insensitive membership check
      - ``"field contains substr"``      → case-insensitive substring / list membership
      - ``"field startswith prefix"``    → case-insensitive prefix check
      - ``"field endswith suffix"``      → case-insensitive suffix check

    Field names may use dot-notation (e.g. ``"checks.api.count"``) or
    array indexing (e.g. ``"records[0].status"``).

    The OR / AND operators split on the literal tokens `` OR `` and
    `` AND `` (case-insensitive, space-padded) and evaluate each operand
    as a simple truthy check — they do NOT support nested comparisons.
    Use ``outcome_rules`` with multiple ``when`` clauses for complex logic.
    """
    condition = condition.strip()
    if not condition:
        return True  # Default/fallback rule always matches

    # ── Numeric comparison ────────────────────────────────────────────
    # "count > 1", "checks.api.count >= 5", "records[0].age != 0"
    numeric_match = re.match(
        r'^([\w.\[\]]+)\s*(>=|<=|>|<|==|!=)\s*(-?\d+(?:\.\d+)?)$', condition
    )
    if numeric_match:
        field, op, value_str = numeric_match.groups()
        raw = _resolve_context_field(field, context)
        try:
            field_val = float(raw) if raw is not None else 0.0
        except (ValueError, TypeError):
            field_val = 0.0
        target = float(value_str)
        ops = {
            ">": field_val > target, "<": field_val < target,
            ">=": field_val >= target, "<=": field_val <= target,
            "==": field_val == target, "!=": field_val != target,
        }
        return ops.get(op, False)

    # ── IN membership ─────────────────────────────────────────────────
    # "status IN [active, pending]"
    in_match = re.match(r'^([\w.\[\]]+)\s+IN\s+\[(.+)]$', condition, re.IGNORECASE)
    if in_match:
        field, values_str = in_match.groups()
        field_val = str(_resolve_context_field(field, context) or "").lower()
        values = [v.strip().strip("'\"").lower() for v in values_str.split(",")]
        return field_val in values

    # ── String operators ──────────────────────────────────────────────
    # "region contains us-east"
    contains_match = re.match(
        r'^([\w.\[\]]+)\s+contains\s+(.+)$', condition, re.IGNORECASE
    )
    if contains_match:
        field, substr = contains_match.groups()
        field_val = _resolve_context_field(field, context)
        substr = substr.strip().strip("'\"").lower()
        if isinstance(field_val, list):
            return substr in [str(v).lower() for v in field_val]
        return substr in str(field_val or "").lower()

    # "incident startswith INC"
    startswith_match = re.match(
        r'^([\w.\[\]]+)\s+startswith\s+(.+)$', condition, re.IGNORECASE
    )
    if startswith_match:
        field, prefix = startswith_match.groups()
        field_val = str(_resolve_context_field(field, context) or "").lower()
        return field_val.startswith(prefix.strip().strip("'\"").lower())

    # "host endswith primary"
    endswith_match = re.match(
        r'^([\w.\[\]]+)\s+endswith\s+(.+)$', condition, re.IGNORECASE
    )
    if endswith_match:
        field, suffix = endswith_match.groups()
        field_val = str(_resolve_context_field(field, context) or "").lower()
        return field_val.endswith(suffix.strip().strip("'\"").lower())

    # ── Boolean combinators ───────────────────────────────────────────
    # OR: "field1 OR field2 OR field3"
    if re.search(r'\s+OR\s+', condition, re.IGNORECASE):
        parts = re.split(r'\s+OR\s+', condition, flags=re.IGNORECASE)
        return any(bool(_resolve_context_field(p.strip(), context)) for p in parts)

    # AND: "field1 AND field2"
    if re.search(r'\s+AND\s+', condition, re.IGNORECASE):
        parts = re.split(r'\s+AND\s+', condition, flags=re.IGNORECASE)
        return all(bool(_resolve_context_field(p.strip(), context)) for p in parts)

    # ── Simple truthy check ───────────────────────────────────────────
    return bool(_resolve_context_field(condition, context))


def _evaluate_outcome_rules(rules: list, context: dict[str, Any]) -> str | None:
    """Evaluate outcome rules in order and return the first matching outcome."""
    for rule in rules:
        if _evaluate_condition(rule.when, context):
            return rule.outcome
    return None


# ── Processors ──────────────────────────────────────────────────────

def process_passthrough(data: Any, response_config, params: dict) -> dict:
    """Return raw data as-is with optional field extraction."""
    result = {"data": data, **params}
    if response_config.extract_fields and isinstance(data, dict):
        result.update(_apply_extract_fields(data, response_config.extract_fields))
    if response_config.outcome_rules:
        outcome = _evaluate_outcome_rules(response_config.outcome_rules, result)
        if outcome:
            result["outcome"] = outcome
    return result


def process_field_presence(data: Any, response_config, params: dict) -> dict:
    """Check if specified fields exist in the response.

    Sets 'has_fields' = True if ANY of presence_fields are truthy.
    Useful for: "does this API record exist?" patterns.
    """
    result = {**params}

    if isinstance(data, dict):
        if response_config.extract_fields:
            result.update(_apply_extract_fields(data, response_config.extract_fields))

        has_fields = any(
            bool(_get_nested(data, f))
            for f in response_config.presence_fields
        ) if response_config.presence_fields else False
        result["has_fields"] = has_fields
    else:
        result["has_fields"] = False

    if response_config.outcome_rules:
        outcome = _evaluate_outcome_rules(response_config.outcome_rules, result)
        if outcome:
            result["outcome"] = outcome

    return result


def process_count_filter(data: Any, response_config, params: dict) -> dict:
    """Count records in an array that match a filter condition.

    Sets 'count' = number of matching records, 'total' = total records.
    Useful for: "how many active records?" → DUPLICATES / PRESENT / ABSENT.
    """
    result = {**params}

    # Resolve array from response
    if response_config.array_path and isinstance(data, dict):
        records = _get_nested(data, response_config.array_path) or []
    elif isinstance(data, list):
        records = data
    elif isinstance(data, dict):
        # Try common array keys
        records = data.get("result") or data.get("data") or data.get("records") or data.get("rows") or []
    else:
        records = []

    if not isinstance(records, list):
        records = [records] if records else []

    total = len(records)
    result["total"] = total

    # Apply filter — supports single-field mode and multi-field AND mode
    filter_fields_cfg = getattr(response_config, "filter_fields", []) or []
    if filter_fields_cfg:
        # Multi-field AND mode: each entry is "field=value" (case-insensitive).
        # A record matches only if ALL conditions are satisfied.
        conditions = []
        for entry in filter_fields_cfg:
            if "=" in entry:
                f, v = entry.split("=", 1)
                conditions.append((f.strip(), v.strip().lower()))
        matching = [
            r for r in records
            if isinstance(r, dict) and all(
                str(r.get(f, "")).lower() == v for f, v in conditions
            )
        ]
        result["count"] = len(matching)
        result["matching_records"] = matching
    elif response_config.filter_field and response_config.filter_values:
        accepted = {v.lower() for v in response_config.filter_values}
        matching = [
            r for r in records
            if isinstance(r, dict) and
            str(r.get(response_config.filter_field, "")).lower() in accepted
        ]
        result["count"] = len(matching)
        result["matching_records"] = matching
    else:
        result["count"] = total
        result["matching_records"] = records

    if response_config.extract_fields:
        extracted = {}
        # Try extracting from the full response first (for sibling paths
        # like payload.product.product_attributes that live outside the
        # filtered array).
        if isinstance(data, dict):
            extracted.update(_apply_extract_fields(data, response_config.extract_fields))
        # Then try from the first matching record (for fields inside the
        # filtered items). Values from the record override None values
        # from the full response.
        if result["matching_records"]:
            first = result["matching_records"][0]
            if isinstance(first, dict):
                record_fields = _apply_extract_fields(first, response_config.extract_fields)
                for k, v in record_fields.items():
                    if v is not None:
                        extracted[k] = v
        # Only set non-None values
        for k, v in extracted.items():
            if v is not None:
                result[k] = v

    if response_config.outcome_rules:
        outcome = _evaluate_outcome_rules(response_config.outcome_rules, result)
        if outcome:
            result["outcome"] = outcome

    return result


def process_priority_match(data: Any, response_config, params: dict) -> dict:
    """Find the highest-priority status value from array records.

    Useful for: "what's the most important status?" → CURRENT > READY > UPCOMING.
    """
    result = {**params}

    if response_config.array_path and isinstance(data, dict):
        records = _get_nested(data, response_config.array_path) or []
    elif isinstance(data, list):
        records = data
    elif isinstance(data, dict):
        records = data.get("result") or data.get("data") or data.get("records") or []
    else:
        records = []

    if not isinstance(records, list):
        records = [records] if records else []

    result["total"] = len(records)

    # Find highest-priority match
    priority_field = response_config.priority_field
    priority_order = [v.lower() for v in response_config.priority_order]
    best_priority = len(priority_order)
    best_value = None

    for record in records:
        if not isinstance(record, dict):
            continue
        val = str(record.get(priority_field, "")).lower()
        if val in priority_order:
            idx = priority_order.index(val)
            if idx < best_priority:
                best_priority = idx
                best_value = val

    result["matched_status"] = best_value
    result["matched_priority"] = best_priority if best_value else -1

    if response_config.extract_fields and records:
        # Extract from the record with the best priority
        for record in records:
            if isinstance(record, dict) and str(record.get(priority_field, "")).lower() == best_value:
                result.update(_apply_extract_fields(record, response_config.extract_fields))
                break

    if response_config.outcome_rules:
        outcome = _evaluate_outcome_rules(response_config.outcome_rules, result)
        if outcome:
            result["outcome"] = outcome

    return result


def process_any_match(data: Any, response_config, params: dict) -> dict:
    """Check if ANY record in an array matches a condition.

    Sets 'any_matched' = True/False.
    Useful for: "is any record confirmed?" → CONFIRMED / UNCONFIRMED.
    """
    result = {**params}

    if response_config.array_path and isinstance(data, dict):
        records = _get_nested(data, response_config.array_path) or []
    elif isinstance(data, list):
        records = data
    elif isinstance(data, dict):
        records = data.get("result") or data.get("data") or data.get("records") or []
    else:
        records = []

    if not isinstance(records, list):
        records = [records] if records else []

    result["total"] = len(records)

    # Check filter condition
    if response_config.filter_field and response_config.filter_values:
        accepted = {v.lower() for v in response_config.filter_values}
        any_matched = any(
            isinstance(r, dict) and
            str(r.get(response_config.filter_field, "")).lower() in accepted
            for r in records
        )
    else:
        any_matched = len(records) > 0

    result["any_matched"] = any_matched

    if response_config.extract_fields and records:
        first = records[0]
        if isinstance(first, dict):
            result.update(_apply_extract_fields(first, response_config.extract_fields))

    if response_config.outcome_rules:
        outcome = _evaluate_outcome_rules(response_config.outcome_rules, result)
        if outcome:
            result["outcome"] = outcome

    return result


def process_first_field(data: Any, response_config, params: dict) -> dict:
    """Extract a specific field from the first record.

    Useful for: "what's the assignment status of the top row?" → Y | N | I | F | E.
    """
    result = {**params}

    if response_config.array_path and isinstance(data, dict):
        records = _get_nested(data, response_config.array_path) or []
    elif isinstance(data, list):
        records = data
    elif isinstance(data, dict) and "rows" in data:
        records = data["rows"]
    else:
        records = [data] if isinstance(data, dict) else []

    if not isinstance(records, list):
        records = [records] if records else []

    result["total"] = len(records)

    if records and isinstance(records[0], dict):
        first = records[0]
        if response_config.extract_field:
            result["value"] = first.get(response_config.extract_field)
        if response_config.extract_fields:
            result.update(_apply_extract_fields(first, response_config.extract_fields))
    else:
        result["value"] = None

    if response_config.outcome_rules:
        outcome = _evaluate_outcome_rules(response_config.outcome_rules, result)
        if outcome:
            result["outcome"] = outcome

    return result


# ── Processor Registry ──────────────────────────────────────────────

PROCESSORS = {
    "passthrough": process_passthrough,
    "field_presence": process_field_presence,
    "count_filter": process_count_filter,
    "priority_match": process_priority_match,
    "any_match": process_any_match,
    "first_field": process_first_field,
}


def apply_processor(
    processor_name: str,
    data: Any,
    response_config,
    params: dict,
) -> dict:
    """Apply a named processor to response data.

    Falls back to passthrough if the processor name is unknown.
    """
    processor_fn = PROCESSORS.get(processor_name, process_passthrough)
    try:
        result = processor_fn(data, response_config, params)
        if response_config.include_raw:
            result["raw"] = data
        return result
    except Exception as e:
        logger.error(f"Response processor '{processor_name}' failed: {e}", exc_info=True)
        return {"error": f"Response processing failed: {e}", "raw": data, **params}
