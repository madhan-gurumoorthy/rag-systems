"""Unit tests for ``RuntimeConfig.response_budget_seconds``.

The field is the per-pack override for the work-item deadline contract.
Resolution order is:

  pack.runtime.response_budget_seconds  →
  secrets.toml [default.work_item_runtime].RESPONSE_BUDGET_SECONDS  →
  180.0 (hard fallback)

These tests pin only the Pydantic-level concerns of the override:
defaults to ``None`` (i.e. "use the framework default"), accepts any
positive float, rejects 0 / negatives.  Resolution logic itself is
tested where the resolver lives (work_item_runner / tests/unit/
test_work_item_runner_budget.py — added in step 10).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_factory.pack_models.pack import RuntimeConfig


class TestResponseBudgetSecondsDefault:

    def test_defaults_to_none(self):
        """An empty `runtime:` block must leave the budget unset so the
        framework default applies — never silently force a value."""
        cfg = RuntimeConfig()
        assert cfg.response_budget_seconds is None

    def test_other_fields_still_default_when_only_budget_set(self):
        cfg = RuntimeConfig(response_budget_seconds=90)
        assert cfg.graph_builder == ""
        assert cfg.state_schema == ""
        assert cfg.state_factory == ""
        assert cfg.response_budget_seconds == 90.0


class TestResponseBudgetSecondsValidation:

    def test_accepts_positive_int(self):
        cfg = RuntimeConfig(response_budget_seconds=90)
        assert cfg.response_budget_seconds == 90.0
        assert isinstance(cfg.response_budget_seconds, float)

    def test_accepts_positive_float(self):
        cfg = RuntimeConfig(response_budget_seconds=12.5)
        assert cfg.response_budget_seconds == 12.5

    def test_rejects_zero(self):
        with pytest.raises(ValidationError) as exc:
            RuntimeConfig(response_budget_seconds=0)
        assert "response_budget_seconds must be > 0" in str(exc.value)

    def test_rejects_negative(self):
        with pytest.raises(ValidationError) as exc:
            RuntimeConfig(response_budget_seconds=-5)
        assert "response_budget_seconds must be > 0" in str(exc.value)

    def test_explicit_none_keeps_unset(self):
        cfg = RuntimeConfig(response_budget_seconds=None)
        assert cfg.response_budget_seconds is None


class TestExistingFieldsUntouched:
    """Defensive — adding a field must not perturb the entry-point
    validation that existing packs depend on."""

    def test_graph_builder_still_validated(self):
        with pytest.raises(ValidationError):
            RuntimeConfig(graph_builder="not_a_module_attr_pair")

    def test_graph_builder_empty_still_allowed(self):
        cfg = RuntimeConfig(graph_builder="")
        assert cfg.graph_builder == ""

    def test_state_schema_valid_pair_accepted(self):
        cfg = RuntimeConfig(state_schema="my.pkg:MyState")
        assert cfg.state_schema == "my.pkg:MyState"
