"""Decision-matrix handler — first-match rule engine driven by YAML.

A generic ``IF (k1=v1 AND k2=v2 AND k3 IS ABSENT) THEN runbook=R``
engine.  Iterates rules in order, returns the first match.  All rules
live on the ``ToolSpec`` (sourced from ``tools.yaml``) so no pack
Python is required.

YAML config (on the ``ToolSpec``):

.. code-block:: yaml

    decision_rules:
      - id: RULE-A
        conditions:        {SOME-CHECK-01: PASSED}
        runbook:           RBK-A-01
        description:       "Condition A matched - happy-path runbook"
      - id: RULE-B
        conditions:        {SOME-CHECK-01: FAILED}
        requires_absent:   [external_response]
        runbook:           RBK-A-02
        description:       "Condition A failed - request external input"
    decision_fallback:
      runbook:     RBK-A-FALLBACK
      description: "No rule matched - escalate"
    decision_error_codes: [API_ERROR, PARSE_FAILURE, UPSTREAM_ERROR]

The agent passes a JSON-encoded observations string as the
``observations`` param.  The handler:

  1. Parses the JSON (fallback runbook on parse failure).
  2. Short-circuits to fallback if any observation value matches an
     entry in ``decision_error_codes``.
  3. Evaluates rules in order; returns the first whose conditions
     all match and whose ``requires_absent`` keys are all empty.
  4. Falls back if no rule matched.
"""
from __future__ import annotations

import json
from typing import Any, TYPE_CHECKING

from ._base import ToolHandler

if TYPE_CHECKING:  # pragma: no cover
    from ..executor import ToolExecutor
    from ..pack_models import ToolSpec


class DecisionMatrixHandler(ToolHandler):
    type_name = "decision_matrix"

    async def execute(
        self,
        *,
        tool_id: str,
        spec: "ToolSpec",
        params: dict[str, Any],
        executor: "ToolExecutor",
    ) -> dict[str, Any]:
        if spec.type != "decision_matrix":
            return {"error": f"Tool '{tool_id}' is not a decision_matrix tool"}

        fallback = spec.decision_fallback or {
            "runbook": "ESCALATE",
            "description": "No rule matched",
        }
        raw_obs = params.get("observations", "{}")

        try:
            obs = json.loads(raw_obs) if isinstance(raw_obs, str) else raw_obs
        except (json.JSONDecodeError, TypeError):
            return {
                "matched_rule": "RULE-FALLBACK",
                "runbook": fallback.get("runbook", "ESCALATE"),
                "description": "Failed to parse observations JSON — escalating",
                "confidence": "low",
                "observations_used": {},
                "error": f"Invalid observations: {raw_obs!r}",
            }

        error_codes = {c.upper() for c in spec.decision_error_codes}
        if error_codes:
            for key, val in obs.items():
                if str(val).upper() in error_codes:
                    return {
                        "matched_rule": "RULE-FALLBACK",
                        "runbook": fallback.get("runbook", "ESCALATE"),
                        "description": f"Error in {key}: {val} — escalating",
                        "confidence": "high",
                        "observations_used": obs,
                    }

        for rule in spec.decision_rules:
            conditions = rule.get("conditions", {})
            absent_keys = rule.get("requires_absent", [])

            all_match = all(
                str(obs.get(k, "")).upper() == str(v).upper()
                for k, v in conditions.items()
            )
            absent_ok = all(
                not str(obs.get(k, "")).strip()
                for k in absent_keys
            )

            if all_match and absent_ok:
                return {
                    "matched_rule": rule.get("id", ""),
                    "runbook": rule.get("runbook", ""),
                    "description": rule.get("description", ""),
                    "confidence": "high",
                    "observations_used": obs,
                }

        return {
            "matched_rule": "RULE-FALLBACK",
            "runbook": fallback.get("runbook", "ESCALATE"),
            "description": fallback.get("description", "No rule matched"),
            "confidence": "medium",
            "observations_used": obs,
        }


__all__ = ["DecisionMatrixHandler"]
