"""
MERLOC Service — aisle location lookups via Uber Keys + Rampart.

Flow:
  1. Offer ID → GTINs   (Uber Keys: OFFERID_TO_GTIN)
  2. GTIN → CID         (Uber Keys: GTIN_TO_CID)
  3. CID + Store ID → Aisle locations (Rampart GraphQL)

Both ``NON_EMPTY_LOCATION_SIGNAL`` and ``NON_EMPTY_CONFIRMATION_SIGNAL``
carry the same raw locations list when any are found, otherwise ``None``
so IMP rules using IS_NULL semantics evaluate correctly:
  • locations exist → signal is non-null (the list)  → IS_NULL=true ⇒ False
  • no locations   → signal is None                  → IS_NULL=true ⇒ True
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from packs.offer_intelligence.services._instrumented_clients import (
    instrumented_httpx_client,
)
from packs.offer_intelligence.services.uber_keys_service import (
    get_uber_keys_mapping,
    get_uber_keys_mapping_list,
)
from packs.offer_intelligence.services.walmart_apis_config import (
    DEFAULT_REQUEST_TIMEOUT,
    RAMPART_BASE_URL,
    rampart_headers,
)

logger = logging.getLogger(__name__)


class MerlocServiceError(Exception):
    """Raised when a Merloc lookup cannot be completed."""


class MerlocService:
    """Resolve aisle locations for an offer at a given store."""

    def __init__(self, timeout: float = DEFAULT_REQUEST_TIMEOUT) -> None:
        self._timeout = timeout
        self._demo = self._should_demo()
        if self._demo:
            logger.warning(
                "merloc_service.demo_mode: MERLOC_DEMO=1 set — returning demo data"
            )
        else:
            logger.info("merloc_service.initialized: live mode enabled")

    @staticmethod
    def _should_demo() -> bool:
        """Demo mode is opt-in via ``MERLOC_DEMO=1`` env var (for local testing)."""
        return os.getenv("MERLOC_DEMO", "").strip() in ("1", "true", "True", "yes")

    # ── Public API ─────────────────────────────────────────────────────

    async def get_locations(self, offer_id: str, store_id: str) -> Dict[str, Any]:
        """Full lookup: Offer ID → GTINs → CID → Rampart locations."""
        if not offer_id or not store_id:
            raise MerlocServiceError("offer_id and store_id are required")

        offer_id = str(offer_id).strip()
        store_id = str(store_id).strip()

        if self._demo:
            demo_locations = ["DEMO-AISLE-A12", "DEMO-AISLE-B07"]
            return {
                "offer_id": offer_id,
                "store_id": store_id,
                "NON_EMPTY_LOCATION_SIGNAL": demo_locations,
                "NON_EMPTY_CONFIRMATION_SIGNAL": demo_locations,
                "location_count": len(demo_locations),
                "locations": demo_locations,
                "gtins": [],
                "cid": None,
                "_demo": True,
            }

        logger.info(f"merloc.lookup_start offer={offer_id} store={store_id}")

        gtins = await get_uber_keys_mapping_list(offer_id, "OFFERID_TO_GTIN")
        if not gtins:
            logger.warning(f"merloc.no_gtins offer={offer_id}")
            return self._empty_response(offer_id, store_id, gtins=[], cid=None)

        cid = await self._resolve_cid(gtins)
        if not cid:
            logger.warning(f"merloc.no_cid offer={offer_id} gtins={gtins}")
            return self._empty_response(offer_id, store_id, gtins=gtins, cid=None)

        locations, status_code = await self._fetch_locations(cid, store_id)
        signal: Optional[List[str]] = locations if locations else None

        return {
            "offer_id": offer_id,
            "store_id": store_id,
            "NON_EMPTY_LOCATION_SIGNAL": signal,
            "NON_EMPTY_CONFIRMATION_SIGNAL": signal,
            "location_count": len(locations),
            "locations": locations,
            "gtins": gtins,
            "cid": cid,
            "rampart_status_code": status_code,
        }

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _empty_response(
        offer_id: str, store_id: str, gtins: List[str], cid: Optional[str]
    ) -> Dict[str, Any]:
        """Return a canonical "no locations" response.

        Signals are ``None`` (null) so ``IS_NULL=true`` rules match.
        """
        return {
            "offer_id": offer_id,
            "store_id": store_id,
            "NON_EMPTY_LOCATION_SIGNAL": None,
            "NON_EMPTY_CONFIRMATION_SIGNAL": None,
            "location_count": 0,
            "locations": [],
            "gtins": gtins,
            "cid": cid,
        }

    @staticmethod
    async def _resolve_cid(gtins: List[str]) -> Optional[str]:
        """Try each GTIN until one resolves to a CID."""
        for gtin in gtins:
            cid = await get_uber_keys_mapping(gtin, "GTIN_TO_CID")
            if cid:
                logger.info(f"merloc.cid_resolved cid={cid} from_gtin={gtin}")
                return cid
        return None

    async def _fetch_locations(
        self, cid: str, store_id: str
    ) -> Tuple[List[str], Optional[int]]:
        """Call Rampart GraphQL for aisle locations."""
        query = (
            "query {\n"
            f'  storeRepl(countryCode:"US", storeId:{store_id}, '
            f'replenishmentGroupNumber: "{cid}") {{\n'
            "    assignmentInfo{\n"
            "      assignedLocations {\n"
            "        storeLocation {\n"
            "          sgln195\n"
            "        }\n"
            "        assignments {\n"
            "          gtin\n"
            "        }\n"
            "      }\n"
            "    }\n"
            "  }\n"
            "}\n"
        )
        payload = {"query": query, "variables": {}}

        logger.info(f"merloc.rampart_call cid={cid} store={store_id}")

        try:
            async with instrumented_httpx_client(
                service_name="merloc",
                verify=False,
                timeout=self._timeout,
            ) as client:
                response = await client.post(
                    RAMPART_BASE_URL,
                    headers=rampart_headers(),
                    json=payload,
                )
                status_code = response.status_code
                data = response.json()
            locations = self._parse_locations(data, cid, store_id)
            return locations, status_code
        except Exception as exc:
            logger.error(
                f"merloc.rampart_failed cid={cid} store={store_id} error={exc}"
            )
            return [], None

    @staticmethod
    def _parse_locations(data: dict, cid: str, store_id: str) -> List[str]:
        """Extract sgln195 values from Rampart response, filtering 'W.S' suffixes."""
        locations: List[str] = []
        try:
            store_repl = (data.get("data") or {}).get("storeRepl")
            if not store_repl:
                logger.info(f"merloc.no_store_repl cid={cid} store={store_id}")
                return locations
            assignment_info = store_repl.get("assignmentInfo")
            if not assignment_info or "assignedLocations" not in assignment_info:
                logger.info(f"merloc.no_assignments cid={cid} store={store_id}")
                return locations
            for loc_entry in assignment_info.get("assignedLocations") or []:
                sgln = (loc_entry.get("storeLocation") or {}).get("sgln195")
                if sgln is None:
                    continue
                sgln_str = str(sgln)
                if sgln_str and not sgln_str.endswith("W.S"):
                    locations.append(sgln_str)
        except Exception as exc:
            logger.error(f"merloc.parse_failed error={exc}")
        return locations


_service: MerlocService | None = None


def get_merloc_service() -> MerlocService:
    global _service
    if _service is None:
        _service = MerlocService()
    return _service
