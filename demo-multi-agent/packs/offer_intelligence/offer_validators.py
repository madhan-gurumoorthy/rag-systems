"""
Offer unpublish reason code validators.

All validation business logic lives here — one function per reason code.
Supported reason codes and their IQS resource types are declared in VALIDATOR_REGISTRY.
"""
import re
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from packs.offer_intelligence.json_path import get_nested_value
from packs.offer_intelligence.result import ValidationResult, ValidationStatus


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_DATE_FORMATS = [
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%d",
]


def _parse_date(value) -> Optional[datetime]:
    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 1e10:
            ts /= 1000
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    str_value = str(value).strip()
    if str_value.isdigit():
        ts = float(str_value)
        if ts > 1e10:
            ts /= 1000
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(str_value, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


def _get(data: dict, path: str) -> Any:
    return get_nested_value(data, path)


def _valid(offer_id: str, reason_code: str, message: str, details: Optional[dict] = None) -> ValidationResult:
    return ValidationResult(
        offer_id=offer_id, reason_code=reason_code,
        status=ValidationStatus.VALID, message=message, details=details or {},
    )


def _invalid(offer_id: str, reason_code: str, message: str, details: Optional[dict] = None) -> ValidationResult:
    return ValidationResult(
        offer_id=offer_id, reason_code=reason_code,
        status=ValidationStatus.INVALID, message=message, details=details or {},
    )


def _manual_review(offer_id: str, reason_code: str, message: str) -> ValidationResult:
    return ValidationResult(
        offer_id=offer_id, reason_code=reason_code,
        status=ValidationStatus.NEEDS_MANUAL_REVIEW, message=message, details={},
    )


# ---------------------------------------------------------------------------
# Reason code validators — one function per reason code
# ---------------------------------------------------------------------------

def validate_end_date(offer_id: str, api_response: dict) -> ValidationResult:
    """END_DATE: VALID if endDate is present and in the past."""
    path = "x.payload.offers[0].offer.endDate"
    raw = _get(api_response, path)
    if raw is None:
        return _invalid(offer_id, "END_DATE",
            "endDate is null or missing – no end date set; END_DATE unpublish is not justified.",
            {"endDate": None, "path": path})
    end_date = _parse_date(raw)
    if end_date is None:
        return _invalid(offer_id, "END_DATE",
            f"Could not parse endDate '{raw}' – unrecognised date format.",
            {"endDate": raw, "path": path})
    now = datetime.now(timezone.utc)
    utc_str = end_date.strftime("%Y-%m-%dT%H:%M:%SZ")
    if end_date < now:
        return _valid(offer_id, "END_DATE",
            f"End date '{utc_str}' is in the past – END_DATE unpublish is correctly applied.",
            {"endDate": utc_str, "endDateParsed": end_date.isoformat(), "evaluatedAt": now.isoformat()})
    return _invalid(offer_id, "END_DATE",
        f"End date '{utc_str}' is in the future – offer is wrongly unpublished.",
        {"endDate": utc_str, "endDateParsed": end_date.isoformat(), "evaluatedAt": now.isoformat()})


def validate_start_date(offer_id: str, api_response: dict) -> ValidationResult:
    """START_DATE: VALID if startDate is present and in the future (not yet reached)."""
    path = "x.payload.offers[0].offer.startDate"
    raw = _get(api_response, path)
    if raw is None:
        return _invalid(offer_id, "START_DATE",
            "startDate is null or missing – START_DATE unpublish is not justified.",
            {"startDate": None, "path": path})
    start_date = _parse_date(raw)
    if start_date is None:
        return _invalid(offer_id, "START_DATE",
            f"Could not parse startDate '{raw}' – unrecognised date format.",
            {"startDate": raw, "path": path})
    now = datetime.now(timezone.utc)
    utc_str = start_date.strftime("%Y-%m-%dT%H:%M:%SZ")
    if start_date > now:
        return _valid(offer_id, "START_DATE",
            f"Start date '{utc_str}' is in the future – START_DATE unpublish is correctly applied.",
            {"startDate": utc_str, "startDateParsed": start_date.isoformat(), "evaluatedAt": now.isoformat()})
    return _invalid(offer_id, "START_DATE",
        f"Start date '{utc_str}' is in the past – offer should be PUBLISHED but is unpublished.",
        {"startDate": utc_str, "startDateParsed": start_date.isoformat(), "evaluatedAt": now.isoformat()})


def validate_no_price(offer_id: str, api_response: dict) -> ValidationResult:
    """NO_PRICE: VALID if currencyAmount is null/missing."""
    path = (
        "x.payload.offers[0].pricing.offerPricingList[0]"
        ".storefrontPricingList[0].currentPrice.currentValue.currencyAmount"
    )
    amount = _get(api_response, path)
    if amount is None:
        return _valid(offer_id, "NO_PRICE",
            "currencyAmount is null – no price found; NO_PRICE unpublish is correctly applied.",
            {"currencyAmount": None, "path": path})
    return _invalid(offer_id, "NO_PRICE",
        f"currencyAmount is '{amount}' – price is present; offer is wrongly unpublished.",
        {"currencyAmount": amount, "path": path})


def validate_no_logistics_data(offer_id: str, api_response: dict) -> ValidationResult:
    """NO_LOGISTICS_DATA: VALID if offerShipNodes is null/missing/empty."""
    path = "x.payload.offers[0].limo.logisticsOffer.offerShipNodes"
    ship_nodes = _get(api_response, path)
    if not ship_nodes:
        return _valid(offer_id, "NO_LOGISTICS_DATA",
            "offerShipNodes is null or missing – NO_LOGISTICS_DATA unpublish is correctly applied.",
            {"offerShipNodes": ship_nodes, "path": path})
    return _invalid(offer_id, "NO_LOGISTICS_DATA",
        "offerShipNodes has data – logistics data is present; offer is wrongly unpublished.",
        {"offerShipNodes": ship_nodes, "path": path})


def validate_no_active_distr(offer_id: str, api_response: dict) -> ValidationResult:
    """NO_ACTIVE_DISTR: VALID if no ship node has offerShipNodeStatus == 'ACTIVE'."""
    path = "x.payload.offers[0].limo.logisticsOffer.offerShipNodes"
    ship_nodes = _get(api_response, path)
    if not ship_nodes or not isinstance(ship_nodes, list):
        return _valid(offer_id, "NO_ACTIVE_DISTR",
            "offerShipNodes is null – no distributor data; NO_ACTIVE_DISTR unpublish is correctly applied.",
            {"offerShipNodes": None, "path": path})
    active = [n for n in ship_nodes if isinstance(n, dict) and n.get("offerShipNodeStatus") == "ACTIVE"]
    if active:
        return _invalid(offer_id, "NO_ACTIVE_DISTR",
            f"{len(active)} active ship node(s) found – active distributor present; offer is wrongly unpublished.",
            {"activeShipNodeCount": len(active), "totalShipNodeCount": len(ship_nodes), "path": path})
    return _valid(offer_id, "NO_ACTIVE_DISTR",
        f"No active ship nodes across {len(ship_nodes)} node(s) – NO_ACTIVE_DISTR correctly applied.",
        {"activeShipNodeCount": 0, "totalShipNodeCount": len(ship_nodes), "path": path})


def validate_missing_dims(offer_id: str, api_response: dict) -> ValidationResult:
    """MISSING_DIMS: VALID if any of Length/Height/Width/Weight is null."""
    base = "x.payload.offers[0].limo.logisticsOffer.productPackageDimensions[0]"
    fields = ["unitLength", "unitHeight", "unitWidth", "unitWeight"]
    values = {f: _get(api_response, f"{base}.{f}") for f in fields}
    missing = [f for f, v in values.items() if v is None]
    if missing:
        return _valid(offer_id, "MISSING_DIMS",
            f"Missing dimension(s): {', '.join(missing)} – MISSING_DIMS unpublish is correctly applied.",
            {"dimensions": values, "missingFields": missing, "basePath": base})
    return _invalid(offer_id, "MISSING_DIMS",
        "All dimensions (length, height, width, weight) are present – offer is wrongly unpublished.",
        {"dimensions": values, "basePath": base})


def validate_product_name_missing(offer_id: str, api_response: dict) -> ValidationResult:
    """PRODUCT_NAME_MISSING: VALID if product_name is null/missing."""
    path = "x.payload.product.product_attributes.product_name.values[0].value"
    name = _get(api_response, path)
    if name is None:
        return _valid(offer_id, "PRODUCT_NAME_MISSING",
            "product_name is null – PRODUCT_NAME_MISSING unpublish is correctly applied.",
            {"productName": None, "path": path})
    return _invalid(offer_id, "PRODUCT_NAME_MISSING",
        f"product_name is '{name}' – product name is present; offer is wrongly unpublished.",
        {"productName": name, "path": path})


def validate_primary_image_missing(offer_id: str, api_response: dict) -> ValidationResult:
    """PRIMARY_IMAGE_MISSING: VALID if no asset with assetType == 'PRIMARY' found."""
    path = "x.payload.product.assets.values"
    assets = _get(api_response, path)
    if not assets or not isinstance(assets, list):
        return _valid(offer_id, "PRIMARY_IMAGE_MISSING",
            "No product assets found – PRIMARY_IMAGE_MISSING unpublish is correctly applied.",
            {"assetsFound": 0, "path": path})
    primary = [
        a for a in assets
        if isinstance(a, dict)
        and isinstance(a.get("properties"), dict)
        and a["properties"].get("assetType") == "PRIMARY"
    ]
    if primary:
        return _invalid(offer_id, "PRIMARY_IMAGE_MISSING",
            f"{len(primary)} PRIMARY image(s) found – primary image present; offer is wrongly unpublished.",
            {"primaryAssetCount": len(primary), "totalAssetCount": len(assets), "path": path})
    return _valid(offer_id, "PRIMARY_IMAGE_MISSING",
        f"No PRIMARY assetType across {len(assets)} asset(s) – PRIMARY_IMAGE_MISSING correctly applied.",
        {"primaryAssetCount": 0, "totalAssetCount": len(assets), "path": path})


_GUNS_PATTERNS: List[Tuple[str, bool]] = [
    ("48:", True),
    ("9:993:2286:", True),
    ("9:993:11327:4928:", True),
    ("9:4215:9286:21023:1004", False),
]


def validate_1p_compliance_guns(offer_id: str, api_response: dict) -> ValidationResult:
    """1P_COMPLIANCE_GUNS: VALID if any HAT path_id matches a guns/firearms pattern."""
    path = "x.payload.product.derived_attributes.hat.values"
    hat_values = _get(api_response, path)
    if not hat_values or not isinstance(hat_values, list):
        return _invalid(offer_id, "1P_COMPLIANCE_GUNS",
            "No HAT path_id data – cannot confirm guns category; may be wrongly unpublished.",
            {"hatValuesFound": 0, "path": path})
    path_ids = [e.get("path_id") for e in hat_values if isinstance(e, dict) and e.get("path_id")]
    matching = [
        pid for pid in path_ids
        if any(pid.startswith(p) if is_pfx else pid == p for p, is_pfx in _GUNS_PATTERNS)
    ]
    if matching:
        return _valid(offer_id, "1P_COMPLIANCE_GUNS",
            f"HAT path_id {matching[0]!r} matches a guns/firearms pattern – 1P_COMPLIANCE_GUNS correctly applied.",
            {"matchingPathIds": matching, "allPathIds": path_ids, "path": path})
    return _invalid(offer_id, "1P_COMPLIANCE_GUNS",
        "No HAT path_id matches any guns/firearms pattern – offer is wrongly unpublished.",
        {"matchingPathIds": [], "allPathIds": path_ids, "path": path})


def validate_unassigned_tax_code(offer_id: str, api_response: dict) -> ValidationResult:
    """UNASSIGNED_TAX_CODE: VALID if globalTaxCode is null/missing."""
    path = "x.payload.offers[0].offer.globalTaxCode"
    tax_code = _get(api_response, path)
    if tax_code is None:
        return _valid(offer_id, "UNASSIGNED_TAX_CODE",
            "globalTaxCode is null – no tax code assigned; UNASSIGNED_TAX_CODE correctly applied.",
            {"globalTaxCode": None, "path": path})
    return _invalid(offer_id, "UNASSIGNED_TAX_CODE",
        f"globalTaxCode is '{tax_code}' – tax code is assigned; offer is wrongly unpublished.",
        {"globalTaxCode": tax_code, "path": path})


def validate_bundle_components_unpublished(offer_id: str, api_response: dict) -> ValidationResult:
    """BUNDLE_COMPONENTS_UNPUBLISHED: 5-step validation via IQS + Uber Keys.

    api_response is a bundle_context dict built by OfferValidatorService:
      {
        product_class_type: str,       # from IQS PRODUCT rt
        bundle_product_id: str,        # from IQS PRODUCT rt
        component_offers: [            # from IQS uber/v1 WPID per component
          {componentProductId, offerId, productId,
           offerPublishStatus, statusChangeReasons}
        ],
        steps: [str],                  # audit trail of each step
      }

    Valid   = offer is BUNDLE and at least one component is UNPUBLISHED
    Invalid = offer is BUNDLE but all components are PUBLISHED
    Manual  = cannot determine (missing data / API failures)
    """
    product_class_type = api_response.get("product_class_type")
    bundle_product_id = api_response.get("bundle_product_id")
    component_offers: List[dict] = api_response.get("component_offers", [])
    steps: List[str] = api_response.get("steps", [])

    details: Dict[str, Any] = {
        "bundleProductId": bundle_product_id,
        "productClassType": product_class_type,
        "validationSteps": steps,
        "componentOffers": component_offers,
    }

    # Step 1 failed or not a bundle
    if product_class_type != "BUNDLE":
        if not product_class_type:
            return _manual_review(
                offer_id, "BUNDLE_COMPONENTS_UNPUBLISHED",
                "Could not determine product_class_type from IQS PRODUCT data – manual review required.",
            )
        return _invalid(
            offer_id, "BUNDLE_COMPONENTS_UNPUBLISHED",
            f"product_class_type='{product_class_type}' is not BUNDLE – "
            "BUNDLE_COMPONENTS_UNPUBLISHED is not justified.",
            details,
        )

    # Step 2 returned no component IDs
    if not component_offers:
        return _manual_review(
            offer_id, "BUNDLE_COMPONENTS_UNPUBLISHED",
            f"Bundle confirmed (productId={bundle_product_id}) but no component offers "
            "could be resolved via Uber Keys – manual review required.",
        )

    # Steps 4 & 5: check component publish statuses
    unpublished = [
        c for c in component_offers
        if c.get("offerPublishStatus") == "UNPUBLISHED"
    ]
    published = [
        c for c in component_offers
        if c.get("offerPublishStatus") == "PUBLISHED"
    ]
    unknown = [
        c for c in component_offers
        if c.get("offerPublishStatus") not in ("PUBLISHED", "UNPUBLISHED")
    ]

    if unpublished:
        unpub_summary = "; ".join(
            f"productId={c['componentProductId']} offerId={c.get('offerId')} "
            f"reasons={c.get('statusChangeReasons', [])}"
            for c in unpublished
        )
        return _valid(
            offer_id, "BUNDLE_COMPONENTS_UNPUBLISHED",
            f"Component offer(s) are unpublished ({unpub_summary}); "
            "BUNDLE_COMPONENTS_UNPUBLISHED unpublish reason is correctly applied.",
            details,
        )

    if published and not unknown:
        pub_summary = "; ".join(
            f"productId={c['componentProductId']} offerId={c.get('offerId')}"
            for c in published
        )
        return _invalid(
            offer_id, "BUNDLE_COMPONENTS_UNPUBLISHED",
            f"All component offers are PUBLISHED ({pub_summary}); "
            "BUNDLE_COMPONENTS_UNPUBLISHED unpublish reason is NOT justified.",
            details,
        )

    return _manual_review(
        offer_id, "BUNDLE_COMPONENTS_UNPUBLISHED",
        f"Bundle confirmed (productId={bundle_product_id}) but component offer status "
        "could not be fully determined – manual review required.",
    )


def validate_product_not_active(offer_id: str, api_response: dict) -> ValidationResult:
    """PRODUCT_NOT_ACTIVE: Multi-step validation via Offer Store, Product Matching, Product Store, Uber Keys.

    api_response is a pna_context dict built by OfferValidatorService:
      {
        gtin: str | None,                   # from Offer Store offerIdentifiers[1].keyName
        wid: str | None,                    # WPID from Product Matching API
        gtin_in_product: bool | None,       # whether GTIN found in Product Store payload
        uber_keys_offer_id: str | None,     # offer ID returned by Uber Keys GTIN_TO_DOTCOM_OFFER_ID
        steps: [str],                       # audit trail
      }

    Valid (Step 3) = GTIN found in Product Store payload → product correctly inactivated
    Valid (Step 4) = GTIN not in Product Store AND Uber Keys offer doesn't match → correctly inactivated
    Needs Review   = GTIN not in Product Store AND Uber Keys offer matches → GTIN missing from offer
    Needs Review   = any data lookup failure
    """
    gtin: Optional[str] = api_response.get("gtin")
    wid: Optional[str] = api_response.get("wid")
    gtin_in_product: Optional[bool] = api_response.get("gtin_in_product")
    uber_keys_offer_id: Optional[str] = api_response.get("uber_keys_offer_id")
    steps: List[str] = api_response.get("steps", [])

    uber_keys_offer_ids: List[str] = api_response.get("uber_keys_offer_ids", [])
    details: Dict[str, Any] = {
        "gtin": gtin,
        "wid": wid,
        "gtinFoundInProductStore": gtin_in_product,
        "uberKeysOfferId": uber_keys_offer_id,
        "uberKeysOfferIds": uber_keys_offer_ids,
        "uberKeysMapsToSameOffer": bool(uber_keys_offer_id and uber_keys_offer_id == offer_id),
        "validationSteps": steps,
    }

    if not gtin:
        return _manual_review(
            offer_id, "PRODUCT_NOT_ACTIVE",
            "Could not retrieve GTIN from Offer Store – manual review required.",
        )

    # If WID is missing, Product Matching returned no result — stop here
    if not wid and uber_keys_offer_id is None:
        return ValidationResult(
            offer_id=offer_id,
            reason_code="PRODUCT_NOT_ACTIVE",
            status=ValidationStatus.NEEDS_MANUAL_REVIEW,
            message=(
                f"GTIN={gtin}: Product Matching returned no WID – "
                "cannot validate product inactivation; needs manual review."
            ),
            details=details,
        )

    if gtin_in_product is None and wid is not None:
        return _manual_review(
            offer_id, "PRODUCT_NOT_ACTIVE",
            f"GTIN={gtin}, WID={wid}: Product Store lookup failed – manual review required.",
        )

    if gtin_in_product:
        # Uber Keys maps GTIN → same offer: GTIN was never reassigned; reason may not be justified.
        if uber_keys_offer_id and uber_keys_offer_id == offer_id:
            return _manual_review(
                offer_id, "PRODUCT_NOT_ACTIVE",
                f"GTIN={gtin} is present in Product Store (WID={wid}) but Uber Keys still maps "
                f"this GTIN to the same offer ({offer_id}) – GTIN has not been reassigned to a "
                "new offer; PRODUCT_NOT_ACTIVE may not be justified; manual review required.",
            )
        return _valid(
            offer_id, "PRODUCT_NOT_ACTIVE",
            f"GTIN={gtin} is present in Product Store (WID={wid}) and Uber Keys maps GTIN to a "
            "different offer – product is correctly inactivated; PRODUCT_NOT_ACTIVE unpublish is "
            "correctly applied.",
            details,
        )

    # GTIN not in product store — check Uber Keys
    if uber_keys_offer_id is None:
        return _manual_review(
            offer_id, "PRODUCT_NOT_ACTIVE",
            f"GTIN={gtin} not found in Product Store and Uber Keys lookup failed – manual review required.",
        )

    if uber_keys_offer_id != offer_id:
        if not uber_keys_offer_id:
            msg = (
                f"GTIN={gtin} not in Product Store and Uber Keys returns no offer for this GTIN – "
                "product correctly inactivated; PRODUCT_NOT_ACTIVE unpublish is correctly applied."
            )
        else:
            msg = (
                f"GTIN={gtin} not in Product Store and Uber Keys maps GTIN to a different offer "
                f"({uber_keys_offer_id!r} ≠ {offer_id!r}) – "
                "product correctly inactivated; PRODUCT_NOT_ACTIVE unpublish is correctly applied."
            )
        return _valid(offer_id, "PRODUCT_NOT_ACTIVE", msg, details)

    return _manual_review(
        offer_id, "PRODUCT_NOT_ACTIVE",
        f"GTIN={gtin} not in Product Store and Uber Keys still maps GTIN to this offer ({offer_id}) – "
        "product may be retired but GTIN was not reassigned; manual review required.",
    )


def validate_1p_sales_unit_missing(offer_id: str, api_response: dict) -> ValidationResult:
    """1P_SALES_UNIT_MISSING: VALID if sales_unit value is null/missing in IQS PRODUCT."""
    path = "x.payload.product.derived_attributes.sales_unit.values[0].value"
    sales_unit = _get(api_response, path)
    if sales_unit is None:
        return _valid(offer_id, "1P_SALES_UNIT_MISSING",
            "sales_unit is null or missing – 1P_SALES_UNIT_MISSING unpublish is correctly applied. "
            "SALES_UNIT will be added by business so, please reach out to business to get this attribute added.",
            {"salesUnit": None, "path": path})
    return _invalid(offer_id, "1P_SALES_UNIT_MISSING",
        f"sales_unit is '{sales_unit}' – sales unit data is present; offer is wrongly unpublished.",
        {"salesUnit": sales_unit, "path": path})


def validate_shipping_info_missing(offer_id: str, api_response: dict) -> ValidationResult:
    """SHIPPING_INFO_MISSING: VALID if oscar[0].result.offerId is null/missing in IQS OSCAR."""
    path = "x.payload.offers[0].oscar[0].result.offerId"
    oscar_offer_id = _get(api_response, path)
    if oscar_offer_id is None:
        return _valid(offer_id, "SHIPPING_INFO_MISSING",
            "OSCAR payload is null or missing – no shipping info found; SHIPPING_INFO_MISSING unpublish is correctly applied.",
            {"oscarOfferId": None, "path": path})
    return _invalid(offer_id, "SHIPPING_INFO_MISSING",
        f"Offer Id from OSCAR Service is '{oscar_offer_id}' – shipping info is present; offer is wrongly unpublished.",
        {"oscarOfferId": oscar_offer_id, "path": path})


def validate_no_min_max_price(offer_id: str, context: dict) -> ValidationResult:
    """NO_MIN_MAX_PRICE: two-step gift card price validation.

    Step 1: IQS PRODUCT – gift_card_type_code.values[0].value must equal 2.
      - If != 2 (or missing): INVALID – item is not a gift card type.
    Step 2: IQS PRICE – minValue and maxValue must both be absent for valid unpublish.
      - Both missing  → VALID
      - Either present → INVALID
    """
    rc = "NO_MIN_MAX_PRICE"
    product_data = context.get("product_data", {})
    price_data = context.get("price_data") or {}

    gc_path = "x.payload.product.product_attributes.gift_card_type_code.values[0].value"
    gc_type_raw = _get(product_data, gc_path)

    try:
        gc_type_val = int(gc_type_raw) if gc_type_raw is not None else None
    except (ValueError, TypeError):
        gc_type_val = None

    if gc_type_val != 2:
        return _invalid(
            offer_id, rc,
            f"gift_card_type_code is '{gc_type_raw}' (not 2) – item is not a gift card type; "
            f"NO_MIN_MAX_PRICE unpublish is not correctly applied.",
            {"giftCardTypeCode": gc_type_raw, "path": gc_path},
        )

    min_path = (
        "x.payload.offers[0].pricing.offerPricingList[0]"
        ".storefrontPricingList[0].currentPrice.minValue"
    )
    max_path = (
        "x.payload.offers[0].pricing.offerPricingList[0]"
        ".storefrontPricingList[0].currentPrice.maxValue"
    )
    min_value = _get(price_data, min_path)
    max_value = _get(price_data, max_path)

    if min_value is None and max_value is None:
        return _valid(
            offer_id, rc,
            "gift_card_type_code=2 and both minValue and maxValue are missing – "
            "NO_MIN_MAX_PRICE unpublish is correctly applied.",
            {"giftCardTypeCode": gc_type_val, "minValue": None, "maxValue": None},
        )

    return _invalid(
        offer_id, rc,
        f"gift_card_type_code=2 but minValue='{min_value}' and maxValue='{max_value}' are present – "
        f"pricing data exists; offer is wrongly unpublished.",
        {"giftCardTypeCode": gc_type_val, "minValue": min_value, "maxValue": max_value},
    )


_GNFR_VALID_SUPPLIERS = {481890, 314101, 538678}
_GNFR_ACCT_DEPT_EXCLUDE = {38, 49}
_GNFR_ACCT_DEPT_EQUAL = {39, 60, 65, 75, 88, 99, 69}


def validate_goods_not_for_resale(offer_id: str, context: dict) -> ValidationResult:
    """GOODS_NOT_FOR_RESALE: Validate using IQS SI (Supply Item) data.

    context is built by OfferValidatorService._validate_goods_not_for_resale:
      {
        item_state_code:        str | None,   # itemStateCode from SI
        buying_region_codes:    list[int],
        replenish_sub_type_codes: list[int],
        unit_cost_amts:         list[float],
        assortment_type_codes:  list[int],
        supplier_nbrs:          list[int],
        accounting_dept_nbrs:   list[int],
        steps:                  list[str],
      }

    VALID   = itemStateCode == GOODS_NOT_FOR_RESALE and at least one GNFR condition is met
    INVALID = itemStateCode != GOODS_NOT_FOR_RESALE (wrongly unpublished)
              OR state matches but no GNFR condition is met (false positive)
    Manual  = SI data unavailable
    """
    _RC = "GOODS_NOT_FOR_RESALE"
    item_state_code: Optional[str] = context.get("item_state_code")
    buying_region_codes: List[int] = context.get("buying_region_codes", [])
    replenish_sub_type_codes: List[int] = context.get("replenish_sub_type_codes", [])
    unit_cost_amts: List[float] = context.get("unit_cost_amts", [])
    assortment_type_codes: List[int] = context.get("assortment_type_codes", [])
    supplier_nbrs: List[int] = context.get("supplier_nbrs", [])
    accounting_dept_nbrs: List[int] = context.get("accounting_dept_nbrs", [])
    steps: List[str] = context.get("steps", [])

    details: Dict[str, Any] = {
        "itemStateCode": item_state_code,
        "buyingRegionCodes": buying_region_codes,
        "replenishSubTypeCodes": replenish_sub_type_codes,
        "unitCostAmts": unit_cost_amts,
        "assortmentTypeCodes": assortment_type_codes,
        "supplierNbrs": supplier_nbrs,
        "accountingDeptNbrs": accounting_dept_nbrs,
        "validationSteps": steps,
    }

    if item_state_code is None:
        return _manual_review(
            offer_id, _RC,
            "Could not retrieve SI data from IQS – manual review required.",
        )

    if item_state_code != "GOODS_NOT_FOR_RESALE":
        return _invalid(
            offer_id, _RC,
            f"itemStateCode='{item_state_code}' is not GOODS_NOT_FOR_RESALE – "
            "GOODS_NOT_FOR_RESALE unpublish is not justified.",
            details,
        )

    # itemStateCode is GOODS_NOT_FOR_RESALE — check GNFR conditions
    supplier_check = any(s in _GNFR_VALID_SUPPLIERS for s in supplier_nbrs)
    acct_dept_not_in_exclude = any(d not in _GNFR_ACCT_DEPT_EXCLUDE for d in accounting_dept_nbrs)
    acct_dept_equal_check = any(d in _GNFR_ACCT_DEPT_EQUAL for d in accounting_dept_nbrs)

    gnfr_conditions: Dict[str, bool] = {
        "buyingRegionCode=7": 7 in buying_region_codes,
        "replenishSubTypeCode=17": 17 in replenish_sub_type_codes,
        "replenishSubTypeCode=21+acctDeptNotIn{38,49}": 21 in replenish_sub_type_codes and acct_dept_not_in_exclude,
        "unitCostAmt<0.03": any(amt < 0.03 for amt in unit_cost_amts),
        "assortmentTypeCode=2": 2 in assortment_type_codes,
        "supplierNbrInGNFRList": supplier_check,
        "acctDeptIn{39,60,65,75,88,99,69}": acct_dept_equal_check,
    }
    matched = [name for name, hit in gnfr_conditions.items() if hit]

    if matched:
        return ValidationResult(
            offer_id=offer_id, reason_code=_RC,
            status=ValidationStatus.VALID,
            message=(
                f"itemStateCode=GOODS_NOT_FOR_RESALE and GNFR condition(s) confirmed: {', '.join(matched)} – "
                "GOODS_NOT_FOR_RESALE unpublish is correctly applied."
            ),
            details={**details, "matchedConditions": matched},
        )

    return ValidationResult(
        offer_id=offer_id, reason_code=_RC,
        status=ValidationStatus.INVALID,
        message=(
            "itemStateCode=GOODS_NOT_FOR_RESALE but no GNFR conditions are met – "
            "offer appears to be a false positive; GOODS_NOT_FOR_RESALE unpublish is not justified."
        ),
        details={**details, "matchedConditions": []},
    )


def validate_needs_inventory(offer_id: str, api_response: dict) -> ValidationResult:
    """NEEDS_INVENTORY: VALID if sellableNational inventory <= 0."""
    raw = api_response.get("_inventory_raw", "NA")
    quantity = api_response.get("_inventory_quantity")

    if quantity is None:
        msg = (
            f"Oasis returned non-numeric sellableNational='{raw}' – manual review required."
            if raw is not None
            else "Could not fetch Oasis inventory data – manual review required."
        )
        return ValidationResult(
            offer_id=offer_id, reason_code="NEEDS_INVENTORY",
            status=ValidationStatus.NEEDS_MANUAL_REVIEW, message=msg, details={},
        )

    if quantity > 0:
        return ValidationResult(
            offer_id=offer_id, reason_code="NEEDS_INVENTORY",
            status=ValidationStatus.INVALID,
            message=f"sellableNational inventory is {quantity} – inventory is available; offer is wrongly unpublished.",
            details={"sellableNational": quantity},
        )

    return ValidationResult(
        offer_id=offer_id, reason_code="NEEDS_INVENTORY",
        status=ValidationStatus.VALID,
        message=f"sellableNational inventory is {quantity} – no inventory available; NEEDS_INVENTORY unpublish is correctly applied.",
        details={"sellableNational": quantity},
    )


_DOTCOM_SELLER_ID = "F55CDC31AB754BB68FE0B39041159D63"


def validate_1p_is_alcohol_beverage_missing(offer_id: str, context: dict) -> ValidationResult:
    """
    1P_IS_ALCOHOL_BEVERAGE_MISSING validation (4-step logic):

    Step 1 – Dotcom check: sellerId must equal the Walmart 1P seller.
             If not → INVALID (unpublish not justified for non-dotcom offer).
    Step 2 – IQS PRODUCT: if is_alcoholic_beverage attribute is present (not null)
             → INVALID (attribute exists; offer wrongly unpublished; needs review).
    Step 3 – Offer createdDtm is within last 24 hours
             → INVALID / NEEDS_MANUAL_REVIEW (newly created offer; attribute may not be populated yet).
    Step 4 – All dotcom offers must have is_alcoholic_beverage; attribute missing on an established
             dotcom offer → INVALID (offer needs review).
    """
    _RC = "1P_IS_ALCOHOL_BEVERAGE_MISSING"
    seller_id = context.get("seller_id")
    is_alcoholic_beverage = context.get("is_alcoholic_beverage")
    created_dtm: Optional[datetime] = context.get("created_dtm")
    steps: list = context.get("steps", [])

    # Step 1: dotcom seller check
    if seller_id != _DOTCOM_SELLER_ID:
        return ValidationResult(
            offer_id=offer_id, reason_code=_RC,
            status=ValidationStatus.INVALID,
            message=(
                f"Offer sellerId='{seller_id}' is not the Walmart 1P dotcom seller – "
                "1P_IS_ALCOHOL_BEVERAGE_MISSING unpublish is not justified for non-dotcom offers."
            ),
            details={"seller_id": seller_id, "steps": steps},
        )

    # Step 2: is_alcoholic_beverage attribute present → wrongly unpublished
    if is_alcoholic_beverage is not None:
        return ValidationResult(
            offer_id=offer_id, reason_code=_RC,
            status=ValidationStatus.INVALID,
            message=(
                f"is_alcoholic_beverage='{is_alcoholic_beverage}' is present in IQS PRODUCT derived_attributes – "
                "attribute is not missing; offer is wrongly unpublished."
            ),
            details={"is_alcoholic_beverage": is_alcoholic_beverage, "steps": steps},
        )

    # Step 3: newly created offer (within last 24 hours) → needs manual review
    if created_dtm is not None:
        now = datetime.now(timezone.utc)
        age_hours = (now - created_dtm).total_seconds() / 3600
        if age_hours <= 24:
            return ValidationResult(
                offer_id=offer_id, reason_code=_RC,
                status=ValidationStatus.NEEDS_MANUAL_REVIEW,
                message=(
                    f"Offer was created {age_hours:.1f} hour(s) ago (within 24 hours) – this is a newly created offer; "
                    "is_alcoholic_beverage attribute may not have been populated yet; needs manual review."
                ),
                details={
                    "is_alcoholic_beverage": None,
                    "createdDtm": created_dtm.isoformat(),
                    "ageHours": round(age_hours, 2),
                    "steps": steps,
                },
            )

    # Step 4: dotcom offer with attribute missing and not newly created → Invalid
    created_str = created_dtm.isoformat() if created_dtm else "unknown"
    return ValidationResult(
        offer_id=offer_id, reason_code=_RC,
        status=ValidationStatus.INVALID,
        message=(
            "is_alcoholic_beverage attribute is missing in IQS PRODUCT derived_attributes – "
            "all Walmart 1P dotcom offers are expected to have this attribute; offer needs review."
        ),
        details={"is_alcoholic_beverage": None, "createdDtm": created_str, "steps": steps},
    )


# ---------------------------------------------------------------------------
# Validator registry
# Maps each reason code → (validator_function, iqs_resource_type)
# iqs_resource_type is None when no extra API call is needed
# ---------------------------------------------------------------------------

ValidatorEntry = Tuple[Callable[[str, dict], ValidationResult], Optional[str]]

VALIDATOR_REGISTRY: Dict[str, ValidatorEntry] = {
    "END_DATE":                       (validate_end_date,                     "OFFER"),
    "START_DATE":                     (validate_start_date,                   "OFFER"),
    "NO_PRICE":                       (validate_no_price,                     "PRICE"),
    "NO_LOGISTICS_DATA":              (validate_no_logistics_data,            "LOGISTICS"),
    "NO_ACTIVE_DISTR":                (validate_no_active_distr,              "LOGISTICS"),
    "MISSING_DIMS":                   (validate_missing_dims,                 "LOGISTICS"),
    "PRODUCT_NAME_MISSING":           (validate_product_name_missing,         "PRODUCT"),
    "PRIMARY_IMAGE_MISSING":          (validate_primary_image_missing,        "PRODUCT"),
    "1P_COMPLIANCE_GUNS":             (validate_1p_compliance_guns,           "PRODUCT"),
    "1P_SALES_UNIT_MISSING":          (validate_1p_sales_unit_missing,        "PRODUCT"),
    "SHIPPING_INFO_MISSING":          (validate_shipping_info_missing,        "OSCAR"),
    "NO_MIN_MAX_PRICE":               (validate_no_min_max_price,             None),
    "UNASSIGNED_TAX_CODE":            (validate_unassigned_tax_code,          "OFFER"),
    "BUNDLE_COMPONENTS_UNPUBLISHED":  (validate_bundle_components_unpublished, None),
    "PRODUCT_NOT_ACTIVE":             (validate_product_not_active,           None),
    "OPS_DELETE":                     (validate_product_not_active,           None),
    "FORCED":                         (validate_product_not_active,           None),
    "GOODS_NOT_FOR_RESALE":           (validate_goods_not_for_resale,         None),
    "NEEDS_INVENTORY":                (validate_needs_inventory,              None),
    "1P_IS_ALCOHOL_BEVERAGE_MISSING": (validate_1p_is_alcohol_beverage_missing, None),
}


def get_validator(reason_code: str) -> Optional[ValidatorEntry]:
    """Return (validator_fn, api_type) for a known reason code, or None if unknown."""
    return VALIDATOR_REGISTRY.get(reason_code.upper())


def validate_unknown_reason(offer_id: str, reason_code: str) -> ValidationResult:
    """Return UNKNOWN_REASON result for unrecognised reason codes."""
    return ValidationResult(
        offer_id=offer_id,
        reason_code=reason_code,
        status=ValidationStatus.UNKNOWN_REASON,
        message=f"Unpublish reason code '{reason_code}' is not in the known list.",
        details={},
    )
