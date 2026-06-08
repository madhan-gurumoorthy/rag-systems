"""
Offer Service — offer-level attributes from the Offer RT API.

Real endpoint:
  GET {OL_API_ENDPOINT}/offerstore-app/api/setup/offer/{offerId}

entry fields covered: sellerId, wfsEligible, offerGroupType, offerGroupSubType
"""
from __future__ import annotations

import logging
import ssl

import httpx

from packs.offer_intelligence.services._instrumented_clients import (
    instrumented_httpx_client,
)
from packs.offer_intelligence.services.walmart_apis_config import (
    LIGHTRAG_REQUESTS_CA_BUNDLE,
    OFFER_API_ENDPOINT,
    OL_API_ENDPOINT,
)

logger = logging.getLogger(__name__)


class OfferService:
    def __init__(self):
        # Reuse the same base URL as OL API (same host, different path)
        self._base_url = OFFER_API_ENDPOINT or OL_API_ENDPOINT
        self._ca_bundle = LIGHTRAG_REQUESTS_CA_BUNDLE
        self._demo = not bool(self._base_url)
        if self._demo:
            logger.warning("offer_service.demo_mode")
        else:
            logger.info("offer_service.initialized: live mode enabled")

    async def get_offer_attributes(self, offer_id: str) -> dict:
        if self._demo:
            return {
                "offer_id": offer_id,
                "sellerId": None,
                "wfsEligible": None,
                "offerGroupType": None,
                "offerGroupSubType": None,
                "_demo": True,
                "note": "Offer API endpoint not configured — offer attributes unavailable",
            }

        url = f"{self._base_url}/offerstore-app/api/setup/offer/{offer_id}"
        headers = {
            "accept": "application/json",
            "cache-control": "no-cache",
            "wm_consumer.id": "ol-triage-agent",
            "wm_mart_id": "0",
            "wm_qos.correlation_id": f"OL-OFFER-{offer_id[:8]}",
            "wm_svc.env": "prod",
            "wm_svc.name": "OLTriageAgent",
            "wm_svc.version": "2.0",
            "wm_vertical_id": "0",
        }

        ssl_ctx = None
        if self._ca_bundle:
            ssl_ctx = ssl.create_default_context()
            ssl_ctx.load_verify_locations(self._ca_bundle)

        try:
            async with instrumented_httpx_client(
                service_name="offer_rt", verify=ssl_ctx or True, timeout=15,
            ) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.error(f"offer_service.request_failed offer={offer_id} error={exc}")
            raise

        payload = data.get("payload", data)
        return {
            "offer_id": offer_id,
            "sellerId": payload.get("sellerId"),
            "wfsEligible": payload.get("wfsEligible"),
            "offerGroupType": payload.get("offerGroupType"),
            "offerGroupSubType": payload.get("offerGroupSubType"),
        }


_service: OfferService | None = None


def get_offer_service() -> OfferService:
    global _service
    if _service is None:
        _service = OfferService()
    return _service
