"""
OL API Service — calls the Offer Listing API to get listing status.

Real endpoint:
  GET /offerstore-app/api/setup/offerlisting/{offerId}/{martId}/{storeId}
"""
from __future__ import annotations

import logging
import re
import ssl
from typing import Any

import httpx

from packs.offer_intelligence.services._instrumented_clients import (
    instrumented_httpx_client,
)
from packs.offer_intelligence.services.walmart_apis_config import (
    LIGHTRAG_REQUESTS_CA_BUNDLE,
    OL_API_ENDPOINT,
)

logger = logging.getLogger(__name__)

# Demo mode data (used when OL_API_ENDPOINT is not configured)
_DEMO_DELISTED = {
    "listing_status": "DELISTED",
    "matched_rule_ids": ["192", "59"],
    "reason_codes": ["Offer-store is not valid", "Missing Start/End Dates"],
    "start_date_source": "LOCATION_SIGNAL",
    "end_date_source": "LOCATION_SIGNAL",
    "start_date": 1686132233579,
    "end_date": 1707161488791,
    "validity_types": [],
    "has_sellable_node_inventory": False,
    "last_inventory_modification_date": None,
    "ol_restriction_expiration_date": None,
    "_demo": True,
}


def _parse_rule_matches(rule_matches_str: str) -> list[str]:
    """Parse '{192=[192] Merloc: Validity Check, 96=[96] Firearms}' → ['192', '96']."""
    if not rule_matches_str or rule_matches_str in ("{}", ""):
        return []
    return re.findall(r"\b(\d+)=\[", rule_matches_str)


class OLApiService:
    def __init__(self):
        self._base_url = OL_API_ENDPOINT
        self._ca_bundle = LIGHTRAG_REQUESTS_CA_BUNDLE
        self._demo = not bool(self._base_url)
        if self._demo:
            logger.warning(
                "ol_api.demo_mode: OL_API_ENDPOINT not configured — returning demo data"
            )

    async def get_listing_status(
        self, offer_id: str, store_id: str, mart_id: str = "0"
    ) -> dict:
        if self._demo:
            demo = dict(_DEMO_DELISTED)
            demo["offer_id"] = offer_id
            demo["store_id"] = store_id
            demo["mart_id"] = mart_id
            return demo

        url = f"{self._base_url}/offerstore-app/api/setup/offerlisting/{offer_id}/{mart_id}/{store_id}"
        headers = {
            "Accept": "application/json",
            "WM_CONSUMER.ID": "ol-triage-agent",
            "WM_SVC.NAME": "OLTriageAgent",
            "WM_SVC.ENV": "prod",
            "WM_SVC.VERSION": "1.0",
            "WM_QOS.CORRELATION_ID": f"OL-{offer_id[:8]}",
        }

        try:
            ssl_ctx = None
            if self._ca_bundle:
                ssl_ctx = ssl.create_default_context()
                ssl_ctx.load_verify_locations(self._ca_bundle)

            async with instrumented_httpx_client(
                service_name="ol_api", verify=ssl_ctx or True, timeout=15,
            ) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.error(f"ol_api.request_failed error={exc}")
            raise

        payload = data.get("payload", {})
        ls = payload.get("listingStatus", {})
        scr = ls.get("statusChangeReasons", {})
        attrs = payload.get("offerListingAttributes", {})

        rule_matches_str = scr.get("ruleMatches", "{}")
        matched_rule_ids = _parse_rule_matches(rule_matches_str)

        reason_codes_raw = scr.get("reasonCodes", "")
        reason_codes = [r.strip() for r in reason_codes_raw.split(",")] if reason_codes_raw else []

        return {
            "offer_id": offer_id,
            "store_id": store_id,
            "mart_id": mart_id,
            "listing_status": ls.get("status", "UNKNOWN"),
            "matched_rule_ids": matched_rule_ids,
            "reason_codes": reason_codes,
            "start_date_source": payload.get("startDateSource"),
            "end_date_source": payload.get("endDateSource"),
            "start_date": payload.get("startDate"),
            "end_date": payload.get("endDate"),
            "validity_types": attrs.get("validityTypes"),
            "has_sellable_node_inventory": attrs.get("hasSellableNodeInventory"),
            "last_inventory_modification_date": attrs.get("lastInventoryModificationDate"),
            "ol_restriction_expiration_date": attrs.get("olRestrictionExpirationDate"),
        }


_service: OLApiService | None = None


def get_ol_api_service() -> OLApiService:
    global _service
    if _service is None:
        _service = OLApiService()
    return _service
