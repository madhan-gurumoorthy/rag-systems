"""Deterministic Marketplace (MP) offer classification.

Decides whether an ODIN offer is a Marketplace offer that should follow
the weight-only validation path, based on ``seller_type`` and
``wfs_eligible`` from the DIAG-ODIN-01 result.  The classification is
intentionally a Python function — not an LLM judgement — so the gate
cannot be missed when the upstream payload omits ``wfsElig`` or carries
mixed casing.

Contract
--------
Inputs (all optional):
  * ``seller_type``   — ODIN ``styp`` (e.g. ``"EXTERNAL"`` / ``"INTERNAL"``).
  * ``wfs_eligible``  — ODIN ``wfsElig`` (may be ``"TRUE"``/``"FALSE"`` /
                        bool / ``None`` / absent).

Returns (always a dict with these keys):
  * ``outcome``              — ``MP_OFFER`` | ``STANDARD_OFFER``
  * ``mp_offer``             — bool
  * ``reason``               — one-line explanation referencing the
                                 normalized inputs
  * ``seller_type_norm``     — ``str`` (uppercase) | ``None``
  * ``wfs_eligible_norm``    — ``"TRUE"`` | ``"FALSE"`` | ``None``

Rules
-----
An offer is MP when **both**:
  1. ``wfs_eligible_norm`` is ``"FALSE"`` or ``None`` (absent counts).
  2. ``seller_type_norm`` equals ``"EXTERNAL"``.

Any other combination is a standard offer.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _norm_seller_type(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text.upper()


def _norm_wfs_eligible(value: Any) -> Optional[str]:
    """Normalize ``wfsElig`` to ``"TRUE"``, ``"FALSE"``, or ``None``.

    Treats absent / empty / unrecognized values as ``None`` so the caller
    can apply the "absent counts as FALSE" rule explicitly.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    text = str(value).strip()
    if not text:
        return None
    upper = text.upper()
    if upper in {"TRUE", "FALSE"}:
        return upper
    if upper in {"YES", "Y", "1"}:
        return "TRUE"
    if upper in {"NO", "N", "0"}:
        return "FALSE"
    return None


def classify_mp_offer(
    seller_type: Any = None,
    wfs_eligible: Any = None,
) -> dict[str, Any]:
    """Classify an ODIN offer as Marketplace (MP) or standard.

    Pure function — no I/O, no state access.  The DiagnosticAgent calls
    this immediately after DIAG-ODIN-01 and routes off the boolean
    ``mp_offer`` flag in the result.
    """
    seller_norm = _norm_seller_type(seller_type)
    wfs_norm = _norm_wfs_eligible(wfs_eligible)

    is_external = seller_norm == "EXTERNAL"
    is_non_wfs = wfs_norm in (None, "FALSE")
    mp_offer = bool(is_external and is_non_wfs)

    if mp_offer:
        reason = (
            f"seller_type={seller_norm!r} and wfs_eligible="
            f"{wfs_norm if wfs_norm is not None else 'absent'} "
            "→ Marketplace offer (weight-only validation)"
        )
        outcome = "MP_OFFER"
    else:
        bits = []
        if not is_external:
            bits.append(f"seller_type={seller_norm!r} is not 'EXTERNAL'")
        if not is_non_wfs:
            bits.append(f"wfs_eligible={wfs_norm!r} is TRUE")
        reason = "; ".join(bits) + " → standard offer (full dimension validation)"
        outcome = "STANDARD_OFFER"

    result = {
        "outcome": outcome,
        "mp_offer": mp_offer,
        "reason": reason,
        "seller_type_norm": seller_norm,
        "wfs_eligible_norm": wfs_norm,
    }
    logger.info(
        "mp_classify: seller_type=%r wfs_eligible=%r -> %s",
        seller_type,
        wfs_eligible,
        outcome,
    )
    return result


__all__ = ["classify_mp_offer"]
