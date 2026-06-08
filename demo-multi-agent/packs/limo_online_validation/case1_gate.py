"""Deterministic Case 1 gates for the LIMO Online Eligibility pack.

Three callables, each exposed as a ``python_function`` tool:

``validate_offer_id``
    Confirms the inbound offer id matches the ODIN 32-char uppercase
    hex contract.  Emits ``OFFER_ID_VALID`` / ``OFFER_ID_INVALID``.

``detect_intent``
    Three-stage resolver:

      1. Honour an explicit ``state.intent`` slot.
      2. Whole-word scan of the inbound text for ``WFS`` → ``FC`` →
         ``MP`` (in precedence order; "marketplace" maps to MP).
      3. Sub-SOP keyword scan (cost rt / pre-order / replenishable /
         acs / substitution / restriction / seller enforcement / …).
         Sub-SOPs do **not** require a main intent — when a sub-SOP
         keyword matches and no FC/WFS/MP is present, the resolver
         emits ``SUB_INTENT_RESOLVED`` with ``sub_intent=<code>`` and
         ``intent=None`` so the chat pipeline can skip the main
         FC/WFS/MP cascade and run the sub-SOP flow directly.

    Emits ``INTENT_RESOLVED`` (main intent), ``SUB_INTENT_RESOLVED``
    (sub-SOP only), or ``INTENT_REQUIRED`` with a ready-to-render menu
    string when nothing can be inferred.

``case1_gate``
    Intent-aware pre-flight gate.  Every intent requires
    ``oa.ofrCrt == true``.  Additionally:

      - ``FC``  requires ``oa.otyp`` ∈ {``ONLINE_ONLY``,
        ``ONLINE_AND_STORE``}.
      - ``WFS`` requires ``wfsElig == true``.
      - ``MP``  proceeds on any ``wfsElig`` value; when ``wfsElig`` is
        true the gate surfaces a ``MP_WFS_ELIGIBLE_NOTICE`` advisory
        (``notice_code`` / ``notice_message``) and continues to
        Cases 2–5.

    Returns ``CASE1_PROCEED`` (optionally carrying a ``notice_code`` /
    ``notice_message``) or ``CASE1_BLOCKED`` with a list of failing
    gates, a stable ``block_code`` for the closure template, and an
    intent-aware ``stop_message`` that tells the caller exactly what
    to do next (e.g. "re-run with WFS intent").
"""
from __future__ import annotations

import re
from typing import Any, Optional

from packs.limo_online_validation.intent_dispatch import classify_sub_intent
from packs.limo_online_validation.seller_enforcement import _norm_bool

__all__ = [
    "validate_offer_id",
    "detect_intent",
    "case1_gate",
]


_OFFER_ID_PATTERN = re.compile(r"^[A-F0-9]{32}$")

_VALID_INTENTS = ("FC", "WFS", "MP")

# Intent precedence for the text scan.  WFS is checked before FC so a
# request like "Validate WFS eligibility" is not mis-classified as FC
# (which would have matched the trailing "FC" in "FC at node ...").
_INTENT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("WFS", re.compile(r"\bWFS\b", re.IGNORECASE)),
    ("FC",  re.compile(r"\bFC\b",  re.IGNORECASE)),
    ("MP",  re.compile(r"\b(?:MP|marketplace)\b", re.IGNORECASE)),
)

_VALID_FC_OFFER_TYPES = frozenset({"ONLINE_ONLY", "ONLINE_AND_STORE"})

_INTENT_MENU_MESSAGE = (
    "Main intent is required.  Please re-run the request with one of:\n"
    "  - FC  (Walmart 1P fulfillment via the selected node)\n"
    "  - WFS (Walmart Fulfillment Services)\n"
    "  - MP  (Marketplace seller-fulfilled)"
)

_MP_WFS_ELIGIBLE_NOTICE = (
    "Note: oa.wfsElig is true for this offer.  The MP path validation "
    "will continue through AURUM / DEW / Promise / Consolidated.  If "
    "you actually want to confirm the WFS path, re-run the request "
    "with WFS intent."
)


def validate_offer_id(offer_id: Any = None, **_: Any) -> dict[str, Any]:
    """Pre-flight check on the ODIN offer id format.

    Inputs:
      - ``offer_id`` : the value extracted by TriageAgent.

    Returns:
      - ``outcome``  : ``OFFER_ID_VALID`` | ``OFFER_ID_INVALID``
      - ``offer_id`` : the normalised (upper-cased) id when valid
      - ``reason``   : one-line explanation
    """
    token = (str(offer_id) if offer_id is not None else "").strip().upper()
    if _OFFER_ID_PATTERN.match(token):
        return {
            "outcome":  "OFFER_ID_VALID",
            "offer_id": token,
            "reason":   "offer_id matches the 32-char uppercase hex contract.",
        }
    return {
        "outcome":  "OFFER_ID_INVALID",
        "offer_id": token or None,
        "reason":   (
            "offer_id must be a 32-character uppercase hexadecimal string "
            "(ODIN oid contract)."
        ),
    }


def _scan_text_for_intent(text: str) -> Optional[str]:
    """First-match whole-word scan in WFS → FC → MP precedence order."""
    for intent, pattern in _INTENT_PATTERNS:
        if pattern.search(text):
            return intent
    return None


def detect_intent(intent: Any = None,
                  work_item_text: str = "",
                  **_: Any) -> dict[str, Any]:
    """Resolve the main intent from state, then text, then sub-SOP keyword.

    Resolution order:
      1. ``state.intent`` slot → ``INTENT_RESOLVED`` with ``source="state"``.
      2. Whole-word ``WFS`` / ``FC`` / ``MP`` scan of ``work_item_text``
         → ``INTENT_RESOLVED`` with ``source="text"``.
      3. Sub-SOP keyword scan via ``classify_sub_intent``.  Any non-
         ``main`` match → ``SUB_INTENT_RESOLVED`` with
         ``sub_intent=<code>``, ``intent=None``, ``source="sub_intent"``.
         The chat pipeline routes these directly to the sub-SOP flow
         and skips the FC/WFS/MP cascade.
      4. Nothing matched → ``INTENT_REQUIRED`` with the menu message.

    Output keys:
      - ``outcome``      : ``INTENT_RESOLVED`` | ``SUB_INTENT_RESOLVED``
                           | ``INTENT_REQUIRED``
      - ``intent``       : main intent (FC/WFS/MP) when resolved, else ``None``
      - ``sub_intent``   : sub-SOP code (e.g. ``"cost_rt"``) when
                           ``SUB_INTENT_RESOLVED``, else ``None``
      - ``source``       : ``"state"`` | ``"text"`` | ``"sub_intent"`` |
                           ``None``
      - ``menu_message`` : ready-to-render selection prompt, or ``None``
    """
    upper = (str(intent) if intent is not None else "").strip().upper()
    if upper in _VALID_INTENTS:
        return {
            "outcome":      "INTENT_RESOLVED",
            "intent":       upper,
            "sub_intent":   None,
            "source":       "state",
            "menu_message": None,
        }

    text = str(work_item_text or "")
    scanned = _scan_text_for_intent(text)
    if scanned is not None:
        return {
            "outcome":      "INTENT_RESOLVED",
            "intent":       scanned,
            "sub_intent":   None,
            "source":       "text",
            "menu_message": None,
        }

    sub = classify_sub_intent(work_item_text=text)
    sub_code = sub.get("sub_intent")
    if sub_code and sub_code != "main":
        return {
            "outcome":      "SUB_INTENT_RESOLVED",
            "intent":       None,
            "sub_intent":   sub_code,
            "source":       "sub_intent",
            "menu_message": None,
        }

    return {
        "outcome":      "INTENT_REQUIRED",
        "intent":       None,
        "sub_intent":   None,
        "source":       None,
        "menu_message": _INTENT_MENU_MESSAGE,
    }


def _redirect_line(intent: str, failed_codes: list[str]) -> str:
    """Build the intent-aware redirect line for a blocked case.

    ``failed_codes`` items are stable block codes
    (``OFFER_NOT_CREATED`` / ``OTYPE_INVALID`` / ``WFS_NOT_ELIGIBLE``)
    — used to compose the human-readable advice.  The MP wfsElig case
    is intentionally absent: MP no longer blocks on ``wfsElig`` and
    instead surfaces ``MP_WFS_ELIGIBLE_NOTICE`` while proceeding.
    """
    if "OFFER_NOT_CREATED" in failed_codes:
        return (
            "Offer is not fully created (oa.ofrCrt is not true).  "
            "Please raise an incident with the LIMO ops team."
        )
    if intent == "FC" and "OTYPE_INVALID" in failed_codes:
        return (
            "Offer Type (oa.otyp) must be ONLINE_ONLY or ONLINE_AND_STORE "
            "for FC path eligibility.  Verify the offer was published as "
            "an online offer."
        )
    if intent == "WFS" and "WFS_NOT_ELIGIBLE" in failed_codes:
        return (
            "Offer is not WFS-eligible (oa.wfsElig is not true).  "
            "Re-run validation with FC or MP intent, or confirm the seller "
            "/ offer is WFS-enrolled."
        )
    return (
        "Case 1 pre-flight check failed.  Please raise an incident with "
        "the LIMO ops team."
    )


def case1_gate(intent: Any = None,
               ofr_crt: Any = None,
               wfs_elig: Any = None,
               offer_type: Any = None,
               **_: Any) -> dict[str, Any]:
    """Intent-aware Case 1 pre-flight gate.

    Inputs:
      - ``intent``     : resolved main intent (``FC`` / ``WFS`` / ``MP``).
      - ``ofr_crt``    : ODIN ``oa.ofrCrt`` value.
      - ``wfs_elig``   : ODIN ``oa.wfsElig`` value.
      - ``offer_type`` : ODIN ``oa.otyp`` value.

    Output keys:
      - ``outcome``        : ``CASE1_PROCEED`` | ``CASE1_BLOCKED``
      - ``intent``         : upper-cased intent (echoed back)
      - ``failed_gates``   : list of ``{"name": ..., "observed": ...}``
      - ``block_code``     : stable code for the closure template, or
                             ``None`` on PROCEED
      - ``stop_message``   : intent-aware redirect line, or ``None`` on
                             PROCEED
      - ``notice_code``    : stable advisory code (e.g.
                             ``MP_WFS_ELIGIBLE_NOTICE``) surfaced
                             alongside PROCEED, or ``None``
      - ``notice_message`` : human-readable advisory rendered above the
                             ODIN block, or ``None``
      - ``reason``         : human-readable summary
    """
    upper_intent = (str(intent) if intent is not None else "").strip().upper()
    if upper_intent not in _VALID_INTENTS:
        return {
            "outcome":        "CASE1_BLOCKED",
            "intent":         None,
            "failed_gates":   [{"name": "intent", "observed": intent}],
            "block_code":     "INTENT_REQUIRED",
            "stop_message":   _INTENT_MENU_MESSAGE,
            "notice_code":    None,
            "notice_message": None,
            "reason":         "Main intent (FC / WFS / MP) not supplied.",
        }

    ofr_norm = _norm_bool(ofr_crt)
    wfs_norm = _norm_bool(wfs_elig)
    otyp_token = (str(offer_type) if offer_type is not None else "").strip().upper()

    failed_gates: list[dict[str, Any]] = []
    failed_codes: list[str] = []
    notice_code: Optional[str] = None
    notice_message: Optional[str] = None

    if ofr_norm is not True:
        failed_gates.append({"name": "oa.ofrCrt", "observed": ofr_crt})
        failed_codes.append("OFFER_NOT_CREATED")

    if upper_intent == "FC":
        if otyp_token not in _VALID_FC_OFFER_TYPES:
            failed_gates.append({"name": "oa.otyp", "observed": offer_type})
            failed_codes.append("OTYPE_INVALID")
    elif upper_intent == "WFS":
        if wfs_norm is not True:
            failed_gates.append({"name": "wfsElig", "observed": wfs_elig})
            failed_codes.append("WFS_NOT_ELIGIBLE")
    else:  # MP
        # wfsElig is informational for MP — surface the value via a
        # notice and continue to Cases 2–5.  MP is never blocked at
        # Case 1 on wfsElig.
        if wfs_norm is True:
            notice_code = "MP_WFS_ELIGIBLE_NOTICE"
            notice_message = _MP_WFS_ELIGIBLE_NOTICE

    if not failed_gates:
        return {
            "outcome":        "CASE1_PROCEED",
            "intent":         upper_intent,
            "failed_gates":   [],
            "block_code":     None,
            "stop_message":   None,
            "notice_code":    notice_code,
            "notice_message": notice_message,
            "reason":         (
                f"Case 1 gates pass for {upper_intent} intent "
                "(oa.ofrCrt is true and intent-specific gate satisfied)."
                + (
                    "  Advisory: oa.wfsElig is true; MP path continues."
                    if notice_code == "MP_WFS_ELIGIBLE_NOTICE"
                    else ""
                )
            ),
        }

    # Primary block_code is the first failed gate so the closure
    # template branches on the most specific cause.
    block_code = failed_codes[0]
    return {
        "outcome":        "CASE1_BLOCKED",
        "intent":         upper_intent,
        "failed_gates":   failed_gates,
        "block_code":     block_code,
        "stop_message":   _redirect_line(upper_intent, failed_codes),
        "notice_code":    None,
        "notice_message": None,
        "reason":         (
            f"Case 1 failed for {upper_intent} intent at "
            f"{', '.join(code for code in failed_codes)}."
        ),
    }
