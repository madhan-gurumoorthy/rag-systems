"""
Inventory Service — inventory signals from Oasis Glass API.

Real endpoint:
  POST {OASIS_ENDPOINT}/oasis-glass-api/v1/inventory/lookup

entry fields covered: hasInventory, hasSellableNodeInventory, lastInventoryModificationDate
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
    OASIS_ENDPOINT,
)

logger = logging.getLogger(__name__)


class InventoryService:
    def __init__(self):
        self._base_url = OASIS_ENDPOINT
        self._ca_bundle = LIGHTRAG_REQUESTS_CA_BUNDLE
        logger.info("inventory_service.initialized: live mode enabled")

    async def get_inventory_signals(self, offer_id: str, store_id: str) -> dict:
        url = f"{self._base_url}/oasis-glass-api/v1/inventory/lookup"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "WM_BU_ID": "WMT",
            "WM_CONSUMER.COUNTRY_CODE": "US",
            "WM_CONSUMER.ID": "ol-triage-agent",
            "WM_QOS.CORRELATION_ID": f"OL-INV-{offer_id[:8]}",
            "WM_SEC.KEY_VERSION": "2",
            "WM_SVC.ENV": "prod",
            "WM_SVC.NAME": "OLTriageAgent",
            "WM_SVC.VERSION": "1.0.0",
        }
        body = {
            "payload": [
                {
                    "offerId": offer_id,
                    "sellerId": "",
                    "nodeGroups": [],
                    "nodes": [int(store_id)],
                    "preferredStores": [int(store_id)],
                }
            ]
        }

        ssl_ctx = None
        if self._ca_bundle:
            ssl_ctx = ssl.create_default_context()
            ssl_ctx.load_verify_locations(self._ca_bundle)

        try:
            async with instrumented_httpx_client(
                service_name="oasis_inventory", verify=ssl_ctx or True, timeout=15,
            ) as client:
                resp = await client.post(url, headers=headers, json=body)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.error(
                f"inventory_service.request_failed offer={offer_id} store={store_id} error={exc}"
            )
            return self._null_result(offer_id, store_id, note=f"Oasis API error: {exc}")

        items = data.get("payload", data) if isinstance(data, dict) else data
        item = items[0] if isinstance(items, list) and items else {}

        return {
            "offer_id": offer_id,
            "store_id": store_id,
            "hasInventory": item.get("hasInventory"),
            "hasSellableNodeInventory": item.get("hasSellableNodeInventory"),
            "lastInventoryModificationDate": item.get("lastInventoryModificationDate"),
        }

    def _null_result(self, offer_id: str, store_id: str, note: str = "") -> dict:
        return {
            "offer_id": offer_id,
            "store_id": store_id,
            "hasInventory": None,
            "hasSellableNodeInventory": None,
            "lastInventoryModificationDate": None,
            "_error": True,
            "note": note,
        }


_service: InventoryService | None = None


def get_inventory_service() -> InventoryService:
    global _service
    if _service is None:
        _service = InventoryService()
    return _service
