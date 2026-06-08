"""Unit tests for agent_factory.decision.expressions — expression evaluator."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_factory.decision.expressions import (
    evaluate_expression,
    evaluate_all_expressions,
    _resolve_field,
    _coerce_literal,
    _apply_operator,
)


# ---------------------------------------------------------------------------
# _resolve_field
# ---------------------------------------------------------------------------

class TestResolveField:

    def test_top_level_key(self):
        found, val = _resolve_field("status", {"status": "healthy"})
        assert found is True
        assert val == "healthy"

    def test_nested_key(self):
        obs = {"checks": {"api": {"count": 5}}}
        found, val = _resolve_field("checks.api.count", obs)
        assert found is True
        assert val == 5

    def test_missing_top_level(self):
        found, val = _resolve_field("missing", {})
        assert found is False
        assert val is None

    def test_missing_nested(self):
        found, val = _resolve_field("checks.missing.field", {"checks": {}})
        assert found is False
        assert val is None

    def test_intermediate_not_a_dict(self):
        found, val = _resolve_field("status.sub", {"status": "hello"})
        assert found is False
        assert val is None


# ---------------------------------------------------------------------------
# _coerce_literal
# ---------------------------------------------------------------------------

class TestCoerceLiteral:

    def test_true(self):
        assert _coerce_literal("true") is True
        assert _coerce_literal("True") is True
        assert _coerce_literal("TRUE") is True

    def test_false(self):
        assert _coerce_literal("false") is False

    def test_integer(self):
        assert _coerce_literal("42") == 42
        assert isinstance(_coerce_literal("42"), int)

    def test_negative_integer(self):
        assert _coerce_literal("-5") == -5

    def test_float(self):
        assert _coerce_literal("3.14") == pytest.approx(3.14)

    def test_string_unquoted(self):
        assert _coerce_literal("API_DOWN") == "API_DOWN"

    def test_string_double_quoted(self):
        assert _coerce_literal('"hello world"') == "hello world"

    def test_string_single_quoted(self):
        assert _coerce_literal("'us-east-1'") == "us-east-1"

    def test_string_with_spaces(self):
        assert _coerce_literal("  hello  ") == "hello"


# ---------------------------------------------------------------------------
# evaluate_expression — unary operators
# ---------------------------------------------------------------------------

class TestUnaryOperators:

    def test_is_present_found(self):
        assert evaluate_expression("status is_present", {"status": "ok"}) is True

    def test_is_present_missing(self):
        assert evaluate_expression("status is_present", {}) is False

    def test_is_absent_missing(self):
        assert evaluate_expression("backup is_absent", {}) is True

    def test_is_absent_present(self):
        assert evaluate_expression("backup is_absent", {"backup": "s3://bucket"}) is False

    def test_is_present_nested(self):
        obs = {"checks": {"db": {"count": 3}}}
        assert evaluate_expression("checks.db.count is_present", obs) is True

    def test_is_present_case_insensitive_op(self):
        assert evaluate_expression("status IS_PRESENT", {"status": "up"}) is True


# ---------------------------------------------------------------------------
# evaluate_expression — equality operators
# ---------------------------------------------------------------------------

class TestEqualityOperators:

    def test_string_equal_case_insensitive(self):
        obs = {"status": "HEALTHY"}
        assert evaluate_expression("status == healthy", obs) is True

    def test_string_not_equal(self):
        obs = {"status": "healthy"}
        assert evaluate_expression("status != degraded", obs) is True

    def test_string_equal_fails(self):
        obs = {"status": "healthy"}
        assert evaluate_expression("status == degraded", obs) is False

    def test_integer_equal(self):
        obs = {"count": 5}
        assert evaluate_expression("count == 5", obs) is True

    def test_integer_not_equal(self):
        obs = {"count": 5}
        assert evaluate_expression("count != 3", obs) is True

    def test_bool_equal(self):
        obs = {"is_primary": True}
        assert evaluate_expression("is_primary == true", obs) is True


# ---------------------------------------------------------------------------
# evaluate_expression — ordering operators
# ---------------------------------------------------------------------------

class TestOrderingOperators:

    def test_greater_than(self):
        assert evaluate_expression("error_count > 5", {"error_count": 10}) is True
        assert evaluate_expression("error_count > 5", {"error_count": 5}) is False

    def test_greater_than_or_equal(self):
        assert evaluate_expression("error_count >= 5", {"error_count": 5}) is True
        assert evaluate_expression("error_count >= 5", {"error_count": 4}) is False

    def test_less_than(self):
        assert evaluate_expression("latency_ms < 200", {"latency_ms": 150}) is True
        assert evaluate_expression("latency_ms < 200", {"latency_ms": 300}) is False

    def test_less_than_or_equal(self):
        assert evaluate_expression("latency_ms <= 200", {"latency_ms": 200}) is True
        assert evaluate_expression("latency_ms <= 200", {"latency_ms": 201}) is False

    def test_numeric_string_field_coerced(self):
        """Field value stored as string should be coerced when literal is numeric."""
        obs = {"error_count": "12"}
        assert evaluate_expression("error_count > 10", obs) is True

    def test_float_comparison(self):
        obs = {"error_rate": 0.75}
        assert evaluate_expression("error_rate >= 0.5", obs) is True
        assert evaluate_expression("error_rate >= 0.9", obs) is False


# ---------------------------------------------------------------------------
# evaluate_expression — string operators
# ---------------------------------------------------------------------------

class TestStringOperators:

    def test_contains_substring(self):
        obs = {"region": "us-east-1"}
        assert evaluate_expression("region contains us-east", obs) is True
        assert evaluate_expression("region contains us-west", obs) is False

    def test_contains_case_insensitive(self):
        obs = {"message": "ERROR: disk full"}
        assert evaluate_expression("message contains error", obs) is True

    def test_contains_in_list(self):
        obs = {"affected": ["us-east-1", "eu-west-1"]}
        assert evaluate_expression("affected contains us-east-1", obs) is True
        assert evaluate_expression("affected contains ap-south-1", obs) is False

    def test_startswith(self):
        obs = {"incident": "INC0012345"}
        assert evaluate_expression("incident startswith INC", obs) is True
        assert evaluate_expression("incident startswith CHG", obs) is False

    def test_startswith_case_insensitive(self):
        obs = {"incident": "INC0012345"}
        assert evaluate_expression("incident startswith inc", obs) is True

    def test_endswith(self):
        obs = {"host": "node-db-primary"}
        assert evaluate_expression("host endswith primary", obs) is True
        assert evaluate_expression("host endswith replica", obs) is False


# ---------------------------------------------------------------------------
# evaluate_expression — nested paths
# ---------------------------------------------------------------------------

class TestNestedFieldPaths:

    def test_deeply_nested(self):
        obs = {"checks": {"api_check": {"response_code": 503}}}
        assert evaluate_expression("checks.api_check.response_code == 503", obs) is True

    def test_nested_missing_field_is_false(self):
        obs = {"checks": {}}
        assert evaluate_expression("checks.api_check.count > 0", obs) is False

    def test_nested_string_check(self):
        obs = {"checks": {"db_check": {"outcome": "DB_STALE"}}}
        assert evaluate_expression("checks.db_check.outcome == DB_STALE", obs) is True


# ---------------------------------------------------------------------------
# evaluate_expression — edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_empty_expression_returns_true(self):
        """Empty expression is a no-op — always satisfied."""
        assert evaluate_expression("", {"anything": "here"}) is True
        assert evaluate_expression("   ", {}) is True

    def test_unknown_field_is_false(self):
        assert evaluate_expression("nonexistent > 5", {}) is False

    def test_unparseable_expression_is_false(self):
        """Garbage expression must not crash — returns False with warning."""
        # Patch the module logger so logger.warning() doesn't trigger the
        # project's custom log filter (which requires Dynaconf AGENT_NAME).
        from unittest.mock import patch
        with patch("agent_factory.decision.expressions.logger"):
            result = evaluate_expression("not a valid expression @@@@", {})
        assert result is False

    def test_type_mismatch_is_false(self):
        """Comparing a list field with > should not raise."""
        from unittest.mock import patch
        obs = {"items": [1, 2, 3]}
        with patch("agent_factory.decision.expressions.logger"):
            result = evaluate_expression("items > 5", obs)
        assert result is False


# ---------------------------------------------------------------------------
# evaluate_all_expressions
# ---------------------------------------------------------------------------

class TestEvaluateAllExpressions:

    def test_empty_list_is_true(self):
        assert evaluate_all_expressions([], {"anything": 1}) is True

    def test_all_pass(self):
        obs = {"count": 10, "status": "down"}
        exprs = ["count > 5", "status == down"]
        assert evaluate_all_expressions(exprs, obs) is True

    def test_one_fails(self):
        obs = {"count": 3, "status": "down"}
        exprs = ["count > 5", "status == down"]
        assert evaluate_all_expressions(exprs, obs) is False

    def test_short_circuits_on_first_failure(self):
        """Once one expression fails the rest are skipped (all-of semantics)."""
        # Even if the second expression has a parse error, the first failure
        # short-circuits and we still get False without crashing.
        obs = {"count": 1}
        exprs = ["count > 100", "@@@@@@"]
        assert evaluate_all_expressions(exprs, obs) is False

    def test_expressions_with_nested_paths(self):
        obs = {
            "checks": {
                "api": {"error_count": 7},
                "db": {"stale_hours": 3},
            }
        }
        exprs = [
            "checks.api.error_count >= 5",
            "checks.db.stale_hours < 12",
        ]
        assert evaluate_all_expressions(exprs, obs) is True


# ---------------------------------------------------------------------------
# Integration: yaml_rules engine uses expressions correctly
# ---------------------------------------------------------------------------

class TestYAMLDecisionEngineIntegration:
    """End-to-end: DecisionCondition.expressions wired into YAMLDecisionEngine."""

    def test_rule_with_expressions_matches(self):
        """A rule fires only when both obs codes AND expressions pass."""
        from unittest.mock import MagicMock, patch

        # Build minimal mock pack
        rule = MagicMock()
        rule.when.all = ["API_DEGRADED"]
        rule.when.any = []
        rule.when.expressions = ["checks.api.error_rate >= 0.5"]
        rule.then_runbook = "RUNBOOK-THROTTLE"

        runbook = MagicMock()
        runbook.id = "RUNBOOK-THROTTLE"
        runbook.name = "Throttle Traffic"
        runbook.card_id = "C1"

        sop_ir = MagicMock()
        sop_ir.decision_rules = [rule]
        sop_ir.runbooks = [runbook]

        policy = MagicMock()
        policy.approvals.required_for_cards = []

        pack = MagicMock()
        pack.pack_id = "test"
        pack.sop_ir = sop_ir
        pack.policy = policy
        pack.config.rules_engine.module_path = ""

        observations = {
            "checks": {
                "api": {"outcome": "API_DEGRADED", "error_rate": 0.75}
            },
            "symptom": "API_DEGRADED",
        }

        import asyncio
        from agent_factory.decision.engine import YAMLDecisionEngine

        engine = YAMLDecisionEngine()
        result = asyncio.get_event_loop().run_until_complete(
            engine.evaluate(observations, pack)
        )

        # The engine resolves runbook_card by stripping "RUNBOOK-" prefix from
        # then_runbook ("RUNBOOK-THROTTLE" → "THROTTLE"), not from runbook.card_id.
        assert result["runbook_card"] == "THROTTLE"
        assert result["decision_source"] == "yaml_rules"
        assert "checks.api.error_rate >= 0.5" in result["reasoning"]

    def test_rule_skipped_when_expression_fails(self):
        """Rule must NOT fire when obs codes match but expression fails."""
        from unittest.mock import MagicMock, patch
        import asyncio
        from agent_factory.decision.engine import YAMLDecisionEngine

        rule = MagicMock()
        rule.when.all = ["API_DEGRADED"]
        rule.when.any = []
        rule.when.expressions = ["checks.api.error_rate >= 0.9"]  # won't match 0.75
        rule.then_runbook = "RUNBOOK-THROTTLE"

        sop_ir = MagicMock()
        sop_ir.decision_rules = [rule]
        sop_ir.runbooks = []

        pack = MagicMock()
        pack.pack_id = "test"
        pack.sop_ir = sop_ir
        pack.policy.approvals.required_for_cards = []
        pack.config.rules_engine.module_path = ""

        observations = {
            "checks": {"api": {"outcome": "API_DEGRADED", "error_rate": 0.75}},
            "symptom": "API_DEGRADED",
        }

        engine = YAMLDecisionEngine()
        # The no-match path calls logger.warning — patch to avoid the
        # Dynaconf AGENT_NAME dependency in the test environment.
        with patch("agent_factory.decision.engine.logger"):
            result = asyncio.get_event_loop().run_until_complete(
                engine.evaluate(observations, pack)
            )

        # No rule matched — falls through to no-match default
        assert result["runbook_card"] == ""
        assert result["confidence"] == "low"
