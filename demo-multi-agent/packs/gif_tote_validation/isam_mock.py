from __future__ import annotations

from typing import Any

from agent_factory.integrations.isam import mock_lookup

MOCK_MERCHANT_EMAIL = "rajeshkumar.mohankumar@walmart.com"


def mock_isam_lookup(
    gtin: str,
    action: str = "lookup_merchant_email",
    dimensions: str = "",
) -> dict[str, Any]:
    """Return a fixed merchant email for any GTIN (mock until real iSAM API is wired)."""
    return mock_lookup(
        gtin,
        action=action,
        dimensions=dimensions,
        mock_email=MOCK_MERCHANT_EMAIL,
    )


__all__ = ["mock_isam_lookup", "MOCK_MERCHANT_EMAIL"]
