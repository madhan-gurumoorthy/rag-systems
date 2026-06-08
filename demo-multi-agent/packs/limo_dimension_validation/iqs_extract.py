"""Deterministic IQS TI fetch + flatten.

Fetches all trade-item records for a single GTIN from IQS LIMO, classifies
them into GOLD vs Supplier by ``informationProviderTypeCode``, and returns
a flat dict of 12 slot values plus an outcome.

The runtime is responsible only for:
  * calling :func:`iqs_extract_for_gtin` with a 14-digit GTIN;
  * forwarding the returned ``iqs_gold_*`` / ``iqs_supplier_*`` slots
    into the comparator and state.

The LLM never sees the raw IQS payload, eliminating the per-record
field-navigation step that was previously dropping IQS writes.

Contract
--------
Inputs:
  * ``gtin`` — 14-digit GTIN string.

Returns (always a dict with all 14 keys):
  * ``outcome``                   — ``TI_DATA_PRESENT`` | ``TI_DIMS_MISSING``
                                    | ``UPSTREAM_ERROR``
  * ``gtin``                      — the GTIN that was queried
  * ``iqs_gold_height``           — float | None
  * ``iqs_gold_length``           — float | None
  * ``iqs_gold_width``            — float | None
  * ``iqs_gold_weight``           — float | None
  * ``iqs_gold_timestamp``        — str   | None
  * ``iqs_gold_capture_method``   — str   | None  (raw code, e.g.
                                                   ``PREDICTED``)
  * ``iqs_supplier_height``       — float | None
  * ``iqs_supplier_length``       — float | None
  * ``iqs_supplier_width``        — float | None
  * ``iqs_supplier_weight``       — float | None
  * ``iqs_supplier_timestamp``    — str   | None
  * ``iqs_supplier_capture_method`` — str | None

Invariants:
  * Missing fields are ``None``, never ``""``, ``0``, or ``"—"``.
  * The first GOLD record (``informationProviderTypeCode == "GOLD"``)
    wins for the GOLD slots.
  * The first non-GOLD record wins for the Supplier slots.
  * Capture method is read first from
    ``metadata.tradeItemDimensions.receivingDimensionsCaptureMethodTypeCode``
    and falls back to
    ``metadata.tradeItemWeight.receivingDimensionsCaptureMethodTypeCode``
    when the dimensions key is absent.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ── Public flat-slot schema ──────────────────────────────────────────
_FLAT_SLOTS: tuple[str, ...] = (
    "iqs_gold_height",
    "iqs_gold_length",
    "iqs_gold_width",
    "iqs_gold_weight",
    "iqs_gold_timestamp",
    "iqs_gold_capture_method",
    "iqs_supplier_height",
    "iqs_supplier_length",
    "iqs_supplier_width",
    "iqs_supplier_weight",
    "iqs_supplier_timestamp",
    "iqs_supplier_capture_method",
)


def _empty_slots() -> dict[str, Any]:
    return {slot: None for slot in _FLAT_SLOTS}


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _capture_method(metadata: dict[str, Any] | None) -> Optional[str]:
    """Pull the dimensions capture method, falling back to weight."""
    if not isinstance(metadata, dict):
        return None
    dim_meta = metadata.get("tradeItemDimensions")
    if isinstance(dim_meta, dict):
        code = dim_meta.get("receivingDimensionsCaptureMethodTypeCode")
        if code:
            return str(code)
    wt_meta = metadata.get("tradeItemWeight")
    if isinstance(wt_meta, dict):
        code = wt_meta.get("receivingDimensionsCaptureMethodTypeCode")
        if code:
            return str(code)
    return None


def _extract_record(record: dict[str, Any]) -> dict[str, Any]:
    """Pull dims/weight/timestamp/capture method from one IQS record.

    Returns a partial slot dict using neutral keys (``height``, ``length``,
    ``width``, ``weight``, ``timestamp``, ``capture_method``).  The caller
    namespaces them into ``iqs_gold_*`` / ``iqs_supplier_*``.
    """
    out = {
        "height": None,
        "length": None,
        "width": None,
        "weight": None,
        "timestamp": None,
        "capture_method": None,
    }
    payload = record.get("payloadJson") if isinstance(record, dict) else None
    attrs = payload.get("attributes") if isinstance(payload, dict) else None
    if not isinstance(attrs, dict):
        return out

    # Dimensions live in tradeItemDimensions[0]
    dims_list = attrs.get("tradeItemDimensions")
    if isinstance(dims_list, list) and dims_list:
        first = dims_list[0]
        if isinstance(first, dict):
            out["height"] = _to_float(first.get("tradeItemDimensionsHeightQty"))
            out["length"] = _to_float(first.get("tradeItemDimensionsDepthQty"))
            out["width"] = _to_float(first.get("tradeItemDimensionsWidthQty"))

    # Weight lives in tradeItemWeight[0]
    wt_list = attrs.get("tradeItemWeight")
    if isinstance(wt_list, list) and wt_list:
        first_wt = wt_list[0]
        if isinstance(first_wt, dict):
            out["weight"] = _to_float(first_wt.get("tradeItemWeightQty"))

    # Timestamp
    ts = attrs.get("lastUpdateTimestamp")
    if ts:
        out["timestamp"] = str(ts)

    # Capture method (under metadata.tradeItemDimensions / .tradeItemWeight)
    metadata = attrs.get("metadata")
    out["capture_method"] = _capture_method(metadata)

    return out


def _classify_records(matching_records: list[dict[str, Any]]) -> dict[str, Any]:
    """Split records into GOLD vs Supplier and flatten the first of each."""
    slots = _empty_slots()
    gold_found = False
    supplier_found = False

    for record in matching_records or []:
        if not isinstance(record, dict):
            continue
        provider_code = (record.get("informationProviderTypeCode") or "").upper()
        is_gold = provider_code == "GOLD"

        if is_gold and not gold_found:
            ext = _extract_record(record)
            slots["iqs_gold_height"] = ext["height"]
            slots["iqs_gold_length"] = ext["length"]
            slots["iqs_gold_width"] = ext["width"]
            slots["iqs_gold_weight"] = ext["weight"]
            slots["iqs_gold_timestamp"] = ext["timestamp"]
            slots["iqs_gold_capture_method"] = ext["capture_method"]
            gold_found = True
        elif not is_gold and not supplier_found:
            ext = _extract_record(record)
            slots["iqs_supplier_height"] = ext["height"]
            slots["iqs_supplier_length"] = ext["length"]
            slots["iqs_supplier_width"] = ext["width"]
            slots["iqs_supplier_weight"] = ext["weight"]
            slots["iqs_supplier_timestamp"] = ext["timestamp"]
            slots["iqs_supplier_capture_method"] = ext["capture_method"]
            supplier_found = True

        if gold_found and supplier_found:
            break

    return slots


def _iqs_config() -> dict[str, str]:
    """Read IQS LIMO connection settings from Dynaconf."""
    from agent_factory.infrastructure.settings import get_config

    config = get_config()
    section = getattr(config, "iqs_limo", None)
    if section is None:
        raise RuntimeError("IQS LIMO config section ([default.iqs_limo]) missing")

    required = (
        "IQS_LIMO_BASE_URL",
        "IQS_LIMO_CONSUMER_ID",
        "IQS_LIMO_QOS_CORRELATION_ID",
        "IQS_LIMO_SVC_ENV",
        "IQS_LIMO_SVC_NAME",
        "IQS_LIMO_SVC_VERSION",
    )
    out: dict[str, str] = {}
    for key in required:
        val = getattr(section, key, None)
        if val is None:
            raise RuntimeError(f"IQS LIMO config key missing: {key}")
        out[key] = str(val)
    return out


def _fetch_iqs_records(gtin: str) -> list[dict[str, Any]]:
    """GET ``/catalog/v1`` for the GTIN; return ``matching_records``."""
    import httpx

    cfg = _iqs_config()
    url = (
        f"{cfg['IQS_LIMO_BASE_URL']}/catalog/v1"
        f"?id={gtin}&filterGoldenData=false&type=GTIN&rt=TI"
    )
    headers = {
        "WM_CONSUMER.ID": cfg["IQS_LIMO_CONSUMER_ID"],
        "WM_QOS.CORRELATION_ID": cfg["IQS_LIMO_QOS_CORRELATION_ID"],
        "WM_SVC.ENV": cfg["IQS_LIMO_SVC_ENV"],
        "WM_SVC.NAME": cfg["IQS_LIMO_SVC_NAME"],
        "WM_SVC.VERSION": cfg["IQS_LIMO_SVC_VERSION"],
        "ENABLE_AUTH_OVERRIDE_TEMP": "",
    }
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(url, headers=headers)
        resp.raise_for_status()
        body = resp.json()

    payload = body.get("payload") if isinstance(body, dict) else None
    items = payload.get("supplyTradeItems") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return []
    return items


def iqs_extract_for_gtin(gtin: str) -> dict[str, Any]:
    """Fetch IQS TI for ``gtin`` and return flat GOLD/Supplier slots.

    Always returns a dict with all 14 keys (``outcome``, ``gtin``, plus
    the 12 flat slots).  Failures map to ``outcome = UPSTREAM_ERROR``
    with every slot ``None``.
    """
    base = {"outcome": "TI_DIMS_MISSING", "gtin": gtin, **_empty_slots()}

    if not gtin:
        base["outcome"] = "TI_DIMS_MISSING"
        return base

    try:
        records = _fetch_iqs_records(gtin)
    except Exception as exc:
        logger.exception("IQS fetch failed for GTIN %s", gtin)
        base["outcome"] = "UPSTREAM_ERROR"
        base["error"] = str(exc)
        return base

    if not records:
        base["outcome"] = "TI_DIMS_MISSING"
        return base

    slots = _classify_records(records)
    base.update(slots)

    has_any = any(
        slots.get(k) is not None
        for k in ("iqs_gold_height", "iqs_gold_weight", "iqs_supplier_height", "iqs_supplier_weight")
    )
    base["outcome"] = "TI_DATA_PRESENT" if has_any else "TI_DIMS_MISSING"
    return base


__all__ = ["iqs_extract_for_gtin"]
