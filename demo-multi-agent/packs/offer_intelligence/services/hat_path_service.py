"""
HAT Path Service — resolves hatPathIds for an offer via the IQS Uber API.

hatPathIds is the Hierarchy and Taxonomy (HAT) category path for an item,
expressed as colon-separated node IDs (e.g. "38:6376:12093:31078:1740").
Rules use MATCHES_IN / NOT_MATCHES_IN with wildcard patterns against this list.

Flow:
  1. Resolve Offer ID → WPID via Uber Keys (OFFERID_TO_WPID mapping).
  2. Call IQS Uber v2: GET /uber/v2/?type=WPID&id={wpid}&rt=PRODUCT
     (same RSA-signed auth as SIV service)
  3. Extract hat.values[].path_id from the response.

entry fields covered: hatPathIds
"""
from __future__ import annotations

import logging
from typing import List, Optional

import httpx

from packs.offer_intelligence.services._instrumented_clients import (
    instrumented_httpx_client,
)
from packs.offer_intelligence.services.iqs_auth import iqs_signed_headers
from packs.offer_intelligence.services.walmart_apis_config import (
    IQS_BASE_URL,
    SIV_REQUEST_TIMEOUT,
)

logger = logging.getLogger(__name__)

# IQS Uber v2 endpoint — strip /catalog/v1 suffix, append /uber/v2/
_IQS_HOST = IQS_BASE_URL.split("/catalog")[0]  # e.g. http://iqs.walmart.com
IQS_UBER_URL = f"{_IQS_HOST}/uber/v2/"


def _iqs_signed_headers() -> dict:
    """Build RSA-signed IQS headers for the HAT-path service."""
    return iqs_signed_headers(
        svc_name="inboundorder",
        svc_version="1.0.0",
        extra={"WM_SVC.ENV": "prod"},
    )


async def _resolve_wpid(offer_id: str) -> Optional[str]:
    """Resolve Offer ID → WPID via Uber Keys."""
    try:
        from packs.offer_intelligence.services.uber_keys_service import get_uber_keys_mapping

        wpid = await get_uber_keys_mapping(offer_id, "OFFERID_TO_WPID")
        if wpid:
            logger.info(f"hat_path_service.wpid_resolved offer_id={offer_id} wpid={wpid}")
        else:
            logger.warning(f"hat_path_service.wpid_not_found offer_id={offer_id}")
        return wpid
    except Exception as exc:
        logger.error(f"hat_path_service.wpid_resolve_failed offer_id={offer_id} error={exc}")
        return None


async def _fetch_hat_path_ids(wpid: str) -> List[str]:
    """Call IQS Uber v2 with signed headers and extract hat.values[].path_id."""
    params = {"type": "WPID", "id": wpid, "rt": "PRODUCT"}
    try:
        headers = _iqs_signed_headers()
    except RuntimeError as exc:
        logger.error(f"hat_path_service.auth_error wpid={wpid} error={exc}")
        return []

    try:
        async with instrumented_httpx_client(
            service_name="hat_path", timeout=SIV_REQUEST_TIMEOUT, verify=False,
        ) as client:
            resp = await client.get(IQS_UBER_URL, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        payload = data.get("payload", {})
        product = payload.get("product", {})
        derived = product.get("derived_attributes", {})
        hat_block = derived.get("hat", {})
        values = hat_block.get("values", [])
        path_ids = [
            entry["path_id"]
            for entry in values
            if isinstance(entry, dict) and entry.get("path_id")
        ]
        logger.info(f"hat_path_service.iqs_ok wpid={wpid} path_ids={path_ids}")
        return path_ids

    except httpx.HTTPStatusError as exc:
        logger.error(
            f"hat_path_service.iqs_http_error wpid={wpid} "
            f"status={exc.response.status_code} body={exc.response.text[:200]}"
        )
        return []
    except Exception as exc:
        logger.error(f"hat_path_service.iqs_failed wpid={wpid} error={exc}")
        return []


class HatPathService:
    """Resolves hatPathIds for an offer via IQS Uber v2 API."""

    async def get_hat_path_ids(self, offer_id: str) -> dict:
        """Resolve hatPathIds for an offer.

        Returns dict with:
          offer_id   (str)
          wpid       (str | None)
          hatPathIds (List[str]) — path_id values from hat.values[]
        """
        wpid = await _resolve_wpid(offer_id)
        if not wpid:
            return {
                "offer_id": offer_id,
                "wpid": None,
                "hatPathIds": [],
                "_note": "Could not resolve WPID — hatPathIds unavailable",
            }

        hat_path_ids = await _fetch_hat_path_ids(wpid)
        return {
            "offer_id": offer_id,
            "wpid": wpid,
            "hatPathIds": hat_path_ids,
        }


_service: HatPathService | None = None


def get_hat_path_service() -> HatPathService:
    global _service
    if _service is None:
        _service = HatPathService()
    return _service
