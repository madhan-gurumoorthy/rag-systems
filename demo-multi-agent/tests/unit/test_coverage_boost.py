"""Branch-coverage tests for narrow code paths.

Covers the following modules and specific branches:
  - response_processors: _get_nested edge cases, _extract_field_with_fallbacks
    fallback chain, _apply_extract_fields non-dict, outcome_rules paths in every
    processor, process_field_presence with non-dict data, apply_processor
    exception handler.
  - decision/expressions: numeric coercion failure pass-through, contains/
    startswith/endswith on non-string/non-list, unknown operator warning.
  - evidence: content that is neither str nor list, runbook_card in content
    string but JSON dict lacks the key.
  - ir/models: SOPIR convenience-lookup methods.
  - decision/engine: PythonDecisionEngine missing module_path, evaluate_decision
    factory dispatch.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure repo root is on sys.path for bare ``utils.*`` imports.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# ---------------------------------------------------------------------------
# ── response_processors ────────────────────────────────────────────────────
# ---------------------------------------------------------------------------
from agent_factory.tools.response_processors import (
    _apply_extract_fields,
    _extract_field_with_fallbacks,
    _get_nested,
    apply_processor,
    process_any_match,
    process_count_filter,
    process_field_presence,
    process_first_field,
    process_passthrough,
    process_priority_match,
)
from agent_factory.pack_models import OutcomeRule, ResponseConfig


# ── _get_nested ─────────────────────────────────────────────────────────────

class TestGetNestedEdgeCases:
    """Target the two uncovered branches inside the array-index path."""

    def test_array_index_on_non_dict_container_returns_none(self):
        """Line 54: idx_match succeeds but current is not a dict → None."""
        # current is a list at top level — can't do list.get("items")
        data = ["a", "b", "c"]
        assert _get_nested(data, "items[0]") is None

    def test_array_index_key_resolves_to_non_list_returns_none(self):
        """Line 58: current['key'] exists but is not a list → None."""
        data = {"items": "not_a_list"}
        assert _get_nested(data, "items[0]") is None

    def test_none_current_returns_none(self):
        """Line 47: current becomes None mid-path."""
        data = {"a": None}
        assert _get_nested(data, "a.b") is None

    def test_non_dict_current_plain_key_returns_none(self):
        """Line 62: current is not a dict for a plain key."""
        data = {"a": [1, 2, 3]}
        assert _get_nested(data, "a.b") is None


# ── _extract_field_with_fallbacks ───────────────────────────────────────────

class TestExtractFieldWithFallbacks:
    """Lines 71-76: verify pipe-fallback chain."""

    def test_first_field_found(self):
        assert _extract_field_with_fallbacks({"footage": 42}, "footage|totalFootage") == 42

    def test_falls_back_to_second_field(self):
        assert _extract_field_with_fallbacks({"totalFootage": 99}, "footage|totalFootage") == 99

    def test_all_fallbacks_miss_returns_none(self):
        assert _extract_field_with_fallbacks({"other": 1}, "footage|totalFootage") is None

    def test_three_level_fallback(self):
        data = {"c": "found"}
        assert _extract_field_with_fallbacks(data, "a|b|c") == "found"


# ── _apply_extract_fields ────────────────────────────────────────────────────

class TestApplyExtractFields:
    """Lines 81-86: non-dict data returns empty dict."""

    def test_non_dict_data_returns_empty(self):
        assert _apply_extract_fields("not a dict", {"key": "field"}) == {}  # type: ignore[arg-type]

    def test_list_data_returns_empty(self):
        assert _apply_extract_fields([1, 2, 3], {"key": "field"}) == {}  # type: ignore[arg-type]

    def test_none_data_returns_empty(self):
        assert _apply_extract_fields(None, {"key": "field"}) == {}  # type: ignore[arg-type]

    def test_dict_data_extracts_correctly(self):
        result = _apply_extract_fields({"foo": "bar", "baz": 1}, {"out": "foo"})
        assert result == {"out": "bar"}


# ── outcome_rules evaluation paths ─────────────────────────────────────────

def _make_response_config(**kwargs) -> ResponseConfig:
    """Create a ResponseConfig with given kwargs, defaults for rest."""
    return ResponseConfig(**kwargs)


def _make_outcome_rules(rules: list[dict]) -> list[OutcomeRule]:
    return [OutcomeRule(**r) for r in rules]


class TestOutcomeRulesInProcessors:
    """Verify that outcome_rules are evaluated and injected into results."""

    def _cfg_with_rules(self, rules: list[dict], **extra) -> ResponseConfig:
        return _make_response_config(
            outcome_rules=_make_outcome_rules(rules),
            **extra,
        )

    # passthrough
    def test_passthrough_outcome_rule_fires(self):
        cfg = self._cfg_with_rules([{"when": "", "outcome": "ALWAYS"}])
        result = process_passthrough({"x": 1}, cfg, {})
        assert result["outcome"] == "ALWAYS"

    def test_passthrough_outcome_rule_no_match(self):
        cfg = self._cfg_with_rules([{"when": "missing_field", "outcome": "NEVER"}])
        result = process_passthrough({"x": 1}, cfg, {})
        assert "outcome" not in result

    # count_filter
    def test_count_filter_outcome_rule_fires_on_count(self):
        rules = [{"when": "count > 0", "outcome": "HAS_RECORDS"}]
        cfg = self._cfg_with_rules(rules)
        result = process_count_filter([{"val": "a"}], cfg, {})
        assert result["outcome"] == "HAS_RECORDS"

    def test_count_filter_extract_fields_from_first_matching(self):
        """Lines 291-295: extract_fields from first matching record."""
        cfg = _make_response_config(
            filter_field="status",
            filter_values=["active"],
            extract_fields={"the_name": "name"},
        )
        data = [
            {"status": "inactive", "name": "skip"},
            {"status": "active", "name": "match_me"},
        ]
        result = process_count_filter(data, cfg, {})
        assert result["the_name"] == "match_me"

    # priority_match
    def test_priority_match_outcome_rule_fires(self):
        rules = [{"when": "matched_status", "outcome": "MATCHED"}]
        cfg = _make_response_config(
            priority_field="status",
            priority_order=["critical", "warning", "ok"],
            outcome_rules=_make_outcome_rules(rules),
        )
        data = [{"status": "warning"}, {"status": "ok"}]
        result = process_priority_match(data, cfg, {})
        assert result["outcome"] == "MATCHED"

    def test_priority_match_extract_fields_from_best_record(self):
        """Lines 345-350: extract_fields from record with best priority."""
        cfg = _make_response_config(
            priority_field="level",
            priority_order=["p1", "p2", "p3"],
            extract_fields={"label": "description"},
        )
        data = [
            {"level": "p3", "description": "low"},
            {"level": "p1", "description": "critical"},
        ]
        result = process_priority_match(data, cfg, {})
        assert result["label"] == "critical"
        assert result["matched_status"] == "p1"

    # any_match
    def test_any_match_outcome_rule_fires(self):
        rules = [{"when": "any_matched", "outcome": "FOUND"}]
        cfg = _make_response_config(
            outcome_rules=_make_outcome_rules(rules),
        )
        result = process_any_match([{"x": 1}], cfg, {})
        assert result["outcome"] == "FOUND"

    # first_field
    def test_first_field_outcome_rule_fires(self):
        rules = [{"when": "value", "outcome": "HAS_VALUE"}]
        cfg = _make_response_config(
            extract_field="status",
            outcome_rules=_make_outcome_rules(rules),
        )
        result = process_first_field([{"status": "ok"}], cfg, {})
        assert result["outcome"] == "HAS_VALUE"

    # field_presence
    def test_field_presence_outcome_rule_fires(self):
        rules = [{"when": "has_fields", "outcome": "PRESENT"}]
        cfg = _make_response_config(
            presence_fields=["active"],
            outcome_rules=_make_outcome_rules(rules),
        )
        result = process_field_presence({"active": True}, cfg, {})
        assert result["outcome"] == "PRESENT"

    def test_field_presence_non_dict_sets_has_fields_false(self):
        """Lines 241-242: non-dict data → has_fields = False."""
        cfg = _make_response_config(presence_fields=["foo"])
        result = process_field_presence([1, 2, 3], cfg, {})
        assert result["has_fields"] is False

    def test_field_presence_non_dict_with_outcome_rule(self):
        """Outcome rules still evaluated on non-dict path."""
        rules = [{"when": "", "outcome": "DEFAULT"}]
        cfg = _make_response_config(
            presence_fields=["foo"],
            outcome_rules=_make_outcome_rules(rules),
        )
        result = process_field_presence("not a dict", cfg, {})
        assert result["has_fields"] is False
        assert result["outcome"] == "DEFAULT"


# ── apply_processor exception handler ───────────────────────────────────────

class TestApplyProcessorExceptionHandler:
    """Lines 474-476: exception inside processor → error dict."""

    def test_exception_returns_error_dict(self):
        cfg = _make_response_config()

        # Inject a broken processor that always raises
        import agent_factory.tools.response_processors as rp
        original = rp.PROCESSORS.get("passthrough")
        try:
            rp.PROCESSORS["passthrough"] = lambda d, c, p: (_ for _ in ()).throw(
                RuntimeError("boom")
            )
            result = apply_processor("passthrough", {"x": 1}, cfg, {"p": "v"})
        finally:
            rp.PROCESSORS["passthrough"] = original

        assert "error" in result
        assert "boom" in result["error"]
        assert result["p"] == "v"


# ---------------------------------------------------------------------------
# ── decision/expressions ───────────────────────────────────────────────────
# ---------------------------------------------------------------------------
from agent_factory.decision.expressions import _apply_operator, evaluate_expression


class TestApplyOperatorEdgeCases:
    """Target the uncovered branches in _apply_operator."""

    def test_numeric_coercion_failure_leaves_field_val_unchanged(self):
        """Lines 257-258: str field value can't be cast to numeric → TypeError
        propagates to caller (which then returns False)."""
        result = evaluate_expression("checks.count > 5", {"checks": {"count": "not_a_number"}})
        assert result is False

    def test_contains_on_non_string_non_list_returns_false(self):
        """Line 287: field is dict → neither str nor list/tuple/set → False."""
        result = _apply_operator("contains", {"nested": "dict"}, "foo")
        assert result is False

    def test_contains_on_integer_field_returns_false(self):
        result = _apply_operator("contains", 42, "4")
        assert result is False

    def test_startswith_on_non_string_returns_false(self):
        """Line 292: field is list → not str → False."""
        result = _apply_operator("startswith", [1, 2, 3], "prefix")
        assert result is False

    def test_startswith_on_integer_returns_false(self):
        result = _apply_operator("startswith", 123, "1")
        assert result is False

    def test_endswith_on_non_string_returns_false(self):
        """Line 297: field is dict → not str → False."""
        result = _apply_operator("endswith", {"a": 1}, "suffix")
        assert result is False

    def test_endswith_on_list_returns_false(self):
        result = _apply_operator("endswith", [1, 2], "2")
        assert result is False

    def test_unknown_operator_returns_false(self):
        """Lines 300-301: unknown op hits the final logger.warning + return False."""
        result = _apply_operator("xor", "value", "other")
        assert result is False


class TestEvaluateExpressionEdgeCases:
    """Higher-level expression parsing edge cases."""

    def test_empty_expression_returns_true(self):
        assert evaluate_expression("", {}) is True

    def test_unparseable_expression_returns_false(self):
        """Exercises the final logger.warning path in evaluate_expression."""
        assert evaluate_expression("!!!invalid!!!", {}) is False

    def test_is_present_returns_true_when_field_exists(self):
        assert evaluate_expression("count is_present", {"count": 0}) is True

    def test_is_absent_returns_true_when_field_missing(self):
        assert evaluate_expression("missing_field is_absent", {}) is True

    def test_is_present_returns_false_when_field_missing(self):
        assert evaluate_expression("count is_present", {}) is False

    def test_binary_field_not_found_returns_false(self):
        assert evaluate_expression("nonexistent > 5", {}) is False

    def test_contains_on_list_field(self):
        obs = {"tags": ["alpha", "beta"]}
        assert evaluate_expression("tags contains alpha", obs) is True

    def test_type_mismatch_in_comparison_returns_false(self):
        """TypeError from comparing list > int logs warning, returns False."""
        obs = {"val": [1, 2, 3]}
        assert evaluate_expression("val > 5", obs) is False


# ---------------------------------------------------------------------------
# ── evidence ───────────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------
from agent_factory.evidence_extractor import (
    _try_parse_decision,
    extract_evidence,
)


class TestTryParseDecisionEdgeCases:
    """Cover decision parsing edge cases."""

    def test_no_runbook_card_string_returns_none(self):
        assert _try_parse_decision("just some text") is None

    def test_runbook_card_in_string_but_invalid_json_returns_none(self):
        """Content has 'runbook_card' literal but is not valid JSON."""
        assert _try_parse_decision("runbook_card is mentioned here but no json") is None

    def test_runbook_card_in_string_but_parsed_dict_lacks_key_returns_none(self):
        """Lines 178-179: JSON parses fine to a dict, but 'runbook_card' not in dict.

        This is tricky: the string-level check sees 'runbook_card' but the
        actual parsed dict may not contain it (e.g. it was inside a nested string).
        """
        import json
        # Build JSON where 'runbook_card' appears in a string value but not as a key
        payload = json.dumps({"message": "see runbook_card for details", "other": 1})
        result = _try_parse_decision(payload)
        assert result is None

    def test_runbook_card_in_valid_json_returns_decision(self):
        import json
        payload = json.dumps({
            "runbook_card": "A1",
            "card_name": "Fix DB",
            "confidence": "high",
            "reasoning": "matched",
            "requires_approval": False,
            "decision_source": "yaml_rules",
        })
        result = _try_parse_decision(payload)
        assert result is not None
        assert result["runbook_card"] == "A1"

    def test_extract_evidence_with_none_steps_returns_empty(self):
        assert extract_evidence(None, pack_id="pack1") == []

    def test_extract_evidence_with_empty_steps_returns_empty(self):
        assert extract_evidence([], pack_id="pack1") == []


# ---------------------------------------------------------------------------
# ── ir/models — SOPIR convenience methods ──────────────────────────────────
# ---------------------------------------------------------------------------
from agent_factory.ir.models import RunbookSpec, SOPIR, SOPMetadata


def _make_sopir(runbooks=None, tags=None) -> SOPIR:
    """Helper to build a minimal SOPIR for testing."""
    return SOPIR(
        metadata=SOPMetadata(
            title="Test SOP",
            owner_team="test-team",
            tags=tags or [],
        ),
        runbooks=runbooks or [],
    )


class TestSOPIRConvenienceMethods:

    def test_get_card_names_uses_card_id_when_set(self):
        rb = RunbookSpec(id="RUNBOOK-A1", name="Fix Alpha", card_id="A1")
        sop = _make_sopir(runbooks=[rb])
        assert sop.get_card_names() == {"A1": "Fix Alpha"}

    def test_get_card_names_strips_runbook_prefix_when_no_card_id(self):
        rb = RunbookSpec(id="RUNBOOK-B2", name="Fix Beta")
        sop = _make_sopir(runbooks=[rb])
        assert sop.get_card_names() == {"B2": "Fix Beta"}

    def test_get_card_names_uses_id_as_name_when_name_empty(self):
        rb = RunbookSpec(id="RUNBOOK-C3", card_id="C3")
        sop = _make_sopir(runbooks=[rb])
        result = sop.get_card_names()
        assert result["C3"] == "C3"

    def test_get_card_names_empty_runbooks(self):
        sop = _make_sopir()
        assert sop.get_card_names() == {}

    def test_get_card_tags_with_tags(self):
        rb = RunbookSpec(
            id="RUNBOOK-D4",
            card_id="D4",
            tags={"issue_tag": "CPU_HIGH", "fix_tag": "SCALE_UP"},
        )
        sop = _make_sopir(runbooks=[rb])
        tags = sop.get_card_tags()
        assert tags["D4"] == ("CPU_HIGH", "SCALE_UP")

    def test_get_card_tags_missing_tags_fall_back_to_empty_strings(self):
        rb = RunbookSpec(id="RUNBOOK-E5", card_id="E5")
        sop = _make_sopir(runbooks=[rb])
        tags = sop.get_card_tags()
        assert tags["E5"] == ("", "")

    def test_get_card_tags_empty_runbooks(self):
        sop = _make_sopir()
        assert sop.get_card_tags() == {}

    def test_get_runbook_by_card_id_found_via_card_id(self):
        rb = RunbookSpec(id="RUNBOOK-F6", name="Fix F6", card_id="F6")
        sop = _make_sopir(runbooks=[rb])
        found = sop.get_runbook_by_card_id("F6")
        assert found is rb

    def test_get_runbook_by_card_id_found_via_id_prefix_strip(self):
        rb = RunbookSpec(id="RUNBOOK-G7", name="Fix G7")
        sop = _make_sopir(runbooks=[rb])
        found = sop.get_runbook_by_card_id("G7")
        assert found is rb

    def test_get_runbook_by_card_id_not_found_returns_none(self):
        rb = RunbookSpec(id="RUNBOOK-H8", card_id="H8")
        sop = _make_sopir(runbooks=[rb])
        assert sop.get_runbook_by_card_id("ZZ") is None

    def test_get_runbook_by_card_id_empty_runbooks(self):
        sop = _make_sopir()
        assert sop.get_runbook_by_card_id("A1") is None

    def test_get_domain_returns_first_tag(self):
        sop = _make_sopir(tags=["payments", "fraud"])
        assert sop.get_domain() == "payments"

    def test_get_domain_returns_empty_when_no_tags(self):
        sop = _make_sopir(tags=[])
        assert sop.get_domain() == ""


# ---------------------------------------------------------------------------
# ── decision/engine ────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------
from agent_factory.decision.engine import (
    PythonDecisionEngine,
    YAMLDecisionEngine,
    _load_rules_module,
    evaluate_decision,
)


def _make_pack(
    decision_engine: str = "yaml_rules",
    module_path: str = "",
    apply_function: str = "apply_decision_matrix",
    decision_rules=None,
    approval_cards=None,
) -> MagicMock:
    """Build a minimal AgentPack-like mock for decision engine tests."""
    pack = MagicMock()
    pack.pack_id = "test-pack"
    pack.config.decision_engine = decision_engine
    pack.config.rules_engine.module_path = module_path
    pack.config.rules_engine.apply_function = apply_function
    pack.policy.approvals.required_for_cards = approval_cards or []
    pack.sop_ir.decision_rules = decision_rules or []
    return pack


class TestPythonDecisionEngineMissingModulePath:
    """Lines 123-129: raises RuntimeError when module_path is not set."""

    @pytest.mark.asyncio
    async def test_raises_runtime_error_when_module_path_empty(self):
        pack = _make_pack(decision_engine="python", module_path="")
        engine = PythonDecisionEngine()
        with pytest.raises(RuntimeError, match="rules_engine.module_path is not set"):
            await engine.evaluate({}, pack)


class TestEvaluateDecisionFactory:
    """Lines 279-284: evaluate_decision selects correct engine class."""

    @pytest.mark.asyncio
    async def test_yaml_rules_engine_dispatched(self):
        """evaluate_decision with yaml_rules engine uses YAMLDecisionEngine."""
        rule = MagicMock()
        rule.when.all = ["CODE_A"]
        rule.when.any = []
        rule.when.expressions = []
        rule.then_runbook = "RUNBOOK-A1"

        rb = MagicMock()
        rb.id = "RUNBOOK-A1"
        rb.name = "Card A1"

        pack = _make_pack(
            decision_engine="yaml_rules",
            decision_rules=[rule],
        )
        pack.sop_ir.runbooks = [rb]

        observations = {"checks": {"diag": {"outcome": "CODE_A"}}}
        result = await evaluate_decision(observations, pack)
        assert result["runbook_card"] == "A1"
        assert result["decision_source"] == "yaml_rules"

    @pytest.mark.asyncio
    async def test_unknown_engine_falls_back_to_yaml(self):
        """Unknown engine type defaults to YAMLDecisionEngine (no match → low confidence)."""
        pack = _make_pack(decision_engine="nonexistent_engine", decision_rules=[])
        pack.config.rules_engine.module_path = ""
        observations = {}
        result = await evaluate_decision(observations, pack)
        # No rules → no match → low confidence default
        assert result["confidence"] == "low"
        assert result["decision_source"] == "yaml_rules_no_match"

    @pytest.mark.asyncio
    async def test_python_engine_missing_module_raises(self):
        """evaluate_decision with python engine and no module_path raises."""
        pack = _make_pack(decision_engine="python", module_path="")
        with pytest.raises(RuntimeError, match="rules_engine.module_path is not set"):
            await evaluate_decision({}, pack)


class TestLoadRulesModuleEdgeCases:
    """Cover _load_rules_module cache and ImportError paths."""

    def test_cached_module_returned_directly(self):
        import agent_factory.decision.engine as eng
        sentinel = object()
        eng._rules_module_cache["cached.module.path"] = sentinel
        try:
            result = _load_rules_module("cached.module.path")
            assert result is sentinel
        finally:
            del eng._rules_module_cache["cached.module.path"]

    def test_nonexistent_module_raises_import_error(self):
        with pytest.raises(ImportError, match="Cannot find rules module"):
            _load_rules_module("nonexistent.module.that.does.not.exist.at.all")
