"""
Offer Validator Service.

Validates whether a Walmart offer is correctly or wrongly unpublished
by fetching relevant IQS API data and running reason-code-specific validators.

All ``iqs.walmart.com`` calls (catalog/v1 + uber/v1) are RSA-signed via
``services.iqs_auth.iqs_signed_headers`` using the pack's IQS private
key (``packs/offer_intelligence/certs/iqs_private_key.key`` or the
``IQS_PRIVATE_KEY`` / ``IQS_PRIVATE_KEY_PATH`` env vars).
"""
import asyncio
import os
from typing import Any, Dict, List, Optional

import httpx

from agent_factory.common.logging import get_logger
from packs.offer_intelligence.offer_validators import get_validator, validate_unknown_reason
from packs.offer_intelligence.result import ValidationResult, ValidationStatus
from packs.offer_intelligence.services.iqs_auth import iqs_signed_headers
from packs.offer_intelligence.services.walmart_apis_config import (
    IQS_BASE_URL as _IQS_BASE_URL,
    IQS_UBER_V1_URL as _IQS_UBER_URL,
)

logger = get_logger("offer_intelligence.validator")

# ---------------------------------------------------------------------------
# Non-IQS API configuration — env-var driven with production defaults
# ---------------------------------------------------------------------------

_OASIS_BASE_URL = os.getenv(
    "OASIS_BASE_URL",
    "http://oasis-availability-api-sf.wakanda.prod.walmart.com/oasis-glass-api/v1/inventory/lookup",
)
_OASIS_CONSUMER_ID = os.getenv("OASIS_CONSUMER_ID", "4e039f25-a0d8-4b94-8c72-9839aab7cdcb")
_CASTAR_BASE_URL = os.getenv(
    "CASTAR_BASE_URL",
    "http://services.centralized-audit.glb.us.walmart.net/castar/api/query",
)
_CASTAR_CONSUMER_ID = os.getenv("CASTAR_CONSUMER_ID", "1dcf32d2-2efd-457f-89cc-c49d06eb9d86")
_OFFER_STORE_BASE_URL = os.getenv(
    "OFFER_STORE_BASE_URL",
    "http://offer-store-setup.prod.offerstore.catdev.prod.walmart.com/offerstore-app/api/setup",
)
_OFFER_STORE_CONSUMER_ID = os.getenv("OFFER_STORE_CONSUMER_ID", "08720b9a-1a2d-4e9a-a394-10d243a3a7b2")
_PRODUCT_MATCHING_BASE_URL = os.getenv(
    "PRODUCT_MATCHING_BASE_URL",
    "https://product-matching-lookup-api.prod.catalog-product-setup.walmart.com/v1/lookup",
)
_PRODUCT_STORE_READ_BASE_URL = os.getenv(
    "PRODUCT_STORE_READ_BASE_URL",
    "http://product-store-read-app.prod.walmart.com/itemstore-item-read-app/services/product",
)
_GCI_SCAN_BASE_URL = os.getenv("GCI_SCAN_BASE_URL", "http://gci-scan.us.walmart.com/search/_sql")
_GCI_SCAN_CONSUMER_ID = os.getenv("GCI_SCAN_CONSUMER_ID", "a585194d-f948-4e22-b8ec-265932d09cac")

_DEFAULT_TIMEOUT = 30.0

# ---------------------------------------------------------------------------
# IQS request headers — RSA-signed via the shared signature manager
# ---------------------------------------------------------------------------

# Service identifier kept stable per pack contract — the IQS consumer
# behind the signing key is whitelisted under this name.
_IQS_SVC_NAME = "transone-offer-validator"
_IQS_SVC_VERSION = "1.0.0"


def _iqs_headers() -> Dict[str, str]:
    """Build a fresh RSA-signed IQS header set.

    Each call gets a fresh ``WM_QOS.CORRELATION_ID`` and a signature
    that's cached internally (re-signed only after the token TTL).
    """
    return iqs_signed_headers(
        svc_name=_IQS_SVC_NAME,
        svc_version=_IQS_SVC_VERSION,
        extra={
            "WM_SVC.ENV": "prod",
            "WM_MART_ID": "0",
        },
    )


# Walmart 1P seller ID — used to scope offer queries
_WALMART_1P_SELLER_ID = "F55CDC31AB754BB68FE0B39041159D63"

# Uber Keys — separate URL + consumer ID used for bundle/GTIN mappings
_UBER_KEYS_BASE_URL = "http://uber-keys-read-nsf.walmart.com/mappings?=null"
_UBER_KEYS_HEADERS = {
    "WM_CONSUMER.ID": "8769b321-1e48-4547-856c-735d93cebf61",
    "WM_SVC.NAME": "UBER-MAPPINGS-READ-NSF",
    "WM_SVC.ENV": "prod",
    "Content-Type": "application/json",
    "wm_svc.version": "0.0.1",
}


class OfferValidatorService:
    """Validates offer unpublish reason codes via IQS and downstream API calls."""

    def __init__(self):
        logger.info("OfferValidatorService initialized")

    async def validate(
        self,
        offer_id: str,
        reason_code: Optional[str] = None,
        skip_publish_check: bool = False,
    ) -> Dict[str, Any]:
        """
        Validate an offer's unpublish reason code(s).

        Args:
            offer_id: The Walmart offer ID to validate.
            reason_code: Specific reason code to check. If empty/None, auto-detects from offer data.
            skip_publish_check: If True, skip the check for whether the offer is currently published.

        Returns:
            Dict containing validation results and offer metadata.
        """
        offer_id = offer_id.strip()
        reason_code = (reason_code or "").strip().upper() or None

        if not offer_id.isalnum():
            return {
                "success": False,
                "offer_id": offer_id,
                "error": (
                    f"'{offer_id}' is not a valid offer ID. "
                    "Offer IDs must be alphanumeric (no spaces, underscores, or special characters)."
                ),
            }

        logger.info(f"OfferValidatorService.validate: offer_id={offer_id}, reason_code={reason_code}")

        try:
            async with httpx.AsyncClient() as client:
                # Fetch OFFER data + CASTAR audit history in parallel
                offer_data, castar_events = await asyncio.gather(
                    self._fetch_iqs(client, offer_id, "OFFER"),
                    self._fetch_castar_history(client, offer_id),
                )
                audit_history = self._build_audit_history_str(castar_events)
                if offer_data is None:
                    return {
                        "success": False,
                        "offer_id": offer_id,
                        "error": f"IQS OFFER fetch failed for offer_id={offer_id}.",
                    }

                if not skip_publish_check:
                    publish_status = self._get_publish_status(offer_data)
                    if publish_status and publish_status.upper() == "PUBLISHED":
                        return {
                            "success": True,
                            "offer_id": offer_id,
                            "publish_status": publish_status,
                            "audit_history": audit_history,
                            "message": "Offer is currently PUBLISHED. No unpublish validation needed.",
                            "results": [],
                        }

                if reason_code:
                    codes_to_check = [reason_code]
                else:
                    codes_to_check = self._extract_reason_codes(offer_data)
                    if not codes_to_check:
                        return {
                            "success": True,
                            "offer_id": offer_id,
                            "publish_status": self._get_publish_status(offer_data),
                            "audit_history": audit_history,
                            "message": "No unpublish reason codes found for this offer.",
                            "results": [],
                        }

                results = await self._run_validators(client, offer_id, codes_to_check, offer_data)

                return {
                    "success": True,
                    "offer_id": offer_id,
                    "publish_status": self._get_publish_status(offer_data),
                    "audit_history": audit_history,
                    "reason_codes_checked": codes_to_check,
                    "results": [r.to_dict() for r in results],
                    "summary": self._build_summary(results),
                }

        except httpx.HTTPStatusError as exc:
            logger.error(f"IQS HTTP error for offer {offer_id}: {exc}")
            return {
                "success": False,
                "offer_id": offer_id,
                "error": f"IQS API returned HTTP {exc.response.status_code}: {exc.response.text[:300]}",
            }
        except Exception as exc:
            logger.exception(f"Unexpected error validating offer {offer_id}")
            return {
                "success": False,
                "offer_id": offer_id,
                "error": str(exc),
            }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _fetch_iqs(
        self, client: httpx.AsyncClient, offer_id: str, resource_type: str
    ) -> Optional[Dict[str, Any]]:
        """Fetch a resource from IQS by offer ID and resource type."""
        params = {"type": "OFFERID", "id": offer_id, "rt": resource_type}
        logger.info(f"IQS fetch: offer_id={offer_id}, rt={resource_type}")
        try:
            response = await client.get(
                _IQS_BASE_URL, headers=_iqs_headers(), params=params, timeout=_DEFAULT_TIMEOUT,
            )
            logger.info(f"IQS {resource_type} response: HTTP {response.status_code} for {offer_id}")
            response.raise_for_status()
            return response.json()
        except RuntimeError as exc:
            logger.error(f"IQS {resource_type} signing failed for {offer_id}: {exc}")
            return None
        except httpx.HTTPStatusError as exc:
            logger.error(
                f"IQS {resource_type} HTTP error {exc.response.status_code} for {offer_id}: "
                f"{exc.response.text[:500]}"
            )
            return None
        except Exception as exc:
            logger.error(f"IQS {resource_type} fetch exception for {offer_id}: {exc}")
            return None

    def _get_publish_status(self, offer_data: dict) -> Optional[str]:
        """Extract offerPublishStatus from IQS OFFER response."""
        try:
            offers = offer_data.get("payload", {}).get("offers", [])
            if offers:
                return offers[0].get("offer", {}).get("offerPublishStatus")
        except Exception:
            pass
        return None

    def _extract_reason_codes(self, offer_data: dict) -> List[str]:
        """Extract unpublish reason codes from IQS OFFER response.

        IQS returns statusChangeReasons as a dict whose keys are the reason codes.
        Special case: {"FORCED": "Unpublished Offer due to OPS_DELETE"} — the key
        is a generic FORCED label but the value identifies OPS_DELETE as the real reason.
        """
        try:
            offers = offer_data.get("payload", {}).get("offers", [])
            if offers:
                reasons = offers[0].get("offer", {}).get("statusChangeReasons", {})
                if isinstance(reasons, dict):
                    codes = []
                    for k, v in reasons.items():
                        if k and isinstance(v, str) and "OPS_DELETE" in v:
                            codes.append("OPS_DELETE")
                        elif k:
                            codes.append(k)
                    return codes
                if isinstance(reasons, list):
                    return [r.get("reasonCode") for r in reasons if r.get("reasonCode")]
        except Exception:
            pass
        return []

    async def _run_validators(
        self,
        client: httpx.AsyncClient,
        offer_id: str,
        reason_codes: List[str],
        offer_data: dict,
    ):
        """Run the appropriate validator for each reason code."""
        _api_cache: Dict[str, Optional[dict]] = {"OFFER": offer_data}

        results = []
        for code in reason_codes:
            entry = get_validator(code)
            if entry is None:
                results.append(validate_unknown_reason(offer_id, code))
                continue

            if code == "BUNDLE_COMPONENTS_UNPUBLISHED":
                results.append(await self._validate_bundle_components(client, offer_id, offer_data))
                continue

            if code in ("PRODUCT_NOT_ACTIVE", "OPS_DELETE", "FORCED"):
                result = await self._validate_product_not_active(client, offer_id)
                result.reason_code = code
                if code == "OPS_DELETE":
                    result.message = result.message.replace(
                        "PRODUCT_NOT_ACTIVE unpublish is correctly applied",
                        "OPS_DELETE unpublish is correctly applied",
                    )
                elif code == "FORCED":
                    result.message = result.message.replace(
                        "PRODUCT_NOT_ACTIVE unpublish is correctly applied",
                        "FORCED unpublish is correctly applied",
                    )
                results.append(result)
                continue

            if code == "GOODS_NOT_FOR_RESALE":
                results.append(await self._validate_goods_not_for_resale(client, offer_id))
                continue

            if code == "NEEDS_INVENTORY":
                results.append(await self._validate_needs_inventory(client, offer_id))
                continue

            if code == "1P_IS_ALCOHOL_BEVERAGE_MISSING":
                results.append(await self._validate_1p_is_alcohol_beverage_missing(
                    client, offer_id, offer_data
                ))
                continue

            if code == "NO_MIN_MAX_PRICE":
                results.append(await self._validate_no_min_max_price(client, offer_id))
                continue

            validator_fn, api_type = entry
            if api_type and api_type not in _api_cache:
                _api_cache[api_type] = await self._fetch_iqs(client, offer_id, api_type)

            api_response = offer_data if api_type is None else (_api_cache.get(api_type) or {})
            try:
                result = validator_fn(offer_id, api_response)
            except Exception as exc:
                logger.error(f"Validator {code} raised exception: {exc}")
                result = ValidationResult(
                    offer_id=offer_id,
                    reason_code=code,
                    status=ValidationStatus.NEEDS_MANUAL_REVIEW,
                    message=f"Validator error: {exc}",
                    details={},
                )
            results.append(result)

        return results

    async def _validate_bundle_components(
        self,
        client: httpx.AsyncClient,
        offer_id: str,
        offer_data: dict,
    ) -> ValidationResult:
        """Multi-step BUNDLE_COMPONENTS_UNPUBLISHED validation.

        Step 1 – IQS PRODUCT rt: confirm offer is BUNDLE and get productId.
        Step 2 – Uber Keys BUNDLE_TO_COMPONENT: resolve component product IDs.
        Step 3 – IQS uber/v1 WPID rt: fetch each component offer, match by sellerId.
        Step 4/5 – If any matched component is UNPUBLISHED → Valid; all PUBLISHED → Invalid.
        """
        from packs.offer_intelligence.offer_validators import validate_bundle_components_unpublished

        logger.info(f"Bundle Step 1: IQS PRODUCT fetch for {offer_id}")
        product_data = await self._fetch_iqs(client, offer_id, "PRODUCT")
        bundle_context = {
            "offer_id": offer_id,
            "product_data": product_data or {},
            "component_offers": [],
            "steps": [],
        }

        if not product_data:
            bundle_context["steps"].append("Step 1 FAILED: could not fetch IQS PRODUCT data")
            return validate_bundle_components_unpublished(offer_id, bundle_context)

        product_class_type = (
            product_data.get("payload", {}).get("product", {}).get("meta", {}).get("product_class_type")
        )
        bundle_product_id = product_data.get("payload", {}).get("productId")
        bundle_context["product_class_type"] = product_class_type
        bundle_context["bundle_product_id"] = bundle_product_id
        bundle_context["steps"].append(
            f"Step 1 OK: product_class_type={product_class_type}, productId={bundle_product_id}"
        )

        if product_class_type != "BUNDLE" or not bundle_product_id:
            bundle_context["steps"].append(
                f"Step 1: offer is not a BUNDLE (product_class_type={product_class_type})"
            )
            return validate_bundle_components_unpublished(offer_id, bundle_context)

        # Step 2: Uber Keys BUNDLE_TO_COMPONENT
        logger.info(f"Bundle Step 2: Uber Keys BUNDLE_TO_COMPONENT for productId={bundle_product_id}")
        component_product_ids: List[str] = []
        try:
            payload = [{"request_id": "1", "key": bundle_product_id, "type": "BUNDLE_TO_COMPONENT"}]
            r = await client.post(
                _UBER_KEYS_BASE_URL, headers=_UBER_KEYS_HEADERS, json=payload, timeout=_DEFAULT_TIMEOUT,
            )
            data = r.json()
            component_product_ids = (
                data[0].get("response", {}).get("data", {}).get("values", []) if data else []
            )
            bundle_context["steps"].append(
                f"Step 2 OK: Uber Keys returned {len(component_product_ids)} component product ID(s): {component_product_ids}"
            )
        except Exception as exc:
            bundle_context["steps"].append(f"Step 2 FAILED: Uber Keys error: {exc}")
            logger.error(f"Bundle Step 2 Uber Keys error: {exc}")
            return validate_bundle_components_unpublished(offer_id, bundle_context)

        if not component_product_ids:
            bundle_context["steps"].append("Step 2: no component product IDs returned by Uber Keys")
            return validate_bundle_components_unpublished(offer_id, bundle_context)

        # Step 3: IQS uber/v1 WPID — fetch offer for each component
        component_offers: List[Dict[str, Any]] = []
        for comp_product_id in component_product_ids:
            logger.info(f"Bundle Step 3: IQS WPID lookup for component productId={comp_product_id}")
            try:
                r = await client.get(
                    _IQS_UBER_URL,
                    headers=_iqs_headers(),
                    params={"type": "WPID", "id": comp_product_id, "rt": "OFFER"},
                    timeout=_DEFAULT_TIMEOUT,
                )
                comp_offers = r.json().get("payload", {}).get("offers", [])
                matched = next(
                    (
                        o.get("offer", {})
                        for o in comp_offers
                        if o.get("offer", {}).get("sellerId") == _WALMART_1P_SELLER_ID
                    ),
                    None,
                )
                if matched:
                    comp_info = {
                        "componentProductId": comp_product_id,
                        "offerId": matched.get("offerId"),
                        "productId": matched.get("productId"),
                        "offerPublishStatus": matched.get("offerPublishStatus"),
                        "statusChangeReasons": list((matched.get("statusChangeReasons") or {}).keys()),
                    }
                    component_offers.append(comp_info)
                else:
                    component_offers.append({
                        "componentProductId": comp_product_id,
                        "offerId": None,
                        "offerPublishStatus": None,
                        "statusChangeReasons": [],
                        "note": "No 1P seller offer found",
                    })
            except Exception as exc:
                logger.error(f"Bundle Step 3 WPID fetch error for {comp_product_id}: {exc}")
                component_offers.append({
                    "componentProductId": comp_product_id,
                    "offerId": None,
                    "offerPublishStatus": None,
                    "statusChangeReasons": [],
                    "note": f"Fetch error: {exc}",
                })

        bundle_context["component_offers"] = component_offers
        bundle_context["steps"].append(f"Step 3 OK: fetched {len(component_offers)} component offer(s)")
        return validate_bundle_components_unpublished(offer_id, bundle_context)

    async def _validate_product_not_active(
        self,
        client: httpx.AsyncClient,
        offer_id: str,
    ) -> ValidationResult:
        """Multi-step PRODUCT_NOT_ACTIVE validation.

        Step 1 – Offer Store /offer/{id}: get GTIN from offerIdentifiers.
        Step 2 – Product Matching API: get WID (wpid) for the GTIN.
        Step 3 – Product Store API: check if GTIN is present in the product payload.
        Step 4 – Uber Keys GTIN_TO_DOTCOM_OFFER_ID: check if GTIN still maps to this offer.
        """
        from packs.offer_intelligence.offer_validators import validate_product_not_active

        _OFFER_STORE_HEADERS = {
            "Accept": "application/json",
            "WM_MART_ID": "0",
            "WM_SVC.VERSION": "2.0",
            "WM_VERTICAL_ID": "0",
            "WM_CONSUMER.ID": _OFFER_STORE_CONSUMER_ID,
            "WM_SVC.NAME": "transone-offer-validator",
            "WM_SVC.ENV": "prod",
            "WM_QOS.CORRELATION_ID": "transone-pna-validation",
        }
        _PRODUCT_MATCHING_HEADERS = {
            "WM_CONSUMER.ID": "a585194d-f948-4e22-b8ec-265932d09cac",
            "WM_SVC.NAME": "CPS-PRODUCT-MATCHING-LOOKUP-API",
            "WM_SVC.ENV": "PROD",
        }
        _PRODUCT_STORE_HEADERS = {
            "Content-Type": "application/json",
            "accept-language": "es-US",
            "response_groups": "item.VARIANT_SUMMARY,item.GROUP_ASSOCIATION",
            "x-o-bu": "WALMART-US",
        }

        pna_context: Dict[str, Any] = {
            "gtin": None, "wid": None,
            "gtin_in_product": None, "uber_keys_offer_id": None, "steps": [],
        }

        # Step 1: Offer Store — get GTIN
        offer_store_url = f"{_OFFER_STORE_BASE_URL}/offer/{offer_id}"
        logger.info(f"PNA Step 1: Offer Store fetch for {offer_id}")
        try:
            r = await client.get(offer_store_url, headers=_OFFER_STORE_HEADERS, timeout=_DEFAULT_TIMEOUT)
            logger.info(f"PNA Step 1: Offer Store HTTP {r.status_code}")
            r.raise_for_status()
            os_data = r.json()
            identifiers = os_data.get("payload", {}).get("offerIdentifiers", [])
            gtin = next(
                (entry.get("keyValue") for entry in identifiers if entry.get("keyName") == "GTIN"),
                None,
            )
            pna_context["gtin"] = gtin
            pna_context["steps"].append(f"Step 1 OK: offerIdentifiers={identifiers}; GTIN={gtin}")
            logger.info(f"PNA Step 1: GTIN={gtin}")
        except Exception as exc:
            pna_context["steps"].append(f"Step 1 FAILED: Offer Store error: {exc}")
            logger.error(f"PNA Step 1 Offer Store error: {exc}")
            return validate_product_not_active(offer_id, pna_context)

        if not pna_context["gtin"]:
            pna_context["steps"].append("Step 1: GTIN not found in offerIdentifiers")
            return validate_product_not_active(offer_id, pna_context)

        gtin = pna_context["gtin"]

        # Step 2: Product Matching — resolve GTIN → WID
        logger.info(f"PNA Step 2: Product Matching for GTIN={gtin}")
        try:
            r = await client.get(
                _PRODUCT_MATCHING_BASE_URL,
                headers=_PRODUCT_MATCHING_HEADERS,
                params={"id": gtin, "type": "gtin", "tenantId": "0", "getAllStrongKeys": "true"},
                timeout=_DEFAULT_TIMEOUT,
            )
            logger.info(f"PNA Step 2: Product Matching HTTP {r.status_code}")
            r.raise_for_status()
            pm_data = r.json()
            wid = pm_data[0].get("wpid") if pm_data else None
            pna_context["wid"] = wid
            pna_context["steps"].append(f"Step 2 OK: Product Matching WID={wid}")
            logger.info(f"PNA Step 2: WID={wid}")
        except Exception as exc:
            pna_context["steps"].append(f"Step 2 FAILED: Product Matching error: {exc}")
            logger.error(f"PNA Step 2 Product Matching error: {exc}")
            return validate_product_not_active(offer_id, pna_context)

        if not pna_context["wid"]:
            pna_context["steps"].append(
                "Step 2: no WID returned by Product Matching – cannot validate; needs manual review"
            )
            return validate_product_not_active(offer_id, pna_context)

        wid = pna_context["wid"]

        # Step 3: Product Store — check GTIN presence
        logger.info(f"PNA Step 3: Product Store for WID={wid}")
        try:
            r = await client.post(
                _PRODUCT_STORE_READ_BASE_URL,
                headers=_PRODUCT_STORE_HEADERS,
                json=[{"productId": wid}],
                timeout=_DEFAULT_TIMEOUT,
            )
            logger.info(f"PNA Step 3: Product Store HTTP {r.status_code}")
            r.raise_for_status()
            ps_data = r.json()
            product_entry = (ps_data.get("payload") or [{}])[0]
            primary_gtin = product_entry.get("productIdentifiers", {}).get("GTIN")
            alt_gtins_raw = product_entry.get("productAttributes", {}).get("alternateGTINs") or {}
            if isinstance(alt_gtins_raw, dict):
                alt_gtins = [e.get("value") for e in alt_gtins_raw.get("values", []) if e.get("value")]
            elif isinstance(alt_gtins_raw, list):
                alt_gtins = [e if isinstance(e, str) else e.get("value") for e in alt_gtins_raw if e]
            else:
                alt_gtins = []
            all_gtins = [g for g in ([primary_gtin] + alt_gtins) if g]
            gtin_in_product = gtin in all_gtins
            pna_context["gtin_in_product"] = gtin_in_product
            pna_context["steps"].append(
                f"Step 3 OK: Product Store primaryGTIN={primary_gtin}, "
                f"alternateGTINs={alt_gtins}; GTIN {gtin!r} found={gtin_in_product}"
            )
            logger.info(f"PNA Step 3: GTIN found in product={gtin_in_product}")
        except Exception as exc:
            pna_context["steps"].append(f"Step 3 FAILED: Product Store error: {exc}")
            logger.error(f"PNA Step 3 Product Store error: {exc}")
            return validate_product_not_active(offer_id, pna_context)

        # Step 4: Uber Keys GTIN_TO_DOTCOM_OFFER_ID
        logger.info(f"PNA Step 4: Uber Keys GTIN_TO_DOTCOM_OFFER_ID for GTIN={gtin}")
        try:
            payload = [{"request_id": "1", "key": gtin, "type": "GTIN_TO_DOTCOM_OFFER_ID"}]
            r = await client.post(
                _UBER_KEYS_BASE_URL, headers=_UBER_KEYS_HEADERS, json=payload, timeout=_DEFAULT_TIMEOUT,
            )
            logger.info(f"PNA Step 4: Uber Keys HTTP {r.status_code}")
            uk_data = r.json()
            uber_offer_ids: List[str] = (
                uk_data[0].get("response", {}).get("data", {}).get("values", []) if uk_data else []
            )
            uber_keys_offer_id = uber_offer_ids[0] if uber_offer_ids else ""
            pna_context["uber_keys_offer_id"] = uber_keys_offer_id
            pna_context["uber_keys_offer_ids"] = uber_offer_ids
            same_offer = uber_keys_offer_id == offer_id if uber_keys_offer_id else False
            pna_context["steps"].append(
                f"Step 4 OK: Uber Keys GTIN→offerIds={uber_offer_ids}; "
                f"mapsToSameOffer={same_offer}"
            )
            logger.info(f"PNA Step 4: Uber Keys offer IDs={uber_offer_ids}")
        except Exception as exc:
            pna_context["steps"].append(f"Step 4 FAILED: Uber Keys error: {exc}")
            logger.error(f"PNA Step 4 Uber Keys error: {exc}")
            return validate_product_not_active(offer_id, pna_context)

        return validate_product_not_active(offer_id, pna_context)

    async def _fetch_oasis_national(self, client: httpx.AsyncClient, offer_id: str) -> Optional[str]:
        """Fetch sellableNational inventory from Oasis API."""
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "WM_BU_ID": "WMT",
            "WM_CONSUMER.COUNTRY_CODE": "US",
            "WM_CONSUMER.ID": _OASIS_CONSUMER_ID,
            "WM_CONSUMER.INTIMESTAMP": "1636422761054",
            "WM_QOS.CORRELATION_ID": "transone-needs-inventory-validation",
            "WM_SEC.KEY_VERSION": "2",
            "WM_SVC.ENV": "prod",
            "WM_SVC.NAME": "GLASS-AVAILABILITY-SERVICE",
            "WM_SVC.VERSION": "1.0.0",
            "cache-control": "no-cache",
        }
        body = {
            "payload": [{
                "offerId": str(offer_id),
                "sellerId": "",
                "nodeGroups": [],
                "nodes": [],
                "preferredStores": [],
            }],
        }
        try:
            response = await client.post(
                _OASIS_BASE_URL, headers=headers, json=body, timeout=_DEFAULT_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
            payload_data = data.get("payload", [{}])[0] if data.get("payload") else {}
            return str(payload_data.get("sellableNational", "NA"))
        except Exception as exc:
            logger.error(f"Oasis fetch error for {offer_id}: {exc}")
            return None

    async def _fetch_castar_history(
        self, client: httpx.AsyncClient, offer_id: str, interval: str = "-P30D"
    ) -> Optional[list]:
        """Fetch audit event history from CASTAR for an offer."""
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "WM_SVC.NAME": "CASTAR",
            "WM_SVC.ENV": "prod",
            "WM_CONSUMER.ID": _CASTAR_CONSUMER_ID,
        }
        body = {
            "id": offer_id,
            "type": "OFFER",
            "interval": interval,
            "fetchSize": 2000,
            "ordering": "DESC",
            "allowUnconfiguredTags": True,
        }
        try:
            response = await client.post(
                _CASTAR_BASE_URL, headers=headers, json=body, timeout=_DEFAULT_TIMEOUT,
            )
            logger.info(f"CASTAR response: HTTP {response.status_code} for {offer_id}")
            response.raise_for_status()
            events = response.json().get("events", [])
            logger.info(f"CASTAR events returned: {len(events)} for {offer_id}")
            return events
        except Exception as exc:
            logger.error(f"CASTAR fetch error for {offer_id}: {exc}")
            return None

    def _build_audit_history_str(self, castar_events: Optional[list]) -> str:
        """Build an audit history string from CASTAR events (PUBLISHED→UNPUBLISHED transition)."""
        if castar_events is None:
            return "offerPublishStatus : PUBLISHED -> UNPUBLISHED - CASTAR fetch failed"

        publish_transitions: list = []
        for event in castar_events:
            for change in event.get("changes", []):
                previous = (change.get("previous") or "").strip('"')
                current = (change.get("current") or "").strip('"')
                if (
                    change.get("name") == "GM.offerPublishStatus"
                    and previous == "PUBLISHED"
                    and current == "UNPUBLISHED"
                ):
                    publish_transitions.append({
                        "from": "PUBLISHED",
                        "to": "UNPUBLISHED",
                        "changedOn": event.get("time", ""),
                    })
        if publish_transitions:
            t = publish_transitions[0]
            return f"offerPublishStatus : {t['from']} -> {t['to']} on {t['changedOn']}"
        return "offerPublishStatus : PUBLISHED -> UNPUBLISHED - No changes in Last 30 Days"

    async def _validate_no_min_max_price(
        self,
        client: httpx.AsyncClient,
        offer_id: str,
    ) -> ValidationResult:
        """Validate NO_MIN_MAX_PRICE: gift card type check (PRODUCT) then min/max price check (PRICE)."""
        from packs.offer_intelligence.offer_validators import validate_no_min_max_price
        from packs.offer_intelligence.json_path import get_nested_value

        logger.info(f"NO_MIN_MAX_PRICE Step 1: IQS PRODUCT fetch for {offer_id}")
        product_data = await self._fetch_iqs(client, offer_id, "PRODUCT")

        context: dict = {"product_data": product_data or {}}

        gc_type_raw = get_nested_value(
            product_data or {},
            "x.payload.product.product_attributes.gift_card_type_code.values[0].value",
        )
        try:
            gc_type_val = int(gc_type_raw) if gc_type_raw is not None else None
        except (ValueError, TypeError):
            gc_type_val = None

        if gc_type_val == 2:
            logger.info(f"NO_MIN_MAX_PRICE Step 2: gift_card_type_code=2, fetching IQS PRICE for {offer_id}")
            price_data = await self._fetch_iqs(client, offer_id, "PRICE")
            context["price_data"] = price_data or {}
        else:
            context["price_data"] = {}

        return validate_no_min_max_price(offer_id, context)

    async def _validate_goods_not_for_resale(
        self,
        client: httpx.AsyncClient,
        offer_id: str,
    ) -> ValidationResult:
        """Validate GOODS_NOT_FOR_RESALE using IQS SI (Supply Item) data."""
        from packs.offer_intelligence.offer_validators import validate_goods_not_for_resale

        logger.info(f"GNFR: IQS SI fetch for {offer_id}")
        si_data = await self._fetch_iqs(client, offer_id, "SI")

        context: Dict[str, Any] = {
            "item_state_code": None,
            "buying_region_codes": [],
            "replenish_sub_type_codes": [],
            "unit_cost_amts": [],
            "assortment_type_codes": [],
            "supplier_nbrs": [],
            "accounting_dept_nbrs": [],
            "steps": [],
        }

        if not si_data:
            context["steps"].append("Step 1 FAILED: could not fetch IQS SI data")
            return validate_goods_not_for_resale(offer_id, context)

        supply_items = (si_data.get("payload") or {}).get("supplyTradeItems", [])
        if not supply_items:
            context["steps"].append("Step 1 OK: IQS SI returned no supplyTradeItems")
            return validate_goods_not_for_resale(offer_id, context)

        context["steps"].append(f"Step 1 OK: {len(supply_items)} supplyTradeItem(s) found")

        def _int_list(key: str) -> List[int]:
            result = []
            for item in supply_items:
                try:
                    result.append(int(item["payloadJson"]["attributes"][key]))
                except (KeyError, TypeError, ValueError):
                    pass
            return result

        def _float_list(key: str) -> List[float]:
            result = []
            for item in supply_items:
                try:
                    result.append(float(item["payloadJson"]["attributes"][key]))
                except (KeyError, TypeError, ValueError):
                    pass
            return result

        item_state_code = None
        for item in supply_items:
            try:
                raw_isc = item["payloadJson"]["attributes"]["itemStateCode"]
                if isinstance(raw_isc, list):
                    item_state_code = raw_isc[0] if raw_isc else None
                else:
                    item_state_code = str(raw_isc)
                break
            except (KeyError, TypeError, IndexError):
                pass

        context["item_state_code"] = item_state_code
        context["buying_region_codes"] = _int_list("buyingRegionCode")
        context["replenish_sub_type_codes"] = _int_list("replenishSubTypeCode")
        context["unit_cost_amts"] = _float_list("unitCostAmt")
        context["assortment_type_codes"] = _int_list("assortmentTypeCode")
        context["supplier_nbrs"] = _int_list("supplierNbr")
        context["accounting_dept_nbrs"] = _int_list("accountingDeptNbr")
        context["steps"].append(
            f"Step 2 OK: itemStateCode={item_state_code}, "
            f"buyingRegionCodes={context['buying_region_codes']}, "
            f"replenishSubTypeCodes={context['replenish_sub_type_codes']}"
        )
        logger.info(f"GNFR: itemStateCode={item_state_code} for {offer_id}")

        return validate_goods_not_for_resale(offer_id, context)

    async def _validate_needs_inventory(
        self,
        client: httpx.AsyncClient,
        offer_id: str,
    ) -> ValidationResult:
        """Validate NEEDS_INVENTORY using Oasis sellableNational inventory."""
        from packs.offer_intelligence.offer_validators import validate_needs_inventory

        raw = await self._fetch_oasis_national(client, offer_id)
        api_response: Dict[str, Any] = {"_inventory_raw": raw}
        if raw is not None:
            try:
                api_response["_inventory_quantity"] = int(float(raw))
            except (ValueError, TypeError):
                api_response["_inventory_quantity"] = None
        else:
            api_response["_inventory_quantity"] = None

        return validate_needs_inventory(offer_id, api_response)

    async def _validate_1p_is_alcohol_beverage_missing(
        self,
        client: httpx.AsyncClient,
        offer_id: str,
        offer_data: dict,
    ) -> ValidationResult:
        """Multi-step 1P_IS_ALCOHOL_BEVERAGE_MISSING validation."""
        from packs.offer_intelligence.offer_validators import validate_1p_is_alcohol_beverage_missing
        from packs.offer_intelligence.json_path import get_nested_value
        from datetime import datetime, timezone

        context: Dict[str, Any] = {
            "seller_id": None,
            "is_alcoholic_beverage": None,
            "created_dtm": None,
            "steps": [],
        }

        seller_id = get_nested_value(offer_data, "x.payload.offers[0].offer.sellerId")
        context["seller_id"] = seller_id
        logger.info(f"ALCOHOL Step 1: offer_id={offer_id}, sellerId={seller_id}")

        if seller_id != _WALMART_1P_SELLER_ID:
            context["steps"].append(
                f"Step 1: sellerId='{seller_id}' is not the Walmart 1P dotcom seller – validation stops."
            )
            return validate_1p_is_alcohol_beverage_missing(offer_id, context)

        context["steps"].append(f"Step 1 OK: sellerId='{seller_id}' confirmed as Walmart 1P dotcom offer.")

        logger.info(f"ALCOHOL Step 2: IQS PRODUCT fetch for {offer_id}")
        product_data = await self._fetch_iqs(client, offer_id, "PRODUCT")
        is_alcoholic_beverage = get_nested_value(
            product_data or {},
            "x.payload.product.derived_attributes.is_alcoholic_beverage.values[0].value",
        )
        context["is_alcoholic_beverage"] = is_alcoholic_beverage
        context["steps"].append(
            f"Step 2 OK: IQS PRODUCT derived_attributes.is_alcoholic_beverage='{is_alcoholic_beverage}'."
        )
        logger.info(f"ALCOHOL Step 2: is_alcoholic_beverage={is_alcoholic_beverage}")

        if is_alcoholic_beverage is not None:
            return validate_1p_is_alcohol_beverage_missing(offer_id, context)

        raw_created = get_nested_value(offer_data, "x.payload.offers[0].offer.createdDtm")
        created_dtm = None
        if raw_created is not None:
            try:
                ts = float(raw_created)
                if ts > 1e10:
                    ts /= 1000
                created_dtm = datetime.fromtimestamp(ts, tz=timezone.utc)
            except (ValueError, TypeError):
                for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ",
                            "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z"):
                    try:
                        created_dtm = datetime.strptime(str(raw_created), fmt)
                        if created_dtm.tzinfo is None:
                            created_dtm = created_dtm.replace(tzinfo=timezone.utc)
                        break
                    except ValueError:
                        continue
        context["created_dtm"] = created_dtm
        context["steps"].append(f"Step 3: createdDtm='{raw_created}' parsed as '{created_dtm}'.")
        logger.info(f"ALCOHOL Step 3: createdDtm={created_dtm}")

        return validate_1p_is_alcohol_beverage_missing(offer_id, context)

    def _build_summary(self, results) -> Dict[str, Any]:
        """Build a summary dict from a list of ValidationResult objects."""
        counts: Dict[str, int] = {}
        for r in results:
            label = r.status.value
            counts[label] = counts.get(label, 0) + 1
        return {"total": len(results), "by_status": counts}


# ---------------------------------------------------------------------------
# Tool entry point — called by the framework via python_function tool type
# ---------------------------------------------------------------------------

async def validate_offer(offer_id: str, reason_code: str = "") -> dict:
    """Entry point for the DIAG-VALIDATE-OFFER-01 tool.

    Args:
        offer_id: 32-character alphanumeric Walmart offer ID.
        reason_code: Optional specific reason code to validate.
                     If empty, all reason codes on the offer are checked.

    Returns:
        Dict with success flag, publish status, audit history, per-reason
        validation results, and a summary.
    """
    service = OfferValidatorService()
    return await service.validate(offer_id, reason_code or None)
