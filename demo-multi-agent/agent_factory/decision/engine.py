"""Generic decision engine interface.

Provides a common interface for decision evaluation across packs.
The engine type is selected from pack.yaml ``decision_engine`` field:
  - "yaml_rules"  — purely config-driven from sop-ir.json (preferred)
  - "python"      — delegates to a pluggable Python rules module

The Python engine's module path comes from pack.yaml ``rules_engine``
config, not from a hardcoded import.  This allows each pack to ship
its own rules module.

Usage::

    result = await evaluate_decision(observations, pack)
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

from agent_factory.common.logging import get_logger
from ..pack_loader import AgentPack
from .expressions import evaluate_all_expressions

logger = get_logger("decision_engine")


class DecisionEngineInterface(ABC):
    """Abstract base for all decision engines."""

    @abstractmethod
    async def evaluate(
        self, observations: dict[str, Any], pack: AgentPack
    ) -> dict[str, Any]:
        """Evaluate observations and return a decision.

        Args:
            observations: Dict of diagnostic observation outcomes.
            pack: The loaded SOP pack for context.

        Returns:
            Dict with at minimum: runbook_card, card_name, confidence,
            reasoning, requires_approval.
        """
        ...


# ── Module-level cache for dynamically loaded rules modules ──────────
_rules_module_cache: dict[str, Any] = {}


def _load_rules_module(module_path: str):
    """Load a Python rules module by dotted path.

    Uses importlib.util to avoid triggering heavy transitive imports
    when the module sits inside a package with langgraph/protobuf deps.

    The module path comes from pack.yaml ``rules_engine.module_path``.
    """
    if module_path in _rules_module_cache:
        return _rules_module_cache[module_path]

    import importlib.util
    import sys

    # If already loaded by the full app, use it
    if module_path in sys.modules:
        _rules_module_cache[module_path] = sys.modules[module_path]
        return _rules_module_cache[module_path]

    # Convert dotted path to file path
    from pathlib import Path
    project_root = Path(__file__).resolve().parent.parent.parent
    parts = module_path.split(".")
    rules_file = project_root / ("/".join(parts) + ".py")

    # Try the path as-is first, then try as a package
    if not rules_file.exists():
        # Maybe it's packs.modflex.decision_rules → packs/modflex/decision_rules.py
        rules_file = project_root / "/".join(parts)
        rules_file = rules_file.with_suffix(".py")

    if not rules_file.exists():
        raise ImportError(f"Cannot find rules module at {rules_file} for path '{module_path}'")

    spec = importlib.util.spec_from_file_location(module_path, rules_file)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot create spec for {rules_file}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_path] = module
    spec.loader.exec_module(module)

    _rules_module_cache[module_path] = module
    return module


class PythonDecisionEngine(DecisionEngineInterface):
    """Delegates to a pluggable Python-based rules module.

    The rules module path and entry-point function name are read from
    pack.yaml ``rules_engine`` config.  This wraps any pack-specific
    Python decision engine so it conforms to the generic interface.

    Approval gates are read from policy.yaml, not hardcoded.
    """

    async def evaluate(
        self, observations: dict[str, Any], pack: AgentPack
    ) -> dict[str, Any]:
        """Evaluate using the Python rule engine configured in the pack.

        Reads ``rules_engine.module_path`` and ``rules_engine.apply_function``
        from pack.yaml to locate the entry point.  After evaluation, the
        ``requires_approval`` flag is overridden from policy.yaml.
        """
        rules_cfg = pack.config.rules_engine
        module_path = rules_cfg.module_path

        if not module_path:
            raise RuntimeError(
                f"Pack '{pack.pack_id}' uses decision_engine='python' but "
                f"rules_engine.module_path is not set in pack.yaml. "
                f"Set it to the dotted import path of your rules module "
                f"(e.g. 'packs.modflex.decision_rules')."
            )

        rules_mod = _load_rules_module(module_path)
        apply_fn = getattr(rules_mod, rules_cfg.apply_function, None)

        if apply_fn is None:
            raise RuntimeError(
                f"Rules module '{module_path}' does not have function "
                f"'{rules_cfg.apply_function}'. Available: "
                f"{[a for a in dir(rules_mod) if not a.startswith('_')]}"
            )

        result_json = await apply_fn(json.dumps(observations))
        result = json.loads(result_json)

        # Override approval flag from policy.yaml
        approval_cards = _get_approval_cards(pack)
        card = result.get("runbook_card", "")
        result["requires_approval"] = card in approval_cards

        return result


class YAMLDecisionEngine(DecisionEngineInterface):
    """Evaluates decision rules from sop-ir.json decision_rules section.

    This is the preferred engine for new packs: purely config-driven
    decisions from the SOP-IR.  No Python rules module needed.

    When no YAML rule matches, returns a low-confidence default rather
    than falling back to a Python engine.
    """

    async def evaluate(
        self, observations: dict[str, Any], pack: AgentPack
    ) -> dict[str, Any]:
        """Evaluate using YAML-defined decision rules from SOP-IR.

        Iterates through decision_rules and checks if conditions match
        the observation codes present in the observations dict.
        """
        obs_codes = set()
        # Flatten observation codes from all checks
        checks = observations.get("checks", {})
        for check_name, check_data in checks.items():
            if isinstance(check_data, dict):
                outcome = check_data.get("outcome", "")
                if outcome:
                    obs_codes.add(outcome)
        # Add top-level fields
        if observations.get("symptom"):
            obs_codes.add(observations["symptom"])

        approval_cards = _get_approval_cards(pack)

        for rule in pack.sop_ir.decision_rules:
            # ── Observation-code conditions ────────────────────────────
            # 'all' — every listed code must be present in obs_codes
            all_match = all(code in obs_codes for code in rule.when.all)

            # 'any' — at least one listed code must be present (vacuously
            # True when the list is empty, matching previous behaviour)
            any_match = (
                not rule.when.any
                or any(code in obs_codes for code in rule.when.any)
            )

            # ── Value-expression conditions ────────────────────────────
            # Optional; evaluated only when code-based conditions pass to
            # short-circuit evaluation for performance.
            expr_match = (
                not rule.when.expressions
                or (
                    all_match
                    and any_match
                    and evaluate_all_expressions(rule.when.expressions, observations)
                )
            )

            if all_match and any_match and expr_match:
                runbook_id = rule.then_runbook
                runbook = next(
                    (rb for rb in pack.sop_ir.runbooks if rb.id == runbook_id),
                    None,
                )
                card_id = (
                    runbook_id.replace("RUNBOOK-", "")
                    if runbook_id.startswith("RUNBOOK-")
                    else runbook_id
                )
                reasoning = (
                    f"YAML rule matched: all={rule.when.all}, any={rule.when.any}"
                )
                if rule.when.expressions:
                    reasoning += f", expressions={rule.when.expressions}"
                return {
                    "runbook_card": card_id,
                    "card_name": runbook.name if runbook else card_id,
                    "confidence": "high",
                    "reasoning": reasoning,
                    "requires_approval": card_id in approval_cards,
                    "decision_source": "yaml_rules",
                }

        # No rule matched — check if pack has a Python fallback configured
        if pack.config.rules_engine.module_path:
            logger.warning("No YAML rule matched; falling back to pack's Python engine")
            fallback = PythonDecisionEngine()
            return await fallback.evaluate(observations, pack)

        # No fallback — return a low-confidence "no match" result
        logger.warning("No YAML rule matched and no Python fallback configured")
        return {
            "runbook_card": "",
            "card_name": "No match",
            "confidence": "low",
            "reasoning": "No decision rule matched the observation codes. Manual review required.",
            "requires_approval": True,  # Safe default: require approval
            "decision_source": "yaml_rules_no_match",
        }


def _get_approval_cards(pack: AgentPack) -> set[str]:
    """Extract the set of card IDs that require approval from policy."""
    return set(pack.policy.approvals.required_for_cards)


# ── Factory function ──────────────────────────────────────────────────

_ENGINES: dict[str, type[DecisionEngineInterface]] = {
    "python": PythonDecisionEngine,
    "yaml_rules": YAMLDecisionEngine,
}


async def evaluate_decision(
    observations: dict[str, Any],
    pack: AgentPack,
) -> dict[str, Any]:
    """Evaluate observations using the pack's configured decision engine.

    The engine type is read from pack.config.decision_engine (default "python").

    Args:
        observations: Diagnostic outcomes.
        pack: The loaded SOP pack.

    Returns:
        Decision dict with runbook_card, card_name, etc.
    """
    engine_type = pack.config.decision_engine
    engine_class = _ENGINES.get(engine_type, YAMLDecisionEngine)
    engine = engine_class()

    logger.info(f"Evaluating decision with engine={engine_type} for pack={pack.pack_id}")
    return await engine.evaluate(observations, pack)
