"""
Product Service — item/product attributes from the Product Store Read API.

Real endpoint:
  POST {PRODUCT_API_ENDPOINT}/itemstore-item-read-app/services/product
  Body: [{"productId": "<wpid>"}]

entry fields covered:
  productClassType, productType, itemId, ItemClassId,
  approvedForAnimals, Personalization, PersonalizationURL
"""
from __future__ import annotations

import logging
import ssl

import httpx

from packs.offer_intelligence.services._instrumented_clients import (
    instrumented_httpx_client,
)
from packs.offer_intelligence.services.uber_keys_service import get_uber_keys_mapping
from packs.offer_intelligence.services.walmart_apis_config import (
    LIGHTRAG_REQUESTS_CA_BUNDLE,
    PRODUCT_API_ENDPOINT,
)

logger = logging.getLogger(__name__)


class ProductService:
    def __init__(self):
        self._base_url = PRODUCT_API_ENDPOINT
        self._ca_bundle = LIGHTRAG_REQUESTS_CA_BUNDLE
        self._demo = False  # always try live; falls back gracefully on error
        logger.info("product_service.initialized: live mode enabled")

    async def get_product_attributes(self, offer_id: str) -> dict:
        # Resolve offer_id → WPID via Uber Keys
        try:
            wpid = await get_uber_keys_mapping(offer_id, "OFFERID_TO_WPID")
        except Exception as exc:
            logger.warning(f"product_service.wpid_lookup_failed offer={offer_id} error={exc}")
            wpid = None

        if not wpid:
            logger.warning(f"product_service.no_wpid offer={offer_id}")
            return self._null_result(offer_id, note="WPID not resolved — product attributes unavailable")

        url = f"{self._base_url}/itemstore-item-read-app/services/product"
        headers = {
            "response_groups": "item.VARIANT_SUMMARY",
            "x-o-bu": "WALMART-US",
            "accept-language": "es-US, en-US",
            "Content-Type": "application/json",
        }

        ssl_ctx = None
        if self._ca_bundle:
            ssl_ctx = ssl.create_default_context()
            ssl_ctx.load_verify_locations(self._ca_bundle)

        try:
            async with instrumented_httpx_client(
                service_name="product_store", verify=ssl_ctx or True, timeout=15,
            ) as client:
                resp = await client.post(url, headers=headers, json=[{"productId": wpid}])
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.error(
                f"product_service.request_failed offer={offer_id} wpid={wpid} error={exc}"
            )
            return self._null_result(offer_id, note=f"Product API error: {exc}")

        # Response is a list; take first item — shape: data[0] is the product object directly
        item = data[0] if isinstance(data, list) and data else (data if isinstance(data, dict) else {})
        payload = item.get("item", item)
        attrs = payload.get("productAttributes", {})

        def _attr(name: str):
            """Extract value from ``productAttributes[name].value`` (flat attr objects)."""
            obj = attrs.get(name, {})
            return obj.get("value") if isinstance(obj, dict) else None

        item_id = (
            _attr("item_id")
            or payload.get("itemId")
            or payload.get("usItemId")
            or (str(item.get("productId", {}).get("USItemId", "")) or None)
        )
        item_class_id = _attr("item_class_id") or payload.get("itemClassId") or payload.get("ItemClassId")
        approved_for_animals = _attr("approved_for_animals") or payload.get("approvedForAnimals")

        return {
            "offer_id": offer_id,
            "wpid": wpid,
            "productClassType": payload.get("productClassType"),
            "productType": payload.get("productType") or _attr("product_type"),
            "itemId": item_id,
            "ItemClassId": item_class_id,
            "approvedForAnimals": approved_for_animals,
            "Personalization": _attr("personalization") or payload.get("personalization") or payload.get("Personalization"),
            "PersonalizationURL": _attr("personalizationUrl") or payload.get("personalizationUrl") or payload.get("PersonalizationURL"),
        }

    def _null_result(self, offer_id: str, note: str = "") -> dict:
        return {
            "offer_id": offer_id,
            "productClassType": None,
            "productType": None,
            "itemId": None,
            "ItemClassId": None,
            "approvedForAnimals": None,
            "Personalization": None,
            "PersonalizationURL": None,
            "_demo": True,
            "note": note,
        }


_service: ProductService | None = None


def get_product_service() -> ProductService:
    global _service
    if _service is None:
        _service = ProductService()
    return _service
