"""
Store Price Service — store-specific pricing from Item Pricing Setup Service.

Real endpoint:
  POST {STORE_PRICE_ENDPOINT}/item-pricing/pricing/offerpricings

entry fields covered: storePrice, priceTypeCode, previewPriceReasonCode
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
    STORE_PRICE_ENDPOINT,
)

logger = logging.getLogger(__name__)


class StorePriceService:
    def __init__(self):
        self._base_url = STORE_PRICE_ENDPOINT
        self._ca_bundle = LIGHTRAG_REQUESTS_CA_BUNDLE
        logger.info("store_price_service.initialized: live mode enabled")

    async def get_store_price(self, offer_id: str, store_id: str) -> dict:
        url = f"{self._base_url}/item-pricing/pricing/offerpricings"
        headers = {
            "WM_SVC.VERSION": "1.0.0",
            "WM_CONSUMER.IP": "127.0.0.1",
            "WM_SVC.ENV": "PROD",
            "WM_QOS.CORRELATION_ID": f"OL-PRICE-{offer_id[:8]}",
            "WM_SEC.AUTH_TOKEN": "OLTriageAgent",
            "WM_CONSUMER.INTIMESTAMP": "0",
            "Accept": "application/json",
            "WM_CONSUMER.ID": "ol-triage-agent",
            "WM_IFX.CLIENT_TYPE": "INTERNAL",
            "Content-Type": "application/json",
            "WM_SVC.NAME": "OLTriageAgent",
        }
        body = {
            "offerPriceIdList": [
                {
                    "offerId": {"offerId": offer_id},
                    "storeFrontId": {"USStoreId": int(store_id)},
                }
            ]
        }

        ssl_ctx = None
        if self._ca_bundle:
            ssl_ctx = ssl.create_default_context()
            ssl_ctx.load_verify_locations(self._ca_bundle)

        try:
            async with instrumented_httpx_client(
                service_name="item_pricing_setup", verify=ssl_ctx or True, timeout=15,
            ) as client:
                resp = await client.post(url, headers=headers, json=body)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.error(
                f"store_price_service.request_failed offer={offer_id} store={store_id} error={exc}"
            )
            return self._null_result(offer_id, store_id, note=f"Price API error: {exc}")

        payload = data.get("payload", {})
        offer_pricing_list = payload.get("offerPricingList", [])
        offer_item = offer_pricing_list[0] if offer_pricing_list else {}
        storefront_list = offer_item.get("storefrontPricingList", [])
        sf = storefront_list[0] if storefront_list else {}
        additional = sf.get("additionalAttributes", {})

        current_price_obj = sf.get("currentPrice", {})
        current_value = current_price_obj.get("currentValue", {})
        store_price = current_value.get("currencyAmount")

        return {
            "offer_id": offer_id,
            "store_id": store_id,
            "storePrice": store_price,
            "priceTypeCode": additional.get("priceTypeCode"),
            "previewPriceReasonCode": sf.get("previewPriceReasonCode")
            or additional.get("previewPriceReasonCode"),
        }

    def _null_result(self, offer_id: str, store_id: str, note: str = "") -> dict:
        return {
            "offer_id": offer_id,
            "store_id": store_id,
            "storePrice": None,
            "priceTypeCode": None,
            "previewPriceReasonCode": None,
            "_error": True,
            "note": note,
        }


_service: StorePriceService | None = None


def get_store_price_service() -> StorePriceService:
    global _service
    if _service is None:
        _service = StorePriceService()
    return _service
