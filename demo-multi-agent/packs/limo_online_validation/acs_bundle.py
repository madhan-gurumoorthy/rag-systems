"""Deterministic ACS-inputs bundle for the LIMO Online Eligibility pack.

One callable, ``acs_inputs_bundled``, exposed as a ``python_function``
tool (``DIAG-ACS-INPUTS-BUNDLE-01``).  Given the seller / node / offer
keys (typically read from ODIN), it fetches every ACS-input upstream
in one server-side step and pipes each response through its analyzer,
returning the four slots the ACS verdict needs:

    ase_status, ase_seller, acs_enabled, plus the pass-through
    ase_odin caller provides.

Replaces the prior six-tool LLM chain
(DEW-Seller → ANALYZE → DCC → ANALYZE → CONSOLIDATED-FC → ANALYZE)
which `gpt-4.1-mini` consistently truncated.  A single tool the LLM
calls once after ODIN guarantees the inputs land on state before the
verdict gate fires.

Upstream endpoint URLs and auth headers are read via the same
``_get_config_value`` helper the framework HTTP-API tools use, so the
secrets-file contract is unchanged.  Partial upstream failures are
surfaced as ``*_UPSTREAM_ERROR`` outcomes inside the per-source
sub-block — the bundle never raises.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from agent_factory.tools.executor import _get_config_value
from agent_factory.tools.param_enrichment import get_ssl_context
from packs.limo_online_validation.analyzers import (
    analyze_acs_consolidated,
    analyze_dcc,
    analyze_dew_seller,
    analyze_shipnodes,
)

logger = logging.getLogger(__name__)


def _setting(key: str, default: str = "") -> str:
    val = _get_config_value(key)
    return str(val) if val else default


def _client_kwargs(timeout: float) -> dict[str, Any]:
    """Match the framework HTTP-API handler's TLS posture.

    The Walmart-internal CAs are loaded into ``LIGHTRAG_REQUESTS_CA_BUNDLE``;
    every framework upstream call routes through that SSL context.
    Without it, internal endpoints fail with ``CERTIFICATE_VERIFY_FAILED``.
    """
    ctx = get_ssl_context()
    kwargs: dict[str, Any] = {"timeout": timeout}
    if ctx is not None:
        kwargs["verify"] = ctx
    return kwargs


async def _fetch_dew_seller(seller_id: str) -> tuple[Any, str | None]:
    base = _setting("LIMO_ONLINE_DEW_SELLER_BASE_URL")
    if not base or not seller_id:
        return None, "DEW_SELLER_INPUT_MISSING"
    url = f"{base}/seller/read/id/{seller_id}-SLR-ELG"
    try:
        async with httpx.AsyncClient(**_client_kwargs(30.0)) as client:
            resp = await client.get(url, headers={"Accept": "application/json"})
            resp.raise_for_status()
            return resp.json(), None
    except Exception as exc:  # noqa: BLE001 — surface upstream errors as outcomes
        logger.warning("acs_bundle: DEW Seller upstream error %s", exc)
        return None, f"DEW_SELLER_UPSTREAM_ERROR:{exc}"


async def _fetch_shipnodes(offer_id: str) -> tuple[Any, str | None]:
    base = _setting("LIMO_ONLINE_SHIPNODES_BASE_URL")
    consumer = _setting("LIMO_ONLINE_SHIPNODES_CONSUMER_ID")
    if not base or not offer_id:
        return None, "SHIPNODES_INPUT_MISSING"
    url = f"{base}/fuel/v1/offers/{offer_id}"
    headers = {
        "Content-Type":   "application/json",
        "Accept":         "application/json",
        "WM_CONSUMER.ID": consumer,
    }
    try:
        async with httpx.AsyncClient(**_client_kwargs(30.0)) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.json(), None
    except Exception as exc:  # noqa: BLE001
        logger.warning("acs_bundle: Shipnodes upstream error %s", exc)
        return None, f"SHIPNODES_UPSTREAM_ERROR:{exc}"


async def _fetch_dcc(legacy_distributor_id: str) -> tuple[Any, str | None]:
    base = _setting("LIMO_ONLINE_DCC_BASE_URL")
    if not base or not legacy_distributor_id:
        return None, "DCC_INPUT_MISSING"
    url = f"{base}/dc-square-app/services/distributors/{legacy_distributor_id}"
    headers = {
        "Content-Type":     "application/json",
        "Accept":           "application/json",
        "WM_CONSUMER.ID":   _setting("LIMO_ONLINE_DCC_CONSUMER_ID"),
        "WM_SVC.ENV":       _setting("LIMO_ONLINE_DCC_SVC_ENV"),
        "WM_SVC.NAME":      _setting("LIMO_ONLINE_DCC_SVC_NAME"),
        "WM_SVC.VERSION":   _setting("LIMO_ONLINE_DCC_SVC_VERSION"),
        "WM_BU.ID":         _setting("LIMO_ONLINE_DCC_BU_ID"),
        "WM_MART.ID":       _setting("LIMO_ONLINE_DCC_MART_ID"),
    }
    try:
        async with httpx.AsyncClient(**_client_kwargs(30.0)) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.json(), None
    except Exception as exc:  # noqa: BLE001
        logger.warning("acs_bundle: DCC upstream error %s", exc)
        return None, f"DCC_UPSTREAM_ERROR:{exc}"


async def _fetch_consolidated(
    offer_id: str,
    partner_id: str,
    partner_type: str,
    state_code: str,
    zip_code: str,
    country_code: str,
) -> tuple[Any, str | None]:
    base = _setting("LIMO_ONLINE_CONSOLIDATED_FC_BASE_URL")
    if not base or not offer_id:
        return None, "CONSOLIDATED_INPUT_MISSING"
    url = f"{base}/offer/consolidated"
    headers = {
        "Content-Type":          "application/json",
        "Accept":                "application/json",
        # Pin gzip/deflate — upstream emits a malformed zstd frame when
        # zstd is advertised (see case2_gate consolidated_fc_gated).
        "Accept-Encoding":       "gzip, deflate",
        "FUEL_SUBSCRIPTION_ID":  _setting("LIMO_ONLINE_CONSOLIDATED_FC_FUEL_SUBSCRIPTION_ID"),
        "WM_CONSUMER.ID":        _setting("LIMO_ONLINE_CONSOLIDATED_FC_CONSUMER_ID"),
        "WM_QOS.CORRELATION_ID": _setting("LIMO_ONLINE_CONSOLIDATED_FC_QOS_CORRELATION_ID"),
        "WM_SVC.ENV":            _setting("LIMO_ONLINE_CONSOLIDATED_FC_SVC_ENV"),
        "WM_SVC.NAME":           _setting("LIMO_ONLINE_CONSOLIDATED_FC_SVC_NAME"),
    }
    sc = state_code   or _setting("LIMO_ONLINE_CONSOLIDATED_FC_DEFAULT_STATE_CODE")
    zc = zip_code     or _setting("LIMO_ONLINE_CONSOLIDATED_FC_DEFAULT_ZIP_CODE")
    cc = country_code or _setting("LIMO_ONLINE_CONSOLIDATED_FC_DEFAULT_COUNTRY_CODE")
    body = {
        "payload": {
            "address": {"stateCode": sc, "zipCode": zc, "countryCode": cc},
            "sellers": [{
                "partnerId":   partner_id,
                "partnerType": partner_type,
                "nodes":       [],
                "offers":      [{"offerId": offer_id}],
            }],
        }
    }
    last_exc: Exception | None = None
    for attempt in (1, 2):
        try:
            async with httpx.AsyncClient(**_client_kwargs(90.0)) as client:
                resp = await client.post(url, headers=headers, json=body)
                resp.raise_for_status()
                return resp.json(), None
        except httpx.HTTPStatusError as exc:
            last_exc = exc
            if exc.response.status_code == 408 and attempt == 1:
                logger.info(
                    "acs_bundle: 408 from Consolidated upstream — retrying once"
                )
                continue
            break
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            break
    logger.warning("acs_bundle: Consolidated upstream error %s", last_exc)
    return None, f"CONSOLIDATED_UPSTREAM_ERROR:{last_exc}"


async def acs_inputs_bundled(
    seller_id: str = "",
    node_id: str = "",
    offer_id: str = "",
    partner_id: str = "",
    partner_type: str = "",
    state_code: str = "",
    zip_code: str = "",
    country_code: str = "",
    ase_odin: Any = None,
    **_: Any,
) -> dict[str, Any]:
    """Fetch every ACS input in one call and surface the four verdict slots.

    Inputs (typically extracted by ODIN earlier in the chain):
      - ``seller_id``  — ODIN ``sid``; passed to DEW Seller.
      - ``node_id``    — node the offer is being validated against;
                         passed to ``analyze_shipnodes``.
      - ``offer_id``   — ODIN ``oid``; passed to Shipnodes + Consolidated.
      - ``partner_id`` / ``partner_type`` — ODIN-resolved seller
                         identifiers for the Consolidated request body.
      - ``state_code`` / ``zip_code`` / ``country_code`` — optional
                         shipping-address overrides for Consolidated;
                         fall back to ``LIMO_ONLINE_CONSOLIDATED_FC_DEFAULT_*``.
      - ``ase_odin``   — ODIN ``oa.oss.ase``; passed through verbatim
                         so the bundle's response carries every input
                         the verdict gate needs.

    Outputs:
      - ``outcome``                 — ``ACS_INPUTS_BUNDLED`` (always).
      - ``ase_odin``                — pass-through.
      - ``ase_status`` / ``ase_seller``  — from DEW Seller.
      - ``legacy_distributor_id``   — from Shipnodes (used to fetch DCC).
      - ``acs_enabled``             — from DCC; falls back to
                                      Consolidated ``isACSEnabled`` when
                                      DCC is missing or unreachable.
      - ``sources``                 — per-upstream {fetched, error,
                                      analyzer_outcome} record for
                                      debugging.
      - ``inputs_received``         — echo of the seller / node / offer
                                      ids the bundle actually received,
                                      so the LLM can self-check whether
                                      the right keys were passed.
      - ``warnings``                — list of human-readable strings
                                      flagging missing-input cases the
                                      LLM should fix before re-calling.

    The bundle never raises.  A failed upstream surfaces in
    ``sources[name].error`` and leaves the corresponding slots
    ``null`` — the verdict gate then treats them the same way it would
    if the LLM had skipped the call.
    """
    sources: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []

    if not seller_id:
        warnings.append(
            "seller_id was empty — DEW Seller skipped, ase_status / "
            "ase_seller will be null.  Pass seller_id=<ODIN sid> from "
            "the prior DIAG-ODIN-01 call."
        )
    if not offer_id:
        warnings.append(
            "offer_id was empty — Shipnodes + Consolidated skipped, "
            "legacy_distributor_id / acs_enabled will be null.  Pass "
            "offer_id=<ODIN oid> from the prior DIAG-ODIN-01 call."
        )

    # 1. DEW Seller — ase_status, ase_seller.
    dew_raw, dew_err = await _fetch_dew_seller(seller_id)
    dew_analyzed = analyze_dew_seller(dew_seller_response=dew_raw) \
        if dew_raw is not None else {"outcome": "DEW_SELLER_MISSING"}
    sources["dew_seller"] = {
        "fetched":           dew_raw is not None,
        "error":             dew_err,
        "analyzer_outcome":  dew_analyzed.get("outcome"),
    }

    # 2. Shipnodes — legacy_distributor_id (used to fetch DCC).
    sn_raw, sn_err = await _fetch_shipnodes(offer_id)
    sn_analyzed = analyze_shipnodes(shipnodes_response=sn_raw,
                                    node_id=node_id) \
        if sn_raw is not None else {"outcome": "SHIPNODE_NOT_FOUND"}
    legacy_distributor_id = sn_analyzed.get("legacy_distributor_id") or ""
    sources["shipnodes"] = {
        "fetched":           sn_raw is not None,
        "error":             sn_err,
        "analyzer_outcome":  sn_analyzed.get("outcome"),
    }

    # 3. DCC — acs_enabled (primary source).
    dcc_raw, dcc_err = await _fetch_dcc(str(legacy_distributor_id))
    dcc_analyzed = analyze_dcc(dcc_response=dcc_raw) \
        if dcc_raw is not None else {"outcome": "DCC_MISSING"}
    sources["dcc"] = {
        "fetched":           dcc_raw is not None,
        "error":             dcc_err,
        "analyzer_outcome":  dcc_analyzed.get("outcome"),
    }

    # 4. Consolidated FC — acs_enabled fallback when DCC is absent.
    cons_raw, cons_err = await _fetch_consolidated(
        offer_id=offer_id,
        partner_id=partner_id,
        partner_type=partner_type,
        state_code=state_code,
        zip_code=zip_code,
        country_code=country_code,
    )
    cons_analyzed = analyze_acs_consolidated(consolidated_response=cons_raw) \
        if cons_raw is not None else {"outcome": "ACS_CONSOLIDATED_MISSING",
                                      "acs_enabled": None}
    sources["consolidated"] = {
        "fetched":           cons_raw is not None,
        "error":             cons_err,
        "analyzer_outcome":  cons_analyzed.get("outcome"),
    }

    # DCC is the primary signal for acs_enabled; fall back to
    # Consolidated only when DCC is unavailable.
    if dcc_analyzed.get("outcome") == "DCC_PRESENT":
        acs_enabled: Any = dcc_analyzed.get("acs_enabled")
    else:
        acs_enabled = cons_analyzed.get("acs_enabled")

    out: dict[str, Any] = {
        "outcome":               "ACS_INPUTS_BUNDLED",
        "ase_status":            dew_analyzed.get("ase_status"),
        "ase_seller":            dew_analyzed.get("ase_seller"),
        "legacy_distributor_id": legacy_distributor_id or None,
        "acs_enabled":           acs_enabled,
        "sources":               sources,
        "inputs_received": {
            "seller_id": seller_id or None,
            "node_id":   node_id   or None,
            "offer_id":  offer_id  or None,
        },
        "warnings":              warnings,
    }
    # Only echo ase_odin back when the caller passed a non-null value
    # — otherwise we would overwrite the ODIN-derived state slot with
    # a None from a caller that simply forgot the kwarg.
    if ase_odin is not None:
        out["ase_odin"] = ase_odin
    return out


__all__ = ["acs_inputs_bundled"]
