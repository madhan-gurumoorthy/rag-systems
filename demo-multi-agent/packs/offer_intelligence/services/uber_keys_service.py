"""
Uber Keys Service — single source of truth for entity-mapping lookups.

Resolves ItemId ↔ OfferId ↔ WPID ↔ GTIN ↔ CID mappings via the
Uber Keys read API.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from packs.offer_intelligence.services._instrumented_clients import (
    instrumented_httpx_client,
)
from packs.offer_intelligence.services.walmart_apis_config import (
    UBER_KEYS_BASE_URL,
    UBER_KEYS_TIMEOUT,
    resolve_mapping_type,
    uber_keys_headers,
)

logger = logging.getLogger(__name__)


async def get_uber_keys_mapping(key: str, mapping_type: str) -> Optional[str]:
    """Look up an entity mapping via the Uber Keys API.

    Args:
        key: The identifier value to look up (e.g. an offer ID or GTIN).
        mapping_type: Friendly name (e.g. ``GTIN_TO_CID``, ``OFFERID_TO_GTIN``).

    Returns:
        The first mapped value, or ``None`` if not found / on error.
    """
    api_type = resolve_mapping_type(mapping_type)
    url = f"{UBER_KEYS_BASE_URL}?key={key}&type={api_type}"
    headers = uber_keys_headers()

    try:
        async with instrumented_httpx_client(
            service_name="uber_keys",
            timeout=UBER_KEYS_TIMEOUT,
        ) as client:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                result = response.json()
                if result and isinstance(result, list) and len(result) > 0:
                    value = str(result[0])
                    logger.info(
                        f"uber_keys.mapped key={key} value={value} type={mapping_type}"
                    )
                    return value
                logger.warning(f"uber_keys.empty key={key} type={mapping_type}")
                return None
            logger.warning(
                f"uber_keys.http_error status={response.status_code} key={key}"
            )
            return None
    except Exception as exc:
        logger.error(f"uber_keys.failed key={key} error={exc}")
        return None


async def get_uber_keys_mapping_list(key: str, mapping_type: str) -> List[str]:
    """Look up an entity mapping via Uber Keys, returning ALL values."""
    api_type = resolve_mapping_type(mapping_type)
    url = f"{UBER_KEYS_BASE_URL}?key={key}&type={api_type}"
    headers = uber_keys_headers()

    try:
        async with instrumented_httpx_client(
            service_name="uber_keys",
            timeout=UBER_KEYS_TIMEOUT,
        ) as client:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                result = response.json()
                if result and isinstance(result, list):
                    values = [str(v) for v in result]
                    logger.info(
                        f"uber_keys.mapped_list key={key} count={len(values)} type={mapping_type}"
                    )
                    return values
                logger.warning(
                    f"uber_keys.empty_list key={key} type={mapping_type}"
                )
                return []
            logger.warning(
                f"uber_keys.http_error status={response.status_code} key={key}"
            )
            return []
    except Exception as exc:
        logger.error(f"uber_keys.list_failed key={key} error={exc}")
        return []
