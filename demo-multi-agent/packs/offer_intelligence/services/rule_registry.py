"""
Rule Registry — parses IMP policy (imp_response.json) and serves rule definitions.

Loads from the pack-local data/imp_response.json on startup; supports an
optional file-system cache with 72-hour TTL.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

CACHE_TTL_HOURS = 72
_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
IMP_POLICY_FILE = os.path.abspath(os.path.join(_DATA_DIR, "imp_response.json"))
CACHE_FILE = os.path.abspath(os.path.join(_DATA_DIR, "rule_registry_cache.json"))


def _parse_conditions(raw_conditions: list[str]) -> list[dict]:
    """Parse a list of JSON-string conditions into dicts, deduplicating by name+entry+operator+fact."""
    parsed = []
    seen: set[tuple] = set()
    for raw in raw_conditions:
        try:
            cond = json.loads(raw) if isinstance(raw, str) else raw
            key = (
                cond.get("name", ""),
                cond.get("entry", ""),
                cond.get("operator", ""),
                cond.get("fact", ""),
            )
            if key in seen:
                continue
            seen.add(key)
            parsed.append(cond)
        except json.JSONDecodeError:
            logger.warning(f"rule_registry.bad_condition raw={str(raw)[:80]}")
    return parsed


def _extract_entry_fields(conditions: list[dict]) -> list[str]:
    """Extract unique entry field names from parsed conditions."""
    seen: set[str] = set()
    fields = []
    for cond in conditions:
        entry = cond.get("entry", "")
        if entry and entry not in seen:
            seen.add(entry)
            fields.append(entry)
    return fields


def _parse_action(action_str: str) -> dict:
    """Parse the action JSON string to extract listingStatus and reasonCode."""
    try:
        action = json.loads(action_str) if isinstance(action_str, str) else action_str
        results = action.get("results", [{}])
        if results:
            return {
                "listing_status": results[0].get("listingStatus", "DELISTED"),
                "reason_code": results[0].get("reasonCode", ""),
            }
    except Exception:
        pass
    return {"listing_status": "DELISTED", "reason_code": ""}


def _build_registry_from_policy(policy_data: dict) -> dict[str, dict]:
    """
    Parse the full IMP policy response and build a rule_id → rule_def map.

    Handles the nested policyResults[].ruleMatches[] structure plus the
    non-matched rules under rulesNoMatch, so the registry sees every rule
    the policy can fire.
    """
    registry: dict[str, dict] = {}

    payload = policy_data.get("payload", {})
    policy_results = payload.get("policyResults", [])

    for policy_result in policy_results:
        rule_matches = policy_result.get("ruleMatches", []) + policy_result.get("rulesNoMatch", [])
        for rule_match in rule_matches:
            meta = rule_match.get("meta", {})
            rule_id = str(meta.get("RuleId", ""))
            if not rule_id:
                continue

            conditions = _parse_conditions(rule_match.get("conditions", []))
            action = _parse_action(rule_match.get("action", "{}"))

            rule_def = {
                "rule_id": rule_id,
                "rule_name": meta.get("RuleName", rule_match.get("ruleName", "")),
                "rule_group": meta.get("RuleGroup", ""),
                "rule_version": meta.get("RuleVersion", ""),
                "expression": rule_match.get("expression", ""),
                "conditions": conditions,
                "entry_fields_required": _extract_entry_fields(conditions),
                "action": action,
                "reason_code": action.get("reason_code", ""),
            }

            # Later occurrence of same rule_id wins (more recent evaluation)
            registry[rule_id] = rule_def

    logger.info(f"rule_registry.parsed rule_count={len(registry)}")
    return registry


class RuleRegistry:
    """In-memory rule definition store backed by IMP policy JSON."""

    def __init__(self):
        self._rules: dict[str, dict] = {}
        self._last_loaded: datetime | None = None
        self._source_file: str = IMP_POLICY_FILE

    def load(self) -> None:
        """Load rules from imp_response.json (or cache file if fresher)."""
        source = self._pick_source()
        if not source:
            logger.warning("rule_registry.no_source: No IMP policy file found")
            return

        try:
            with open(source, "r") as f:
                data = json.load(f)
            self._rules = _build_registry_from_policy(data)
            self._last_loaded = datetime.now(timezone.utc)
            logger.info(f"rule_registry.loaded source={source} count={len(self._rules)}")
        except Exception as exc:
            logger.error(f"rule_registry.load_failed error={exc}")

    def _pick_source(self) -> str | None:
        """Choose the most appropriate file to load from."""
        if os.path.exists(IMP_POLICY_FILE):
            return IMP_POLICY_FILE
        if os.path.exists(CACHE_FILE):
            return CACHE_FILE
        return None

    def _is_stale(self) -> bool:
        if not self._last_loaded:
            return True
        age_hours = (datetime.now(timezone.utc) - self._last_loaded).total_seconds() / 3600
        return age_hours >= CACHE_TTL_HOURS

    def get_rule(self, rule_id: str) -> dict | None:
        """Return rule definition for given rule_id, refreshing if stale."""
        if self._is_stale():
            self.load()
        return self._rules.get(str(rule_id))

    def list_rules(self) -> list[str]:
        """Return all known rule IDs."""
        if self._is_stale():
            self.load()
        return list(self._rules.keys())

    @property
    def rule_count(self) -> int:
        return len(self._rules)


_registry: RuleRegistry | None = None


def get_registry() -> RuleRegistry:
    global _registry
    if _registry is None:
        _registry = RuleRegistry()
        _registry.load()
    return _registry
