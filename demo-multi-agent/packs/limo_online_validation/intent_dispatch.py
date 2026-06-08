"""Intent and sub-SOP classifiers for the LIMO Online Eligibility pack.

Two callable tools:

``classify_intent``
    Looks at the resolved-state slot ``intent`` (populated by the HITL
    gate's ``resume_value``).  If empty it emits ``INTENT_REQUIRED`` so
    the approval gate fires; once the user picks one of MP / FC / WFS
    it emits ``INTENT_RESOLVED`` and the pipeline proceeds.

``classify_sub_intent``
    Pure keyword scan of the user's work-item text.  Returns the first
    matching sub-SOP code or ``main`` when nothing matches.  The user
    never has to type MP/FC/WFS — that lives behind the Slack menu.
"""
from __future__ import annotations

from typing import Any, Optional

_VALID_INTENTS = ("MP", "FC", "WFS")

# Sub-SOP precedence: more specific keywords win.  Order matters.
_SUB_SOP_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("cost_rt",      ("cost rt", "shipnode itemid", "shipnode item id",
                      "fms costrt", "fms cost rt")),
    ("pre_order",    ("pre-order", "preorder", "pre order")),
    ("replenishable",("replenishable", "replen")),
    ("shipsize",     ("shipsize", "ship size", "ship-size")),
    ("ship_class",   ("ship class", "shipclass", "ship-class")),
    ("sortable",     ("sortable",)),
    ("gifting",      ("gifting", "gift wrap", "gift message",
                      "gift receipt", "overbox")),
    ("substitution", ("substitution", "substitute", "substitutable")),
    ("acs",          ("acs flag", "acs ", "ase flag",
                      "automated shipping enabled")),
    ("ftc",          ("ftc check", "ftc validation",
                      "fulfillment type classification",
                      "fulfilment type classification")),
    ("enforcement",  ("enforcement",)),
    ("restriction",  ("restriction", "compliance")),
)


def classify_intent(intent: Optional[str] = None,
                    **_: Any) -> dict[str, Any]:
    """Decide whether the HITL gate must fire.

    ``intent`` arrives from the resolved-state slot — populated either
    by an upstream caller (legacy) or by the Slack approval round-trip
    via ``resume_value['intent']``.
    """
    upper = (intent or "").strip().upper()
    if upper in _VALID_INTENTS:
        return {
            "outcome": "INTENT_RESOLVED",
            "verdict": "INTENT_RESOLVED",
            "intent":  upper,
        }
    return {
        "outcome": "INTENT_REQUIRED",
        "verdict": "INTENT_REQUIRED",
        "intent":  None,
    }


def classify_sub_intent(work_item_text: str = "",
                        **_: Any) -> dict[str, Any]:
    """First-match keyword scan.  Returns ``main`` if nothing hits."""
    text = (work_item_text or "").lower()
    for code, keywords in _SUB_SOP_KEYWORDS:
        for kw in keywords:
            if kw in text:
                return {
                    "outcome":    f"SUB_INTENT_{code.upper()}",
                    "sub_intent": code,
                }
    return {
        "outcome":    "SUB_INTENT_MAIN",
        "sub_intent": "main",
    }


__all__ = ["classify_intent", "classify_sub_intent"]
