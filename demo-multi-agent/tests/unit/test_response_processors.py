"""Unit tests for agent_factory.tools.response_processors.

Covers the upgraded helpers introduced in Phase 2:
  - _get_nested: dot-path + array-index resolution
  - _evaluate_condition: numeric, IN, contains/startswith/endswith,
                          OR/AND, dot-path fields, fallback
  - Processor functions: passthrough, count_filter, priority_match,
                          any_match, first_field, field_presence
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_factory.tools.response_processors import (
    _get_nested,
    _evaluate_condition,
    _resolve_context_field,
    apply_processor,
    process_passthrough,
    process_count_filter,
    process_priority_match,
    process_any_match,
    process_first_field,
    process_field_presence,
)


# ---------------------------------------------------------------------------
# _get_nested — dot-path + array-index
# ---------------------------------------------------------------------------

class TestGetNested:

    def test_flat_key(self):
        assert _get_nested({"a": 1}, "a") == 1

    def test_dot_path(self):
        assert _get_nested({"a": {"b": {"c": 42}}}, "a.b.c") == 42

    def test_missing_key_returns_none(self):
        assert _get_nested({"a": 1}, "b") is None

    def test_missing_nested_key_returns_none(self):
        assert _get_nested({"a": {}}, "a.b") is None

    def test_intermediate_not_dict_returns_none(self):
        assert _get_nested({"a": "string"}, "a.b") is None

    def test_array_index_top_level(self):
        data = {"items": ["x", "y", "z"]}
        assert _get_nested(data, "items[1]") == "y"

    def test_array_index_zero(self):
        data = {"items": [{"name": "first"}, {"name": "second"}]}
        assert _get_nested(data, "items[0]") == {"name": "first"}

    def test_array_index_followed_by_key(self):
        data = {"records": [{"status": "active"}, {"status": "inactive"}]}
        assert _get_nested(data, "records[0].status") == "active"
        assert _get_nested(data, "records[1].status") == "inactive"

    def test_array_index_out_of_range_returns_none(self):
        data = {"items": [1, 2]}
        assert _get_nested(data, "items[5]") is None

    def test_nested_then_array(self):
        data = {"data": {"rows": [{"val": 99}]}}
        assert _get_nested(data, "data.rows[0].val") == 99

    def test_none_data_returns_none(self):
        assert _get_nested(None, "a.b") is None

    def test_empty_list_index_returns_none(self):
        assert _get_nested({"items": []}, "items[0]") is None


# ---------------------------------------------------------------------------
# _evaluate_condition — comprehensive
# ---------------------------------------------------------------------------

class TestEvaluateCondition:

    # ── Fallback ─────────────────────────────────────────────────────

    def test_empty_string_is_true(self):
        assert _evaluate_condition("", {}) is True

    def test_whitespace_is_true(self):
        assert _evaluate_condition("   ", {}) is True

    # ── Truthy check ─────────────────────────────────────────────────

    def test_truthy_present_field(self):
        assert _evaluate_condition("count", {"count": 5}) is True

    def test_truthy_zero_is_false(self):
        assert _evaluate_condition("count", {"count": 0}) is False

    def test_truthy_missing_field(self):
        assert _evaluate_condition("missing", {}) is False

    # ── Numeric comparisons ───────────────────────────────────────────

    def test_numeric_gt(self):
        assert _evaluate_condition("count > 3", {"count": 5}) is True
        assert _evaluate_condition("count > 5", {"count": 5}) is False

    def test_numeric_gte(self):
        assert _evaluate_condition("count >= 5", {"count": 5}) is True
        assert _evaluate_condition("count >= 6", {"count": 5}) is False

    def test_numeric_lt(self):
        assert _evaluate_condition("count < 10", {"count": 5}) is True
        assert _evaluate_condition("count < 5", {"count": 5}) is False

    def test_numeric_lte(self):
        assert _evaluate_condition("count <= 5", {"count": 5}) is True
        assert _evaluate_condition("count <= 4", {"count": 5}) is False

    def test_numeric_eq(self):
        assert _evaluate_condition("count == 5", {"count": 5}) is True
        assert _evaluate_condition("count == 6", {"count": 5}) is False

    def test_numeric_neq(self):
        assert _evaluate_condition("count != 5", {"count": 3}) is True

    def test_numeric_float_value(self):
        assert _evaluate_condition("rate >= 0.5", {"rate": 0.75}) is True
        assert _evaluate_condition("rate >= 0.9", {"rate": 0.75}) is False

    def test_numeric_negative_value(self):
        assert _evaluate_condition("delta > -1", {"delta": 0}) is True

    def test_numeric_string_coercion(self):
        """Field stored as string should be coerced to numeric for comparison."""
        assert _evaluate_condition("count > 3", {"count": "5"}) is True

    def test_numeric_dot_path(self):
        ctx = {"checks": {"api": {"error_count": 7}}}
        assert _evaluate_condition("checks.api.error_count >= 5", ctx) is True
        assert _evaluate_condition("checks.api.error_count >= 10", ctx) is False

    def test_numeric_array_index_path(self):
        ctx = {"records": [{"val": 10}, {"val": 2}]}
        assert _evaluate_condition("records[0].val > 5", ctx) is True
        assert _evaluate_condition("records[1].val > 5", ctx) is False

    # ── IN membership ─────────────────────────────────────────────────

    def test_in_matches(self):
        assert _evaluate_condition(
            "status IN [active, pending]", {"status": "active"}
        ) is True

    def test_in_no_match(self):
        assert _evaluate_condition(
            "status IN [active, pending]", {"status": "deleted"}
        ) is False

    def test_in_case_insensitive(self):
        assert _evaluate_condition(
            "status IN [Active, Pending]", {"status": "active"}
        ) is True

    def test_in_quoted_values(self):
        assert _evaluate_condition(
            "status IN ['active', 'pending']", {"status": "active"}
        ) is True

    # ── contains ─────────────────────────────────────────────────────

    def test_contains_substring(self):
        assert _evaluate_condition("region contains us-east", {"region": "us-east-1"}) is True
        assert _evaluate_condition("region contains eu-west", {"region": "us-east-1"}) is False

    def test_contains_case_insensitive(self):
        assert _evaluate_condition("msg contains error", {"msg": "ERROR: disk full"}) is True

    def test_contains_list_membership(self):
        ctx = {"affected": ["us-east-1", "eu-west-1"]}
        assert _evaluate_condition("affected contains us-east-1", ctx) is True
        assert _evaluate_condition("affected contains ap-south-1", ctx) is False

    def test_contains_dot_path(self):
        ctx = {"checks": {"api": {"message": "ERROR occurred"}}}
        assert _evaluate_condition("checks.api.message contains error", ctx) is True

    # ── startswith ────────────────────────────────────────────────────

    def test_startswith_matches(self):
        assert _evaluate_condition("incident startswith INC", {"incident": "INC001"}) is True
        assert _evaluate_condition("incident startswith CHG", {"incident": "INC001"}) is False

    def test_startswith_case_insensitive(self):
        assert _evaluate_condition("incident startswith inc", {"incident": "INC001"}) is True

    # ── endswith ──────────────────────────────────────────────────────

    def test_endswith_matches(self):
        assert _evaluate_condition("host endswith primary", {"host": "db-primary"}) is True
        assert _evaluate_condition("host endswith replica", {"host": "db-primary"}) is False

    def test_endswith_case_insensitive(self):
        assert _evaluate_condition("host endswith PRIMARY", {"host": "db-primary"}) is True

    # ── OR / AND ──────────────────────────────────────────────────────

    def test_or_first_truthy(self):
        ctx = {"a": 1, "b": 0}
        assert _evaluate_condition("a OR b", ctx) is True

    def test_or_both_falsy(self):
        assert _evaluate_condition("a OR b", {"a": 0, "b": 0}) is False

    def test_and_both_truthy(self):
        ctx = {"a": 1, "b": 2}
        assert _evaluate_condition("a AND b", ctx) is True

    def test_and_one_falsy(self):
        ctx = {"a": 1, "b": 0}
        assert _evaluate_condition("a AND b", ctx) is False

    def test_or_three_fields(self):
        assert _evaluate_condition("x OR y OR z", {"x": 0, "y": 0, "z": 1}) is True


# ---------------------------------------------------------------------------
# process_count_filter — array extraction paths
# ---------------------------------------------------------------------------

class TestProcessCountFilter:

    def _make_rc(self, **kwargs):
        rc = MagicMock()
        rc.processor = "count_filter"
        rc.array_path = kwargs.get("array_path", "")
        rc.filter_field = kwargs.get("filter_field", "")
        rc.filter_values = kwargs.get("filter_values", [])
        # `filter_fields` enables multi-field AND-mode in
        # process_count_filter; default it to an empty list so the
        # default mock falls through to single-field mode.  Without
        # this, MagicMock auto-attribute returns a truthy mock and
        # forces the wrong branch.
        rc.filter_fields = kwargs.get("filter_fields", [])
        rc.extract_fields = kwargs.get("extract_fields", {})
        rc.outcome_rules = []
        rc.include_raw = False
        return rc

    def test_list_input_total(self):
        rc = self._make_rc()
        result = process_count_filter([1, 2, 3], rc, {})
        assert result["total"] == 3
        assert result["count"] == 3

    def test_array_path_extraction(self):
        data = {"data": {"records": [{"s": "ok"}, {"s": "err"}, {"s": "ok"}]}}
        rc = self._make_rc(array_path="data.records", filter_field="s", filter_values=["ok"])
        result = process_count_filter(data, rc, {})
        assert result["count"] == 2
        assert result["total"] == 3

    def test_filter_case_insensitive(self):
        data = [{"status": "OK"}, {"status": "ERROR"}, {"status": "ok"}]
        rc = self._make_rc(filter_field="status", filter_values=["ok"])
        result = process_count_filter(data, rc, {})
        assert result["count"] == 2

    def test_no_filter_counts_all(self):
        data = [{"s": "a"}, {"s": "b"}]
        rc = self._make_rc()
        result = process_count_filter(data, rc, {})
        assert result["count"] == 2


# ---------------------------------------------------------------------------
# process_priority_match — basic
# ---------------------------------------------------------------------------

class TestProcessPriorityMatch:

    def _make_rc(self, priority_field="state", priority_order=None):
        rc = MagicMock()
        rc.array_path = ""
        rc.priority_field = priority_field
        rc.priority_order = priority_order or ["current", "ready", "upcoming"]
        rc.extract_fields = {}
        rc.outcome_rules = []
        rc.include_raw = False
        return rc

    def test_finds_highest_priority(self):
        data = [
            {"state": "upcoming", "id": 3},
            {"state": "ready", "id": 2},
            {"state": "current", "id": 1},
        ]
        rc = self._make_rc()
        result = process_priority_match(data, rc, {})
        assert result["matched_status"] == "current"
        assert result["matched_priority"] == 0

    def test_no_match(self):
        data = [{"state": "unknown"}]
        rc = self._make_rc()
        result = process_priority_match(data, rc, {})
        assert result["matched_status"] is None
        assert result["matched_priority"] == -1


# ---------------------------------------------------------------------------
# process_any_match
# ---------------------------------------------------------------------------

class TestProcessAnyMatch:

    def _make_rc(self, filter_field="", filter_values=None):
        rc = MagicMock()
        rc.array_path = ""
        rc.filter_field = filter_field
        rc.filter_values = filter_values or []
        rc.extract_fields = {}
        rc.outcome_rules = []
        rc.include_raw = False
        return rc

    def test_any_matched_true(self):
        data = [{"confirmed": "yes"}, {"confirmed": "no"}]
        rc = self._make_rc(filter_field="confirmed", filter_values=["yes"])
        result = process_any_match(data, rc, {})
        assert result["any_matched"] is True

    def test_any_matched_false(self):
        data = [{"confirmed": "no"}]
        rc = self._make_rc(filter_field="confirmed", filter_values=["yes"])
        result = process_any_match(data, rc, {})
        assert result["any_matched"] is False

    def test_no_filter_truthy_when_non_empty(self):
        rc = self._make_rc()
        result = process_any_match([1, 2, 3], rc, {})
        assert result["any_matched"] is True

    def test_no_filter_falsy_when_empty(self):
        rc = self._make_rc()
        result = process_any_match([], rc, {})
        assert result["any_matched"] is False


# ---------------------------------------------------------------------------
# process_first_field
# ---------------------------------------------------------------------------

class TestProcessFirstField:

    def _make_rc(self, extract_field="", extract_fields=None):
        rc = MagicMock()
        rc.array_path = ""
        rc.extract_field = extract_field
        rc.extract_fields = extract_fields or {}
        rc.outcome_rules = []
        rc.include_raw = False
        return rc

    def test_extract_field_from_first_record(self):
        data = [{"assignment": "Y"}, {"assignment": "N"}]
        rc = self._make_rc(extract_field="assignment")
        result = process_first_field(data, rc, {})
        assert result["value"] == "Y"

    def test_empty_list_returns_none(self):
        rc = self._make_rc(extract_field="assignment")
        result = process_first_field([], rc, {})
        assert result["value"] is None

    def test_dict_input_wrapped(self):
        rc = self._make_rc(extract_field="status")
        result = process_first_field({"status": "ok"}, rc, {})
        assert result["value"] == "ok"


# ---------------------------------------------------------------------------
# apply_processor — include_raw and unknown processor fallback
# ---------------------------------------------------------------------------

class TestApplyProcessor:

    def _make_rc(self, include_raw=False):
        rc = MagicMock()
        rc.processor = "passthrough"
        rc.extract_fields = {}
        rc.outcome_rules = []
        rc.include_raw = include_raw
        return rc

    def test_include_raw_attaches_original_data(self):
        rc = self._make_rc(include_raw=True)
        data = {"key": "value"}
        result = apply_processor("passthrough", data, rc, {})
        assert result["raw"] == data

    def test_unknown_processor_falls_back_to_passthrough(self):
        rc = self._make_rc()
        data = {"x": 1}
        result = apply_processor("nonexistent_processor", data, rc, {})
        assert result["data"] == data
