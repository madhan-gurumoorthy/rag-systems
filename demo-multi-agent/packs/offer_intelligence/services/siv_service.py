"""
SIV (Store Item Verification) Service.

Retrieves store-specific SIV metadata from the IQS (Item Query Service) API
using RSA-signed authentication.

Flow:
  1. Resolve all GTINs for the offer via Uber Mappings (POST).
  2. For each GTIN, call IQS with an RSA-signed token to fetch SIV content
     for the given store.
  3. Aggregate ``validityTypeCode``s, ``salesExistsInd``, and ``isRecallInd``
     across GTINs into a single response.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, Set, Tuple

import httpx

from packs.offer_intelligence.services._instrumented_clients import (
    instrumented_httpx_client,
)
from packs.offer_intelligence.services.iqs_auth import iqs_signed_headers
from packs.offer_intelligence.services.walmart_apis_config import (
    IQS_BASE_URL,
    SIV_CONCURRENCY,
    SIV_REQUEST_TIMEOUT,
    UBER_MAPPING_BASE_URL,
    get_iqs_private_key_text,
    uber_mapping_headers,
)

logger = logging.getLogger(__name__)


# ── SIV Service ──────────────────────────────────────────────────────────

class SIVService:
    """Store Item Verification service."""

    def __init__(self):
        self._has_key = bool(get_iqs_private_key_text())
        self._demo = not self._has_key
        if self._demo:
            logger.warning(
                "siv_service.demo_mode: no RSA private key configured — "
                "returning demo SIV data. Configure IQS_PRIVATE_KEY or "
                "IQS_PRIVATE_KEY_PATH for real data."
            )
        else:
            logger.info("siv_service.initialized: live mode enabled")

    # ── GTIN resolution via Uber Mappings ──────────────────────────────

    async def _fetch_gtins_for_offer(
        self, client: httpx.AsyncClient, offer_id: str
    ) -> List[str]:
        """Resolve GTINs from an offer ID via the Uber Mappings POST API."""
        payload = [{
            "request_id": "4",
            "key": offer_id,
            "type": "DOTCOM_OFFER_ID_TO_GTIN",
        }]

        try:
            response = await client.post(
                UBER_MAPPING_BASE_URL,
                headers=uber_mapping_headers(),
                json=payload,
                timeout=SIV_REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
            if not data:
                return []
            response_body = data[0].get("response", {}) if isinstance(data, list) else {}
            values = response_body.get("data", {}).get("values", [])
            return [str(v) for v in values] if isinstance(values, list) else []
        except Exception as exc:
            logger.error(f"siv_service.uber_mapping_failed offer={offer_id} error={exc}")
            return []

    # ── Single-GTIN SIV fetch ──────────────────────────────────────────

    async def _fetch_siv_content(
        self, client: httpx.AsyncClient, gtin: str, store_id: str
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Fetch SIV content for one GTIN at one store."""
        headers = iqs_signed_headers()
        params = {
            "id": str(gtin),
            "type": "GTIN",
            "rt": "SIV",
            "includeSivContent": "true",
            "storeNumber": str(store_id),
        }

        response = await client.get(
            IQS_BASE_URL,
            headers=headers,
            params=params,
            timeout=SIV_REQUEST_TIMEOUT,
        )
        response.raise_for_status()

        payload = response.json().get("payload", {})
        siv_items = payload.get("sivItems", {}) or {}
        content_map = siv_items.get("content", {}) or {}
        store_content = content_map.get(str(store_id), {}) or {}
        attributes = store_content.get("attributes", {}) or {}
        si_attributes = store_content.get("siAttributes", []) or []
        return attributes, si_attributes

    # ── Public API ─────────────────────────────────────────────────────

    async def get_siv_data(self, offer_id: str, store_id: str) -> Dict[str, Any]:
        """Get aggregated SIV data for an offer at a store."""
        if self._demo:
            return {
                "offer_id": offer_id,
                "store_id": store_id,
                "ValidityTypes": ["VALID"],
                "hasSales": False,
                "recallFlag": False,
                "gtins": [],
                "_demo": True,
            }

        try:
            async with instrumented_httpx_client(service_name="siv") as client:
                gtins = await self._fetch_gtins_for_offer(client, offer_id)
                if not gtins:
                    return {
                        "offer_id": offer_id,
                        "store_id": store_id,
                        "ValidityTypes": [],
                        "hasSales": False,
                        "recallFlag": False,
                        "gtins": [],
                        "note": "No GTINs found for this offer",
                    }

                semaphore = asyncio.Semaphore(SIV_CONCURRENCY)
                validity_codes: Set[str] = set()
                has_sales: Optional[bool] = None
                is_recall: Optional[bool] = None
                errors: List[str] = []
                successful_fetches = 0

                async def _fetch_one(gtin: str) -> None:
                    nonlocal has_sales, is_recall, successful_fetches
                    async with semaphore:
                        try:
                            attrs, si_attrs = await self._fetch_siv_content(
                                client, gtin, store_id
                            )
                            successful_fetches += 1
                            sales = attrs.get("salesExistsInd")
                            if sales is not None:
                                has_sales = bool(sales) if has_sales is None else (has_sales or bool(sales))
                            elif has_sales is None:
                                has_sales = False
                            if attrs.get("isRecallInd"):
                                is_recall = True
                            elif is_recall is None:
                                is_recall = False
                            for entry in si_attrs:
                                code = entry.get("validityTypeCode")
                                if code:
                                    validity_codes.add(str(code))
                        except Exception as exc:
                            logger.warning(
                                f"siv_service.gtin_fetch_failed gtin={gtin} error={exc}"
                            )
                            errors.append(f"{gtin}: {str(exc)[:120]}")

                await asyncio.gather(*[_fetch_one(g) for g in gtins])

                result: Dict[str, Any] = {
                    "offer_id": offer_id,
                    "store_id": store_id,
                    "ValidityTypes": sorted(validity_codes),
                    "hasSales": has_sales,
                    "recallFlag": is_recall,
                    "gtins": gtins,
                }
                if errors:
                    result["errors"] = errors
                return result

        except Exception as exc:
            logger.error(
                f"siv_service.get_siv_data_failed offer={offer_id} store={store_id} error={exc}"
            )
            raise


_service: SIVService | None = None


def get_siv_service() -> SIVService:
    global _service
    if _service is None:
        _service = SIVService()
    return _service
