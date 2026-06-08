"""Deterministic helpers for the Seller-Level Enforcement sub-SOP.

Two callable tools:

``check_offer_fully_created``
    Reads the ODIN ``oa.ofrCrt`` flag.  Emits ``OFFER_FULLY_CREATED``
    when the flag normalises to true, ``OFFER_NOT_CREATED`` otherwise.
    Returns ``OFFER_CRT_UNKNOWN`` when the input is None — distinct
    from a hard "not created" signal so the prompt can branch.

``classify_seller_enforcement``
    Pure set-membership check against the upstream
    ``payload.restrictions`` array.

    Contract:
      - ``seller_type == 'INTERNAL'`` → ``ENFORCEMENT_NOT_APPLICABLE``
        (internal sellers are exempt; no display gate).
      - For external sellers the *relevant* path is chosen from the
        offer's ``wfsElig``:
          * truthy → ``WALMART_PATH`` (offer is WFS-fulfilled)
          * else   → ``SELLER_PATH``  (seller-fulfilled)
      - ``ENFORCEMENT_BLOCKED`` when the relevant path is in the
        enforced set, ``ENFORCEMENT_CLEAR`` otherwise.

    Both ``SELLER_PATH`` and ``WALMART_PATH`` may appear in
    ``payload.restrictions``; the gate only fires on the path that
    applies to this offer.
"""
from __future__ import annotations

from typing import Any, Iterable, Optional

_TRUE_TOKENS = frozenset({"true", "1", "yes", "y", "t"})
_FALSE_TOKENS = frozenset({"false", "0", "no", "n", "f"})


def _norm_bool(value: Any) -> Optional[bool]:
    """Best-effort bool coercion.  Returns None if the value is
    missing or unrecognisable so callers can distinguish "no signal"
    from "explicitly false"."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    token = str(value).strip().lower()
    if not token:
        return None
    if token in _TRUE_TOKENS:
        return True
    if token in _FALSE_TOKENS:
        return False
    return None


def check_offer_fully_created(ofr_crt: Any = None,
                              **_: Any) -> dict[str, Any]:
    """Gate on ODIN ``oa.ofrCrt``.

    Returns one of three outcomes plus a normalised bool so prompts
    can render the raw + interpreted values side by side.
    """
    norm = _norm_bool(ofr_crt)
    if norm is True:
        return {
            "outcome": "OFFER_FULLY_CREATED",
            "ofr_crt_norm": True,
            "reason": "oa.ofrCrt is true — offer is fully created.",
        }
    if norm is False:
        return {
            "outcome": "OFFER_NOT_CREATED",
            "ofr_crt_norm": False,
            "reason": "oa.ofrCrt is not true — offer is not fully created.",
        }
    return {
        "outcome": "OFFER_CRT_UNKNOWN",
        "ofr_crt_norm": None,
        "reason": "oa.ofrCrt is missing or unparseable.",
    }


def _normalise_restrictions(restrictions: Any) -> list[str]:
    """Coerce ``payload.restrictions`` into a deduped, upper-snake list.

    Accepts list, set, tuple, or any iterable of strings.  Filters
    falsy values; preserves insertion order for the deduped output."""
    if not isinstance(restrictions, (list, tuple, set, frozenset)):
        return []
    seen: list[str] = []
    for raw in restrictions:
        if raw is None:
            continue
        token = str(raw).strip().upper()
        if not token or token in seen:
            continue
        seen.append(token)
    return seen


def classify_seller_enforcement(restrictions: Optional[Iterable[Any]] = None,
                                wfs_eligible: Any = None,
                                seller_type: Optional[str] = None,
                                **_: Any) -> dict[str, Any]:
    """Deterministic enforcement gate.

    Inputs:
      - ``restrictions``  : ``payload.restrictions`` list from the
                            seller-enforcement endpoint (e.g.
                            ``["SELLER_PATH", "WALMART_PATH"]``).
      - ``wfs_eligible``  : ODIN ``oa.wfsElig`` (string/bool).
      - ``seller_type``   : ODIN ``styp`` (e.g. ``EXTERNAL``,
                            ``INTERNAL``).

    Output keys:
      - ``outcome``  — ENFORCEMENT_NOT_APPLICABLE | ENFORCEMENT_CLEAR
                       | ENFORCEMENT_BLOCKED
      - ``scope``    — the path that applies to this offer
                       (``WALMART_PATH`` / ``SELLER_PATH`` / None)
      - ``blocked``  — bool; True iff ``scope`` is in enforced set
      - ``enforced`` — the deduped, upper-cased restriction set as a
                       sorted list (useful for closure rendering)
      - ``reason``   — human-readable one-liner
    """
    styp = (seller_type or "").strip().upper()
    enforced = _normalise_restrictions(restrictions)

    if styp == "INTERNAL":
        return {
            "outcome":  "ENFORCEMENT_NOT_APPLICABLE",
            "scope":    None,
            "blocked":  False,
            "enforced": sorted(enforced),
            "reason":   "Internal seller — enforcement check skipped.",
        }

    wfs_norm = _norm_bool(wfs_eligible) is True
    scope = "WALMART_PATH" if wfs_norm else "SELLER_PATH"
    blocked = scope in enforced

    return {
        "outcome":  "ENFORCEMENT_BLOCKED" if blocked else "ENFORCEMENT_CLEAR",
        "scope":    scope,
        "blocked":  blocked,
        "enforced": sorted(enforced),
        "reason":   (
            f"{scope} {'is' if blocked else 'is not'} present in enforced "
            f"restrictions {sorted(enforced) or '[]'}."
        ),
    }


__all__ = [
    "check_offer_fully_created",
    "classify_seller_enforcement",
]
