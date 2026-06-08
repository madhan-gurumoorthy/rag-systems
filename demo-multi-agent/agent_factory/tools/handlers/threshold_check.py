"""Threshold-check handler.

Compares numeric input values against YAML-configured limits with
optional unit conversion.  Generic "do measurements exceed limits?"
check — all policy lives on the ToolSpec; no pack Python required.

YAML config (on the ``ToolSpec``):

.. code-block:: yaml

    thresholds:         ["height=10.5", "width=13.0", "depth=20.5"]
    weight_threshold:   34.55
    weight_param:       "weight"
    dim_uom_param:      "dim_uom"
    weight_uom_param:   "weight_uom"
    dim_conversions:    {CM: 0.3937, MM: 0.03937}
    weight_conversions: {KG: 2.205, G: 0.002205, OZ: 0.0625}
    exceeds_outcome:    "EXCEEDS_LIMIT"
    within_outcome:     "WITHIN_LIMIT"

The agent passes measured values as ``params`` (height, width, depth,
weight, dim_uom, weight_uom).  The handler converts units if needed,
compares each value against its limit, and returns a structured result
the decision layer can match outcomes against.
"""
from __future__ import annotations

from typing import Any, TYPE_CHECKING

from ._base import ToolHandler

if TYPE_CHECKING:  # pragma: no cover
    from ..executor import ToolExecutor
    from ..pack_models import ToolSpec


class ThresholdCheckHandler(ToolHandler):
    type_name = "threshold_check"

    async def execute(
        self,
        *,
        tool_id: str,
        spec: "ToolSpec",
        params: dict[str, Any],
        executor: "ToolExecutor",
    ) -> dict[str, Any]:
        if spec.type != "threshold_check":
            return {"error": f"Tool '{tool_id}' is not a threshold_check tool"}

        dim_uom = str(params.get(spec.dim_uom_param, "")).upper().strip() or "IN"
        weight_uom = str(params.get(spec.weight_uom_param, "")).upper().strip() or "LB"

        dim_factor = spec.dim_conversions.get(dim_uom, 1.0) if dim_uom != "IN" else 1.0
        wt_factor = spec.weight_conversions.get(weight_uom, 1.0) if weight_uom != "LB" else 1.0
        conversion_applied = dim_uom != "IN" or weight_uom != "LB"

        exceeds = False
        reasons: list[str] = []
        checked: dict[str, dict] = {}

        for entry in spec.thresholds:
            if "=" not in entry:
                continue
            param_name, limit_str = entry.split("=", 1)
            param_name = param_name.strip()
            limit = float(limit_str.strip())
            raw_val = params.get(param_name)
            if raw_val is None:
                continue
            converted = round(float(raw_val) * dim_factor, 2)
            checked[param_name] = {"value": converted, "limit": limit, "uom": "IN"}
            if converted > limit:
                exceeds = True
                reasons.append(
                    f"{param_name} {converted} IN exceeds limit {limit} IN"
                )

        if spec.weight_threshold > 0:
            raw_wt = params.get(spec.weight_param)
            if raw_wt is not None:
                converted_wt = round(float(raw_wt) * wt_factor, 2)
                checked["weight"] = {
                    "value": converted_wt,
                    "limit": spec.weight_threshold,
                    "uom": "LB",
                }
                if converted_wt >= spec.weight_threshold:
                    exceeds = True
                    reasons.append(
                        f"weight {converted_wt} LB exceeds limit "
                        f"{spec.weight_threshold} LB"
                    )

        outcome = spec.exceeds_outcome if exceeds else spec.within_outcome

        return {
            "outcome": outcome,
            "exceeds": exceeds,
            "reason": reasons[0] if reasons else "All values within limits",
            "details": reasons if reasons else ["All values within configured limits"],
            "checked": checked,
            "unit_conversion_applied": conversion_applied,
        }


__all__ = ["ThresholdCheckHandler"]
