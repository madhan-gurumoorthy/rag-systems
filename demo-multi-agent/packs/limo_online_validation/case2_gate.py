"""Deterministic Case 2 (AURUM gate) enforcement for the retrieval
pipeline.

The retrieval (chat) pipeline exposes raw HTTP tools to a single LLM
agent.  Without code-side enforcement the LLM is free to call DEW,
Promise, and Consolidated even when AURUM has flagged the requested
node as INACTIVE, and is free to skip the AURUM analyzer entirely
when the raw AURUM response looks empty to a human reader (e.g. when
``offerNodeAttr.nodes`` is ``{}`` and the node actually lives under
``offerDistributorAttr.nodes``).  This module exposes Python-function
tools that replace the raw HTTP tools and remove that freedom:

  - ``aurum_fc_analyzed``      — AURUM FC fetch + analyzer in one call.
  - ``dew_fc_gated``           — DEW FC, gated.
  - ``promise_gated``          — Wakanda Promise, gated.
  - ``consolidated_fc_gated``  — Eligibility Consolidated FC, gated.

Each gated wrapper re-derives the Case 2 gate from the raw AURUM
response on every call (no state trust, no LLM trust) and refuses to
make the upstream HTTP request when the gate fails.  When the gate
passes the wrapper makes the same HTTP request the framework
``http_api`` tool would have made and pipes the response through the
matching analyzer.

``aurum_fc_analyzed`` fetches AURUM and runs ``analyze_aurum_fc`` in
the same call, so the LLM cannot render the AURUM block from the raw
HTTP response — the analyzer is the only source of
``aurum_node_status`` / ``aurum_dcc_status`` / ``aurum_inclusions`` /
``aurum_exclusions``.

Upstream endpoint URLs and auth headers are read from the same
Dynaconf keys the ``tools.yaml`` templates use (``LIMO_ONLINE_*``),
via the framework's ``_get_config_value`` helper.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from agent_factory.tools.executor import _get_config_value
from packs.limo_online_validation.analyzers import (
    analyze_aurum_fc,
    analyze_consolidated_fc,
    analyze_dew_fc,
    analyze_promise,
)

logger = logging.getLogger(__name__)


_CASE2_STOP_TEMPLATE = "Node is inactive"


# ─────────────────────────────────────────────────────────────────────
# Gate
# ─────────────────────────────────────────────────────────────────────


def case2_gate(aurum_response: Any = None,
               node_id: str = "",
               **_: Any) -> dict[str, Any]:
    """Re-derive the Case 2 gate deterministically from raw AURUM JSON.

    Returns a dict with::

        {
          "blocked":           bool,
          "outcome":           "CASE2_PROCEED" | "CASE2_BLOCKED",
          "aurum_outcome":     <analyzer outcome code>,
          "aurum_node_status": <sts>,
          "aurum_dcc_status":  <dccSts>,
          "stop_message":      <human-readable message> | None,
        }

    The pipeline is BLOCKED when the AURUM analyzer outcome is one of
    ``AURUM_NODE_INACTIVE`` / ``AURUM_NODE_MISSING`` / ``AURUM_NO_PATHS``
    / ``AURUM_NOT_FOUND`` — i.e. anything that is not
    ``AURUM_PATHS_PRESENT``.
    """
    aurum = analyze_aurum_fc(aurum_response=aurum_response, node_id=node_id)
    sts = aurum.get("aurum_node_status")
    dcc = aurum.get("aurum_dcc_status")
    outcome = aurum.get("outcome")

    if outcome != "AURUM_PATHS_PRESENT":
        return {
            "blocked":           True,
            "outcome":           "CASE2_BLOCKED",
            "aurum_outcome":     outcome,
            "aurum_node_status": sts,
            "aurum_dcc_status":  dcc,
            "stop_message":      _CASE2_STOP_TEMPLATE,
        }
    return {
        "blocked":           False,
        "outcome":           "CASE2_PROCEED",
        "aurum_outcome":     outcome,
        "aurum_node_status": sts,
        "aurum_dcc_status":  dcc,
        "stop_message":      None,
    }


def _blocked_payload(tool_label: str,
                     gate: dict[str, Any]) -> dict[str, Any]:
    return {
        "outcome":           "CASE2_BLOCKED",
        "tool":              tool_label,
        "called":            False,
        "aurum_outcome":     gate["aurum_outcome"],
        "aurum_node_status": gate["aurum_node_status"],
        "aurum_dcc_status":  gate["aurum_dcc_status"],
        "stop_message":      gate["stop_message"],
        "paths":             [],
    }


def _setting(key: str, default: str = "") -> str:
    val = _get_config_value(key)
    return str(val) if val else default


# ─────────────────────────────────────────────────────────────────────
# Gated wrappers
# ─────────────────────────────────────────────────────────────────────


async def aurum_fc_analyzed(offer_id: str = "",
                            node_id: str = "",
                            **_: Any) -> dict[str, Any]:
    """Fetch AURUM FC and project the per-node payload in one call.

    Mirrors the URL of ``DIAG-AURUM-FC-01``
    (``GET {base}/aurum/services/final-eligibility/preview/tenant/{tenant}/offer/{offer_id}/node/{node_id}``)
    and pipes the raw response through ``analyze_aurum_fc``.

    Returns the analyzer's output dict (``outcome``, ``aurum_node_id``,
    ``aurum_node_type``, ``aurum_node_status``, ``aurum_dcc_status``,
    ``aurum_ols``, ``aurum_inclusions``, ``aurum_exclusions``) plus the
    raw response under ``raw`` for callers that need it.  Upstream
    errors are surfaced as ``outcome=UPSTREAM_ERROR``.

    Removes the LLM's freedom to render the AURUM block from the raw
    HTTP response when the per-node payload lives in
    ``offerDistributorAttr.nodes`` (Marketplace / Distributor nodes)
    rather than ``offerNodeAttr.nodes``.
    """
    base = _setting("LIMO_ONLINE_AURUM_FC_BASE_URL")
    tenant = _setting("LIMO_ONLINE_AURUM_FC_TENANT")
    url = (
        f"{base}/aurum/services/final-eligibility/preview/tenant/"
        f"{tenant}/offer/{offer_id}/node/{node_id}"
    )
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers={"Accept": "application/json"})
            resp.raise_for_status()
            aurum_response = resp.json()
    except Exception as exc:  # noqa: BLE001 — surface upstream errors as outcomes
        logger.warning("aurum_fc_analyzed: upstream error %s", exc)
        return {
            "outcome": "UPSTREAM_ERROR",
            "called":  True,
            "error":   str(exc),
            "aurum_node_id":     None,
            "aurum_node_type":   None,
            "aurum_node_status": None,
            "aurum_dcc_status":  None,
            "aurum_ols":         None,
            "aurum_inclusions":  [],
            "aurum_exclusions":  [],
        }

    analyzed = analyze_aurum_fc(
        aurum_response=aurum_response, node_id=node_id,
    )
    return {
        "outcome":           analyzed.get("outcome", "AURUM_NOT_FOUND"),
        "called":            True,
        "aurum_node_id":     analyzed.get("aurum_node_id"),
        "aurum_node_type":   analyzed.get("aurum_node_type"),
        "aurum_node_status": analyzed.get("aurum_node_status"),
        "aurum_dcc_status":  analyzed.get("aurum_dcc_status"),
        "aurum_ols":         analyzed.get("aurum_ols"),
        "aurum_inclusions":  analyzed.get("aurum_inclusions", []),
        "aurum_exclusions":  analyzed.get("aurum_exclusions", []),
        "raw":               aurum_response,
    }


async def dew_fc_gated(offer_id: str = "",
                       node_id: str = "",
                       aurum_response: Any = None,
                       **_: Any) -> dict[str, Any]:
    """Gated DEW FC fetch.

    Mirrors ``DIAG-DEW-FC-01`` (``GET {base}/offer/read/id/{offer_id}-FC``)
    when the Case 2 gate passes; returns a deterministic ``CASE2_BLOCKED``
    payload — without making the upstream HTTP call — when the gate
    fails.
    """
    gate = case2_gate(aurum_response, node_id)
    if gate["blocked"]:
        logger.info(
            "dew_fc_gated: Case 2 BLOCKED — skipping DEW (%s, sts=%s, dccSts=%s)",
            gate["aurum_outcome"], gate["aurum_node_status"], gate["aurum_dcc_status"],
        )
        return _blocked_payload("DEW_FC", gate)

    base = _setting("LIMO_ONLINE_DEW_FC_BASE_URL")
    url = f"{base}/offer/read/id/{offer_id}-FC"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers={"Accept": "application/json"})
            resp.raise_for_status()
            dew_response = resp.json()
    except Exception as exc:  # noqa: BLE001 — surface upstream errors as outcomes
        logger.warning("dew_fc_gated: upstream error %s", exc)
        return {"outcome": "UPSTREAM_ERROR", "called": True,
                "error": str(exc), "dew_paths": []}

    analyzed = analyze_dew_fc(dew_response=dew_response, node_id=node_id)
    return {
        "outcome":   analyzed.get("outcome", "DEW_FC_RESPONSE_RECEIVED"),
        "called":    True,
        "dew_paths": analyzed.get("dew_paths", []),
    }


async def promise_gated(offer_id: str = "",
                        node_id: str = "",
                        aurum_response: Any = None,
                        **_: Any) -> dict[str, Any]:
    """Gated Wakanda Promise fetch.

    Mirrors ``DIAG-PROMISE-01`` (``POST {base}/fuel/offer`` with the
    ``[{offerId}]`` body) when the Case 2 gate passes; returns
    ``CASE2_BLOCKED`` when the gate fails.
    """
    gate = case2_gate(aurum_response, node_id)
    if gate["blocked"]:
        logger.info(
            "promise_gated: Case 2 BLOCKED — skipping Promise (%s)",
            gate["aurum_outcome"],
        )
        return _blocked_payload("PROMISE", gate)

    base = _setting("LIMO_ONLINE_PROMISE_BASE_URL")
    url = f"{base}/fuel/offer"
    headers = {
        "Content-Type":          "application/json",
        "Accept":                "application/json",
        # Pin Accept-Encoding to gzip/deflate — the upstream serves a
        # malformed zstd frame when httpx advertises zstd support
        # (the zstandard lib is installed in this runtime), so the
        # response fails the frame-descriptor check before JSON parse.
        "Accept-Encoding":       "gzip, deflate",
        "FUEL_SUBSCRIPTION_ID":  _setting("LIMO_ONLINE_PROMISE_FUEL_SUBSCRIPTION_ID"),
        "BATCH_ID":              _setting("LIMO_ONLINE_PROMISE_BATCH_ID"),
        "WM_CONSUMER.ID":        _setting("LIMO_ONLINE_PROMISE_CONSUMER_ID"),
        "WM_QOS.CORRELATION_ID": _setting("LIMO_ONLINE_PROMISE_QOS_CORRELATION_ID"),
    }
    body = {
        "header":  {"headerAttributes": {}},
        "payload": [{"offerId": offer_id}],
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            promise_response = resp.json()
    except Exception as exc:  # noqa: BLE001 — surface upstream errors as outcomes
        logger.warning("promise_gated: upstream error %s", exc)
        return {"outcome": "UPSTREAM_ERROR", "called": True,
                "error": str(exc), "promise_paths": [],
                "promise_present": False}

    analyzed = analyze_promise(promise_response=promise_response,
                               node_id=node_id)
    return {
        "outcome":         analyzed.get("outcome", "PROMISE_RESPONSE_RECEIVED"),
        "called":          True,
        "promise_present": analyzed.get("promise_present", False),
        "promise_paths":   analyzed.get("promise_paths", []),
    }


async def consolidated_fc_gated(offer_id: str = "",
                                node_id: str = "",
                                partner_id: str = "",
                                partner_type: str = "",
                                state_code: str = "",
                                zip_code: str = "",
                                country_code: str = "",
                                aurum_response: Any = None,
                                **_: Any) -> dict[str, Any]:
    """Gated Eligibility Consolidated fetch.

    Mirrors ``DIAG-CONSOLIDATED-FC-01`` (``POST {base}/offer/consolidated``
    with the address + seller + offer body) when the Case 2 gate passes;
    returns ``CASE2_BLOCKED`` when the gate fails.
    """
    gate = case2_gate(aurum_response, node_id)
    if gate["blocked"]:
        logger.info(
            "consolidated_fc_gated: Case 2 BLOCKED — skipping Consolidated (%s)",
            gate["aurum_outcome"],
        )
        return _blocked_payload("CONSOLIDATED_FC", gate)

    base = _setting("LIMO_ONLINE_CONSOLIDATED_FC_BASE_URL")
    url = f"{base}/offer/consolidated"
    headers = {
        "Content-Type":          "application/json",
        "Accept":                "application/json",
        # Same reasoning as promise_gated — pin to gzip/deflate so a
        # malformed zstd frame cannot break JSON decoding.
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
    # Consolidated tail latency is bursty — the LB returns 408 when
    # an upstream task takes too long.  Give our client a generous
    # ceiling (90 s) and retry once on a 408 so a single transient
    # timeout does not break the cascade.
    consolidated_response: Any = None
    last_exc: Exception | None = None
    for attempt in (1, 2):
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                resp = await client.post(url, headers=headers, json=body)
                resp.raise_for_status()
                consolidated_response = resp.json()
                last_exc = None
                break
        except httpx.HTTPStatusError as exc:
            last_exc = exc
            if exc.response.status_code == 408 and attempt == 1:
                logger.info(
                    "consolidated_fc_gated: 408 from upstream — retrying once"
                )
                continue
            break
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            break

    if last_exc is not None:
        logger.warning("consolidated_fc_gated: upstream error %s", last_exc)
        return {"outcome": "UPSTREAM_ERROR", "called": True,
                "error": str(last_exc), "consolidated_paths": []}

    analyzed = analyze_consolidated_fc(
        consolidated_response=consolidated_response, node_id=node_id,
    )
    return {
        "outcome":                         analyzed.get("outcome", "CONSOLIDATED_FC_RESPONSE_RECEIVED"),
        "called":                          True,
        "consolidated_paths":              analyzed.get("consolidated_paths", []),
        "consolidated_available_node_ids": analyzed.get("consolidated_available_node_ids", []),
        "fulfillment_speed":               analyzed.get("fulfillment_speed"),
    }
