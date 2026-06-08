"""Generic iSAM lookup client — mock-only until the real API is available."""
from __future__ import annotations

from typing import Any, Optional


def mock_lookup(
    gtin: str,
    *,
    action: str = "lookup_merchant_email",
    dimensions: str = "",
    mock_response: Optional[dict[str, Any]] = None,
    mock_email: Optional[str] = None,
) -> dict[str, Any]:
    """Return a fixed-response iSAM lookup (mock).

    Args:
        gtin: 14-digit GTIN (or any string); echoed in the response
            but not used to resolve the mock email.
        action: ``lookup_merchant_email`` or ``update_dimensions`` —
            recorded in the response so callers can branch on the
            requested operation.  The mock does not persist updates.
        dimensions: Unused in mock; reserved for future real-API parity.
        mock_response: Full override dict — if supplied, returned
            (after merging ``gtin`` / ``action`` / ``mock`` / ``source``
            metadata onto it).  Lets packs simulate any response shape
            their tool contract expects.
        mock_email: Convenience for the common case of supplying just
            the merchant email; merged under the ``merchant_email``
            key if provided.

    Returns:
        Dict with ``gtin``, ``action``, ``mock``, ``source`` (always)
        plus whatever the caller supplied via ``mock_response`` /
        ``mock_email``.
    """
    _ = dimensions  # reserved for real iSAM

    out: dict[str, Any] = {
        "gtin": (gtin or "").strip(),
        "action": action,
        "mock": True,
        "source": "isam_mock",
        "note": (
            "Placeholder until iSAM API is integrated; response is fixed regardless of GTIN."
        ),
    }
    if mock_response:
        out.update(mock_response)
    if mock_email is not None:
        out["merchant_email"] = mock_email
    return out


__all__ = ["mock_lookup"]
