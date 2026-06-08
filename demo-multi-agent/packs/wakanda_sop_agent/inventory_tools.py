"""
Wakanda SOP Agent — inventory tools (BigQuery-backed implementations).

Each function is imported by a DIAG-* tool entry in tools.yaml.
Signatures and return shapes match what the tool executor and outcome_rules expect.
"""

from __future__ import annotations

import os
from typing import Any, Optional


# ── Shared helpers ────────────────────────────────────────────────────────────

def _get_bq_setup():
    """Return (client, data_project, tables) for all inventory tool functions.

    Credential chain:
      1. BQ_CREDENTIALS_PATH in config
      2. /etc/secrets/bigquerycredentials_eventops  (has bigquery.jobs.create)
      3. GCP_CREDENTIALS_PATH in config
      4. Application Default Credentials
    """
    from google.cloud import bigquery  # type: ignore
    from google.oauth2 import service_account  # type: ignore
    from agent_factory.infrastructure.settings import get_config

    cfg = get_config()
    bq_cfg = getattr(cfg, "wakanda_bigquery", None)
    data_project = (
        str(getattr(bq_cfg, "GCP_PROJECT_ID", "wakanda-gcp-prod"))
        if bq_cfg else "wakanda-gcp-prod"
    )
    bq_creds_path = (
        str(getattr(bq_cfg, "BQ_CREDENTIALS_PATH", "")) if bq_cfg else ""
    ) or "/etc/secrets/bigquerycredentials_eventops"
    gcp_creds_path = str(getattr(bq_cfg, "GCP_CREDENTIALS_PATH", "")) if bq_cfg else ""

    creds_path = bq_creds_path if os.path.exists(bq_creds_path) else gcp_creds_path
    if creds_path and os.path.exists(creds_path):
        creds = service_account.Credentials.from_service_account_file(
            creds_path, scopes=["https://www.googleapis.com/auth/cloud-platform"])
        client = bigquery.Client(project=creds.project_id, credentials=creds)
    else:
        client = bigquery.Client(project=data_project)

    def _tbl(key, default):
        val = str(getattr(bq_cfg, key, default)) if bq_cfg else default
        return f"`{data_project}.{val}`"

    tables = {
        "km_snapshot": _tbl("BQ_KILLMONGER_SNAPSHOT",
                             "killmonger_current.killmonger_current_snapshot"),
        "mb_fnfeed":   _tbl("BQ_MBAKU_FNFEED",
                             "mbaku_current.mbaku_current_fnfeed"),
        "mb_snapshot": _tbl("BQ_MBAKU_SNAPSHOT",
                             "mbaku_current.mbaku_current_snapshot"),
        "km_res":      _tbl("BQ_KILLMONGER_RESERVATION",
                             "killmonger_current.killmonger_current_reservation"),
    }
    return client, data_project, tables


def _resolve_node_id(node_id: str) -> str:
    """Convert 'store:N' to numeric node ID; return other IDs unchanged."""
    raw = str(node_id).strip()
    if raw.lower().startswith("store:"):
        store_num = raw.split(":", 1)[1].strip()
        try:
            return str(999900000 + int(store_num))
        except ValueError:
            return store_num
    return raw


# ── DIAG-NODE-01 ──────────────────────────────────────────────────────────────

def get_node_inventory(offer_id: str, node_id: str) -> dict[str, Any]:
    """Return inventory snapshot for an offer at a specific fulfilment node.

    Queries BigQuery killmonger + mbaku tables.
    Accepts store: prefix — store:N is converted to node 999900000 + N.

    Returns:
        {"status": "success", "data": <formatted string>} on success
        {"status": "no_data_found", "data": None} when the offer/node pair has no record
        {"status": "error", "data": None, "error": "..."} on failure
    """
    try:
        from google.cloud import bigquery  # type: ignore
    except ImportError:
        return {"status": "error", "data": None,
                "error": "google-cloud-bigquery is not installed"}

    try:
        client, data_project, tables = _get_bq_setup()
    except Exception as exc:
        return {"status": "error", "data": None, "error": str(exc)}

    node_id = _resolve_node_id(node_id)
    s_id = f"{offer_id}-fn-{node_id}"

    sql = f"""
SELECT sellingId AS offerId, km.fnId AS NodeId, fnType,
       km.f AS feed_qty, c AS completed_qty,
       r AS reserved_qty, s AS sellable_qty,
       mlu AS last_inventory_update, ifa, lock,
       accModes, accessModesVp, wfsEligible,
       mb.isPreOrderEligible AS isPreOrderEligible, isAltPath
FROM {tables['km_snapshot']} km
JOIN {tables['mb_fnfeed']} mb
  ON mb.sId = km.sellingId AND mb.fnId = km.fnId
WHERE km.sId = '{s_id}'
  AND km.partitionId >= 0
  AND mb.partitionId >= 0
"""
    try:
        rows = list(client.query(sql).result(timeout=55))
    except Exception as exc:
        return {"status": "error", "data": None, "error": str(exc)}

    if not rows:
        return {
            "status": "no_data_found",
            "data": None,
            "message": (
                f"No inventory record found for offer {offer_id} at node {node_id}. "
                "The offer may not be present in the current killmonger snapshot for this node."
            ),
        }

    row = dict(rows[0])
    feed_qty      = int(row.get("feed_qty") or 0)
    reserved_qty  = int(row.get("reserved_qty") or 0)
    completed_qty = int(row.get("completed_qty") or 0)
    sellable_qty  = int(row.get("sellable_qty") or 0)
    ifa           = str(row.get("ifa") or "").lower()
    fn_type       = str(row.get("fnType") or "N/A")
    last_update   = str(row.get("last_inventory_update") or "N/A")

    # Lock — may be a dict or string
    _lock_raw = row.get("lock")
    lock_str = str(_lock_raw) if _lock_raw and str(_lock_raw).lower() not in ("none", "null", "") else None

    def _lock_label(raw):
        if not raw:
            return "lock"
        try:
            import ast
            d = ast.literal_eval(raw) if isinstance(raw, str) else raw
            parts = []
            if d.get("lockType"):
                parts.append(d["lockType"])
            if d.get("lockedBy"):
                parts.append(f"placed by '{d['lockedBy']}'")
            return " ".join(parts) if parts else "lock"
        except Exception:
            return "lock"

    lock_label = _lock_label(lock_str)

    # accModes — REPEATED field; may come back as list
    _acc_raw = row.get("accModes")
    try:
        if hasattr(_acc_raw, "__len__") and not isinstance(_acc_raw, str):
            acc_modes = str(list(_acc_raw)) if len(_acc_raw) > 0 else None
        elif _acc_raw and str(_acc_raw).lower() not in ("none", "null", ""):
            acc_modes = str(_acc_raw)
        else:
            acc_modes = None
    except Exception:
        acc_modes = None

    _vp_raw = row.get("accessModesVp")
    vp_modes = (
        str(list(_vp_raw))
        if hasattr(_vp_raw, "__len__") and not isinstance(_vp_raw, str)
        else str(_vp_raw)
    )

    preorder_elig = row.get("isPreOrderEligible")

    # Plain-English narrative
    if ifa == "false":
        what_found = (
            f"Location {node_id} is currently switched off for this offer. "
            f"Even though there are {feed_qty} units recorded here, "
            "nothing can be sold from a disabled location."
        )
        conclusion = "This location is inactive. The offer is unavailable here because the location needs to be re-enabled."
        actions = (
            "- Contact the warehouse or location operations team to re-enable this fulfilment location.\n"
            "- Confirm the location was not intentionally deactivated before turning it back on."
        )
    elif feed_qty == 0:
        what_found = (
            f"This offer has no stock at location {node_id}. "
            "The supplier has not sent any inventory here."
        )
        conclusion = "The offer is unavailable because no stock has been received from the supplier at this location."
        actions = (
            "- Ask the supplier to send an inventory update for this offer at this location.\n"
            "- Check whether the stock feed is correctly set up to include this location."
        )
    elif sellable_qty <= 0 and lock_str:
        what_found = (
            f"This offer has {feed_qty} units at location {node_id} but is currently locked. "
            f"The lock type is '{lock_label}'. "
            f"There are {reserved_qty} units in pending orders and {completed_qty} already fulfilled."
        )
        conclusion = f"Stock is present but a {lock_label} is preventing it from being sold."
        actions = (
            f"- Ask the inventory operations team to remove the {lock_label}.\n"
            "- Confirm the lock was not placed intentionally before removing it."
        )
    elif sellable_qty <= 0:
        what_found = (
            f"This offer has {feed_qty} units at location {node_id} but none are available to sell — "
            f"{reserved_qty} unit{'s are' if reserved_qty != 1 else ' is'} held in pending orders "
            f"and {completed_qty} {'have' if completed_qty != 1 else 'has'} already been fulfilled."
        )
        conclusion = "All available units are tied up in existing orders."
        actions = (
            "- Ask the supplier to send more stock to this location.\n"
            "- Review pending orders for any that are stuck and could be cancelled."
        )
    elif not acc_modes:
        what_found = (
            f"This offer has {sellable_qty} units available at location {node_id} "
            "but it is not set up to be sold — sales eligibility settings are missing."
        )
        conclusion = "Stock is available but the offer is missing required sales eligibility settings."
        actions = (
            "- Contact the onboarding or catalogue team to configure sales eligibility for this offer.\n"
            "- They will need to set the correct sales access settings."
        )
    else:
        what_found = (
            f"This offer has {sellable_qty} units available at location {node_id} and is ready to sell. "
            f"Feed: {feed_qty} units total, {reserved_qty} in pending orders, {completed_qty} fulfilled."
        )
        conclusion = f"Everything looks fine at location {node_id}. If the offer is still not showing, the issue is elsewhere."
        actions = (
            "- No inventory action needed.\n"
            "- If the offer is still not purchasable on the site, contact the downstream fulfilment team."
        )

    formatted_data = (
        f"What We Found:\n{what_found}\n\n"
        f"Conclusion:\n{conclusion}\n\n"
        f"Recommended Actions:\n{actions}\n\n"
        f"Wakanda Analysis Details:\n"
        f"- Offer ID: {row.get('offerId')}\n"
        f"- Node ID: {row.get('NodeId')}\n"
        f"- Fulfillment Node Type: {fn_type}\n"
        f"- Feed Quantity: {feed_qty} units\n"
        f"- Reserved Quantity: {reserved_qty} units\n"
        f"- Completed Quantity: {completed_qty} units\n"
        f"- Sellable Quantity: {sellable_qty} units\n"
        f"- Node Enabled (ifa): {ifa}\n"
        f"- Last Inventory Update: {last_update}\n"
        f"- Active Lock: {lock_str or 'None'}\n"
        f"- Regular Eligibility (accModes): {acc_modes or 'not configured'}\n"
        f"- VirtualPack Eligibility (accessModesVp): {vp_modes}\n"
        f"- PreOrder Eligible: {preorder_elig}"
    )

    return {
        "status": "success",
        "offer_id": offer_id,
        "node_id": node_id,
        "data": formatted_data,
        "acc_modes": acc_modes,
        "vp_modes": vp_modes,
    }


# ── DIAG-RES-01 ───────────────────────────────────────────────────────────────

def get_node_reservations(offer_id: str, node_id: str) -> dict[str, Any]:
    """Return open reservations for an offer at a specific fulfilment node.

    Queries killmonger_current_reservation.

    Returns:
        {"status": "success", "data": <formatted string>} on success
        {"status": "no_data_found", "data": None} when no reservations exist
        {"status": "error", "data": None, "error": "..."} on failure
    """
    try:
        from google.cloud import bigquery  # type: ignore
    except ImportError:
        return {"status": "error", "data": None,
                "error": "google-cloud-bigquery is not installed"}

    try:
        client, data_project, tables = _get_bq_setup()
    except Exception as exc:
        return {"status": "error", "data": None, "error": str(exc)}

    node_id = _resolve_node_id(node_id)
    s_id = f"{offer_id}-fn-{node_id}"

    sql = f"""
SELECT coId AS order_id, sellingId AS offer_id, fnId AS node_id,
       s AS status, q AS reserved_qty, oq AS ordered_qty,
       updateTime, opd
FROM {tables['km_res']}
WHERE sId = '{s_id}'
  AND partitionId >= 0
  AND type = 'reservation'
  AND s IN ('reserved', 'partiallyShipped')
ORDER BY updateTime DESC
"""
    try:
        rows = list(client.query(sql).result(timeout=55))
    except Exception as exc:
        return {"status": "error", "data": None, "error": str(exc)}

    if not rows:
        return {
            "status": "no_data_found",
            "data": None,
            "total_rows": 0,
            "total_reserved_qty": 0,
        }

    records = [dict(r) for r in rows]
    total = len(records)
    total_reserved = sum(int(r.get("reserved_qty") or 0) for r in records)

    what_found = (
        f"There {'are' if total != 1 else 'is'} {total} order{'s' if total != 1 else ''} "
        f"with stock currently set aside ({total_reserved} unit{'s' if total_reserved != 1 else ''} reserved) "
        f"at node {node_id}."
    )
    conclusion = "Stock is being held for pending orders. Once these orders ship or are cancelled, that stock will become available again."
    actions = (
        "- Check that reserved orders are progressing through fulfilment.\n"
        "- Cancel any stuck reservations to release stock back to available."
    )
    analysis = (
        f"- Offer ID: {offer_id}\n"
        f"- Node ID: {node_id}\n"
        f"- Open Reservations: {total} order(s), {total_reserved} units"
    )

    row_lines = []
    for r in records[:20]:  # cap inline at 20
        parts = [
            f"Order: {r.get('order_id')}",
            f"Status: {r.get('status')}",
            f"Reserved Qty: {int(r.get('reserved_qty') or 0)}",
        ]
        if r.get("opd"):
            parts.append(f"OPD: {r['opd']}")
        row_lines.append("- " + " | ".join(parts))

    rows_section = "Open Reservation Details:\n" + "\n".join(row_lines)
    if total > 20:
        rows_section += f"\n... ({total - 20} more rows not shown)"

    formatted_data = (
        f"What We Found:\n{what_found}\n\n"
        f"Conclusion:\n{conclusion}\n\n"
        f"Recommended Actions:\n{actions}\n\n"
        f"Wakanda Analysis Details:\n{analysis}\n\n"
        f"{rows_section}"
    )

    return {
        "status": "success",
        "offer_id": offer_id,
        "node_id": node_id,
        "total_rows": total,
        "total_reserved_qty": total_reserved,
        "rows_section": rows_section,
        "data": formatted_data,
    }


# ── DIAG-EI-01 ────────────────────────────────────────────────────────────────

def get_ei_inventory(offer_id: str, node_id: str) -> dict[str, Any]:
    """Compare Wakanda inventory with Enterprise Inventory (EI) for an offer at a node.

    Routes to the appropriate EI table by node type (DC/FC/STORE/DSV/MARKETPLACE).
    Returns both Wakanda and EI quantities with a mismatch flag.

    Returns:
        {"status": "success", "data": <formatted string>} on success
        {"status": "not_applicable", "data": <message>} for unsupported node types
        {"status": "no_data_found", "data": None} when EI has no data
        {"status": "error", "data": None, "error": "..."} on failure
    """
    try:
        from google.cloud import bigquery  # type: ignore
    except ImportError:
        return {"status": "error", "data": None,
                "error": "google-cloud-bigquery is not installed"}

    try:
        client, data_project, tables = _get_bq_setup()
    except Exception as exc:
        return {"status": "error", "data": None, "error": str(exc)}

    node_id = _resolve_node_id(node_id)
    s_id = f"{offer_id}-fn-{node_id}"

    # Step 1: Get fnType from killmonger_snapshot
    fn_type_sql = f"""
SELECT fnType
FROM {tables['km_snapshot']}
WHERE sId = '{s_id}' AND partitionId >= 0
LIMIT 1
"""
    try:
        fn_rows = list(client.query(fn_type_sql).result(timeout=30))
    except Exception as exc:
        return {"status": "error", "data": None, "error": str(exc)}

    if not fn_rows:
        return {
            "status": "no_data_found",
            "data": None,
            "message": f"No killmonger record found for offer {offer_id} at node {node_id}.",
        }

    fn_type = str(dict(fn_rows[0]).get("fnType") or "UNKNOWN").upper()

    if fn_type not in ("DC", "FC", "STORE", "DSV", "MARKETPLACE"):
        msg = (
            f"Node type is {fn_type}, which is not DC, FC, STORE, DSV, or MARKETPLACE. "
            "EI inventory comparison is not applicable for this node type."
        )
        return {"status": "not_applicable", "data": msg, "fn_type": fn_type}

    # Step 2: Get Wakanda feed/reserved/completed/sellable quantities
    wakanda_sql = f"""
SELECT sellingId AS offerId, fnId AS nodeId,
       f AS feed_qty, r AS reserved_qty, c AS completed_qty,
       s AS sellable_qty, mlu AS last_inventory_update
FROM {tables['km_snapshot']}
WHERE sId = '{s_id}' AND partitionId >= 0
LIMIT 1
"""
    try:
        wk_rows = list(client.query(wakanda_sql).result(timeout=30))
    except Exception as exc:
        return {"status": "error", "data": None, "error": str(exc)}

    wk = dict(wk_rows[0]) if wk_rows else {}
    wakanda_feed      = int(wk.get("feed_qty") or 0)
    wakanda_reserved  = int(wk.get("reserved_qty") or 0)
    wakanda_completed = int(wk.get("completed_qty") or 0)
    wakanda_sellable  = int(wk.get("sellable_qty") or 0)
    wakanda_lut       = str(wk.get("last_inventory_update") or "N/A")

    # Formula: sellable = feed - reserved - completed
    sellable_formula = (
        f"{wakanda_feed} (feed) − {wakanda_reserved} (reserved)"
        f" − {wakanda_completed} (completed) = {wakanda_sellable}"
    )

    # Step 3: Build EI query based on node type
    if fn_type == "STORE":
        ei_node = str(int(node_id) - 999900000)
        ei_sql = f"""
SELECT nodeId AS ei_nodeId, itemIdentifierValue AS ei_offer,
       lastUpdatedTime AS ei_lut,
       SUM(CASE WHEN ags.state = 'EVENT' THEN ags.quantity ELSE 0 END) AS event_qty,
       SUM(CASE WHEN ags.state = 'AVAILABLE' THEN ags.quantity ELSE 0 END) AS regular_qty
FROM `wmt-omni-datalake-prod.wm_ei_tables.offerId_rollup_inventory_snapshot_store`
CROSS JOIN UNNEST(onhandInventory) AS oh
CROSS JOIN UNNEST(oh.inventory) AS ags
WHERE ags.state IN ('EVENT', 'AVAILABLE')
  AND countryCode = 'US'
  AND oh.locationArea IN ('STORE', 'MFC')
  AND itemIdentifierValue = '{offer_id}'
  AND nodeId = '{ei_node}'
GROUP BY nodeId, itemIdentifierValue, lastUpdatedTime
"""
    elif fn_type == "DSV":
        # Get GTIN first
        gtin_sql = f"""
SELECT DISTINCT gtin
FROM {tables['km_snapshot']}
WHERE partitionId >= 0 AND sellingId = '{offer_id}' AND gtin IS NOT NULL
LIMIT 1
"""
        gtin_rows = list(client.query(gtin_sql).result(timeout=20))
        gtin_value = str(dict(gtin_rows[0]).get("gtin") or "") if gtin_rows else ""
        if not gtin_value:
            return {
                "status": "no_data_found",
                "data": None,
                "message": f"No GTIN found for offer {offer_id} at DSV node {node_id}.",
            }
        ei_node = node_id
        ei_sql = f"""
SELECT DISTINCT ei.nodeId AS ei_nodeId, ei.itemIdentifierValue AS ei_offer,
       SUM(ags.quantity) AS ei_qty, ei.lastUpdatedTime AS ei_lut
FROM `wmt-omni-datalake-prod.wm_ei_tables.ei_wmt_ecom_owned_streams_v2_snapshot` ei,
     UNNEST(ei.onhandInventory) oh,
     UNNEST(oh.inventory) ags
WHERE ei.countryCode = 'US'
  AND ags.state IN ('AVAILABLE', 'PICKED')
  AND itemIdentifierValue = '{gtin_value}'
  AND nodeId = '{ei_node}'
GROUP BY ei.nodeId, ei.itemIdentifierValue, ei.lastUpdatedTime
"""
    elif fn_type == "MARKETPLACE":
        seller_sql = f"""
SELECT SLR_OFFR_ID
FROM `wmt-edw-prod.WW_PRODUCT_DL_VM.OFFR`
WHERE OFFR_ID = '{offer_id}'
LIMIT 1
"""
        sel_rows = list(client.query(seller_sql).result(timeout=20))
        seller_offer_id = str(dict(sel_rows[0]).get("SLR_OFFR_ID") or "") if sel_rows else ""
        if not seller_offer_id:
            return {
                "status": "no_data_found",
                "data": None,
                "message": f"No seller offer ID found for offer {offer_id} at MARKETPLACE node {node_id}.",
            }
        ei_node = node_id
        ei_sql = f"""
SELECT ei.nodeId AS ei_nodeId, ei.itemIdentifierValue AS ei_offer,
       SUM(ags.quantity) AS ei_qty, ei.lastUpdatedTime AS ei_lut
FROM `wmt-omni-datalake-prod.wm_ei_tables.ei_wmt_ecom_3p_v2_snapshot` ei,
     UNNEST(ei.onhandInventory) oh,
     UNNEST(oh.inventory) ags
WHERE ei.countryCode = 'US'
  AND ags.state IN ('AVAILABLE', 'PICKED')
  AND itemIdentifierValue = '{seller_offer_id}'
  AND nodeId = '{node_id}'
GROUP BY ei.nodeId, ei.itemIdentifierValue, ei.lastUpdatedTime
"""
    else:
        # DC / FC
        ei_node = node_id
        ei_sql = f"""
SELECT ei.nodeId AS ei_nodeId, ei.itemIdentifierValue AS ei_offer,
       SUM(ags.quantity) AS ei_qty, ei.lastUpdatedTime AS ei_lut
FROM `wmt-omni-datalake-prod.wm_ei_tables.offerId_rollup_inventory_snapshot_fc` ei,
     UNNEST(ei.onhandInventory) oh,
     UNNEST(oh.inventory) ags
WHERE ei.countryCode = 'US'
  AND ags.state IN ('AVAILABLE', 'PICKED')
  AND ei.itemIdentifierValue = '{offer_id}'
  AND nodeId = '{node_id}'
GROUP BY ei.nodeId, ei.itemIdentifierValue, ei.lastUpdatedTime
"""

    try:
        ei_rows = list(client.query(ei_sql).result(timeout=55))
    except Exception as exc:
        return {"status": "error", "data": None, "error": str(exc)}

    if not ei_rows:
        ei_qty = 0
        ei_lut = "N/A"
        ei_summary = (
            f"No EI inventory data found for offer {offer_id} at node {node_id} ({fn_type}). "
            "The offer may not be present in the EI system at this node."
        )
    else:
        ei_row = dict(ei_rows[0])
        ei_lut = str(ei_row.get("ei_lut") or "N/A")
        if fn_type == "STORE":
            event_qty   = int(ei_row.get("event_qty") or 0)
            regular_qty = int(ei_row.get("regular_qty") or 0)
            ei_qty      = event_qty + regular_qty
            ei_summary  = (
                f"EI Inventory (STORE): Node={ei_row.get('ei_nodeId')}, "
                f"EVENT={event_qty}, AVAILABLE={regular_qty}, Total={ei_qty}, LUT={ei_lut}"
            )
        else:
            ei_qty = int(ei_row.get("ei_qty") or 0)
            ei_summary = (
                f"EI Inventory ({fn_type}): Node={ei_row.get('ei_nodeId')}, "
                f"Available={ei_qty}, LUT={ei_lut}"
            )

    diff = wakanda_sellable - ei_qty
    if abs(diff) == 0:
        status_flag = "✅ MATCH"
        comparison  = f"Both Wakanda and EI show {wakanda_sellable} units. No discrepancy."
    elif diff > 0:
        status_flag = "⚠️ WAKANDA > EI"
        # Check whether reservations/completed explain why EI is lower
        reserved_explains = (wakanda_reserved + wakanda_completed) >= diff
        if reserved_explains and (wakanda_reserved > 0 or wakanda_completed > 0):
            root_cause = (
                f"EI may not yet reflect {wakanda_reserved} reserved and "
                f"{wakanda_completed} completed unit(s) that Wakanda has already accounted for."
            )
        else:
            root_cause = "Reserved/completed orders do not fully account for the gap — further investigation may be needed."
        comparison = (
            f"Wakanda sellable={wakanda_sellable}, EI available={ei_qty}. "
            f"Difference: +{diff} units in Wakanda's favour.\n"
            f"Root cause: {root_cause}"
        )
    else:
        status_flag = "⚠️ EI > WAKANDA"
        # Check whether reservations + completed fully explain why Wakanda sellable is lower
        reserved_explains = (wakanda_reserved + wakanda_completed) >= abs(diff)
        if reserved_explains and (wakanda_reserved > 0 or wakanda_completed > 0):
            root_cause = (
                f"Wakanda sellable is lower because {wakanda_reserved} unit(s) are reserved "
                f"and {wakanda_completed} unit(s) are completed. "
                f"Sellable = {wakanda_feed} (feed) − {wakanda_reserved} (reserved) "
                f"− {wakanda_completed} (completed) = {wakanda_sellable}."
            )
        else:
            root_cause = (
                "Reserved/completed orders do not fully account for the gap — "
                "further investigation may be needed."
            )
        comparison = (
            f"EI available={ei_qty}, Wakanda sellable={wakanda_sellable}. "
            f"Difference: {abs(diff)} units in EI's favour.\n"
            f"Root cause: {root_cause}"
        )

    from datetime import datetime, timezone
    formatted_data = (
        f"📊 Wakanda vs EI Inventory Comparison — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
        f"Offer ID : {offer_id}\n"
        f"Node ID  : {node_id}\n"
        f"Node Type: {fn_type}\n\n"
        f"Comparison Result:\n{comparison}\n\n"
        f"Status: {status_flag}\n\n"
        f"Wakanda Inventory:\n"
        f"  - Feed Quantity   : {wakanda_feed} units\n"
        f"  - Reserved Qty    : {wakanda_reserved} units\n"
        f"  - Completed Qty   : {wakanda_completed} units\n"
        f"  - Sellable Qty    : {wakanda_sellable} units  [{sellable_formula}]\n"
        f"  - Last Update     : {wakanda_lut}\n\n"
        f"EI Inventory:\n  - {ei_summary}"
    )

    return {
        "status": "success",
        "offer_id": offer_id,
        "node_id": node_id,
        "fn_type": fn_type,
        "wakanda_feed": wakanda_feed,
        "wakanda_reserved": wakanda_reserved,
        "wakanda_completed": wakanda_completed,
        "wakanda_sellable": wakanda_sellable,
        "ei_available": ei_qty,
        "difference": diff,
        "status_flag": status_flag,
        "data": formatted_data,
    }


# ── DIAG-PATH-01 ──────────────────────────────────────────────────────────────

def get_path_eligibility(offer_id: str, node_id: str) -> dict[str, Any]:
    """Return path eligibility (accModes / accessModesVp) for an offer at a node.

    Returns:
        {"status": "success", "data": <formatted string>} on success
        {"status": "no_data_found", "data": None} when no eligibility record exists
        {"status": "error", "data": None, "error": "..."} on failure
    """
    try:
        from google.cloud import bigquery  # type: ignore
    except ImportError:
        return {"status": "error", "data": None,
                "error": "google-cloud-bigquery is not installed"}

    try:
        client, data_project, tables = _get_bq_setup()
    except Exception as exc:
        return {"status": "error", "data": None, "error": str(exc)}

    node_id = _resolve_node_id(node_id)

    sql = f"""
SELECT fn.accModes AS regular_eligibility,
       fn.accessModesVp AS vp_eligibility
FROM {tables['mb_fnfeed']} fn
WHERE fn.partitionId >= 0
  AND fn.sId = '{offer_id}'
  AND fn.fnId = '{node_id}'
LIMIT 1
"""
    try:
        rows = list(client.query(sql).result(timeout=30))
    except Exception as exc:
        return {"status": "error", "data": None, "error": str(exc)}

    if not rows:
        return {
            "status": "no_data_found",
            "data": None,
            "acc_modes": None,
            "vp_modes": "[]",
            "has_national_carrier": False,
            "has_regular": False,
            "has_vp": False,
            "global_rollup_note": (
                "No eligibility record found in mb_fnfeed for this offer+node combination."
            ),
        }

    row = dict(rows[0])
    acc_raw = row.get("regular_eligibility")
    vp_raw  = row.get("vp_eligibility")

    try:
        acc_modes = str(list(acc_raw)) if acc_raw is not None else None
    except Exception:
        acc_modes = str(acc_raw) if acc_raw is not None else None

    try:
        vp_modes = str(list(vp_raw)) if vp_raw is not None else "[]"
    except Exception:
        vp_modes = str(vp_raw) if vp_raw is not None else "[]"

    has_regular = bool(acc_modes and acc_modes not in ("None", "[]", ""))
    has_vp      = bool(vp_modes and vp_modes not in ("None", "[]", ""))

    # Determine whether national_carrier eligibility is present.
    # national_carrier in accModes is required for node inventory to roll up
    # to the global customer-facing sellable quantity.
    has_national_carrier = bool(
        has_regular and "national_carrier" in str(acc_modes)
    )

    if has_regular and has_national_carrier:
        global_rollup_note = (
            "national_carrier eligibility is present — "
            "node inventory WILL roll up to global sellable."
        )
    elif has_regular and not has_national_carrier:
        global_rollup_note = (
            "national_carrier eligibility is ABSENT from accModes — "
            "node inventory will NOT roll up to global sellable."
        )
    elif has_vp:
        global_rollup_note = (
            "VirtualPack-only eligibility (accessModesVp is set, accModes is empty) — "
            "VirtualPack inventory does NOT contribute to global sellable."
        )
    else:
        global_rollup_note = (
            "No eligibility modes configured — "
            "inventory cannot be visible at any sales path."
        )

    if has_regular and has_vp:
        summary = f"Offer {offer_id} at node {node_id} is eligible for both regular and VirtualPack sales paths."
    elif has_regular:
        summary = f"Offer {offer_id} at node {node_id} is eligible for regular sales only."
    elif has_vp:
        summary = f"Offer {offer_id} at node {node_id} is eligible for VirtualPack sales only."
    else:
        summary = f"Offer {offer_id} at node {node_id} has no active eligibility modes configured."

    formatted_data = (
        f"Path Eligibility for Offer {offer_id} at Node {node_id}\n\n"
        f"Summary: {summary}\n\n"
        f"Regular Eligibility (accModes)         : {acc_modes or '(none)'}\n"
        f"VirtualPack Eligibility (accessModesVp): {vp_modes}\n\n"
        f"Global Rollup Diagnosis: {global_rollup_note}"
    )

    return {
        "status": "success",
        "offer_id": offer_id,
        "node_id": node_id,
        "acc_modes": acc_modes,
        "vp_modes": vp_modes,
        "has_national_carrier": has_national_carrier,
        "has_regular": has_regular,
        "has_vp": has_vp,
        "global_rollup_note": global_rollup_note,
        "data": formatted_data,
    }


# ── DIAG-LOCK-01 ──────────────────────────────────────────────────────────────

def get_node_lock_details(offer_id: str, node_id: str) -> dict[str, Any]:
    """Return active inventory lock details for an offer at a specific node.

    Queries the lock field in killmonger_snapshot.

    Returns:
        {"status": "success", "data": <formatted string>} on success
        {"status": "no_data_found", "data": None} when no lock record exists
        {"status": "error", "data": None, "error": "..."} on failure
    """
    try:
        from google.cloud import bigquery  # type: ignore
    except ImportError:
        return {"status": "error", "data": None,
                "error": "google-cloud-bigquery is not installed"}

    try:
        client, data_project, tables = _get_bq_setup()
    except Exception as exc:
        return {"status": "error", "data": None, "error": str(exc)}

    node_id = _resolve_node_id(node_id)
    s_id = f"{offer_id}-fn-{node_id}"

    sql = f"""
SELECT lock, fnType
FROM {tables['km_snapshot']}
WHERE sId = '{s_id}' AND partitionId >= 0
LIMIT 1
"""
    try:
        rows = list(client.query(sql).result(timeout=30))
    except Exception as exc:
        return {"status": "error", "data": None, "error": str(exc)}

    if not rows:
        return {
            "status": "no_data_found",
            "data": None,
            "message": f"No inventory snapshot found for offer {offer_id} at node {node_id}.",
        }

    row     = dict(rows[0])
    raw_lock = row.get("lock")
    fn_type  = str(row.get("fnType") or "").upper()

    if raw_lock is None or str(raw_lock).lower() in ("none", "null", "nan", ""):
        return {
            "status": "success",
            "offer_id": offer_id,
            "node_id": node_id,
            "lock_present": False,
            "data": (
                f"No active lock found for offer {offer_id} at node {node_id}. "
                "Inventory is not restricted by any lock."
            ),
        }

    try:
        import ast
        lock_dict = ast.literal_eval(str(raw_lock)) if isinstance(raw_lock, str) else raw_lock
    except Exception:
        lock_dict = {}

    lock_type        = lock_dict.get("lockType", "Unknown")
    locked_by        = lock_dict.get("lockedBy", "N/A")
    locked_at        = lock_dict.get("lockedAt", "N/A")
    max_lock_age     = lock_dict.get("maxLockAge", "N/A")
    unlock_on_update = lock_dict.get("unlockOnInventoryUpdate", False)
    is_modified      = lock_dict.get("isModifiedByInventoryUpdate", False)
    cancel_reason    = lock_dict.get("cancellationReasonCode")
    is_store         = fn_type == "STORE" or node_id.startswith("9999")

    if lock_type == "BusinessLock":
        summary = (
            f"Offer {offer_id} at node {node_id} has an active BusinessLock placed by {locked_by}. "
            "This lock must be manually removed by the Business team."
        )
    elif lock_type in ("SmartNilPickLock", "NilPickLock"):
        summary = (
            f"Offer {offer_id} at node {node_id} has an active {lock_type}. "
            "This lock will be automatically released on the next inventory update from FMS."
            + (f" For stores, released once maxLockAge ({max_lock_age}) has passed." if is_store else "")
        )
    elif lock_type == "Backorder":
        summary = (
            f"Offer {offer_id} at node {node_id} has an active Backorder lock. "
            "This lock will be automatically released on the next inventory update."
            + (f" For stores, released once maxLockAge ({max_lock_age}) has passed." if is_store else "")
        )
    else:
        summary = (
            f"Offer {offer_id} at node {node_id} has an active {lock_type} lock placed by {locked_by}. "
            "Review the lock details and contact the responsible team if manual intervention is needed."
        )

    lock_lines = (
        f"  lockedBy: {locked_by}\n"
        f"  lockedAt: {locked_at}\n"
        f"  lockType: {lock_type}\n"
        f"  maxLockAge: {max_lock_age}\n"
        f"  unlockOnInventoryUpdate: {unlock_on_update}\n"
        f"  isModifiedByInventoryUpdate: {is_modified}"
    )
    if cancel_reason:
        lock_lines += f"\n  cancellationReasonCode: {cancel_reason}"

    formatted_data = f"{summary}\n\nLock Details:\n{lock_lines}"

    return {
        "status": "success",
        "offer_id": offer_id,
        "node_id": node_id,
        "lock_present": True,
        "lock_type": lock_type,
        "data": formatted_data,
    }


# ── DIAG-BULK-01 ──────────────────────────────────────────────────────────────

def get_offer_level_nodes_inventory(offer_id: str) -> dict[str, Any]:
    """Return inventory across all fulfilment nodes mapped to an offer.

    Returns:
        {"status": "success", "data": <formatted string>} on success
        {"status": "no_data_found", "data": None} when the offer has no node mappings
        {"status": "error", "data": None, "error": "..."} on failure
    """
    try:
        from google.cloud import bigquery  # type: ignore
    except ImportError:
        return {"status": "error", "data": None,
                "error": "google-cloud-bigquery is not installed"}

    try:
        client, data_project, tables = _get_bq_setup()
    except Exception as exc:
        return {"status": "error", "data": None, "error": str(exc)}

    sql = f"""
SELECT DISTINCT fn.sId AS offer_id, fn.fnId AS node_id,
       luf AS last_updated_feed,
       fn.accModes AS regular_eligibility,
       fn.accessModesVp AS vp_eligibility,
       m.f AS sellable_qty
FROM {tables['mb_fnfeed']} fn,
     UNNEST(fn.m) AS m
WHERE fn.partitionId >= 0
  AND fn.sId = '{offer_id}'
ORDER BY node_id
"""
    try:
        rows = list(client.query(sql).result(timeout=55))
    except Exception as exc:
        return {"status": "error", "data": None, "error": str(exc)}

    if not rows:
        return {
            "status": "no_data_found",
            "data": None,
            "message": f"No node inventory data found for offer {offer_id}.",
        }

    records      = [dict(r) for r in rows]
    total_nodes  = len(records)
    total_sellable = sum(int(r.get("sellable_qty") or 0) for r in records)

    what_found = (
        f"Offer {offer_id} is mapped to {total_nodes} fulfilment node{'s' if total_nodes != 1 else ''} "
        f"with a combined sellable quantity of {total_sellable} units across all locations."
    )
    conclusion = (
        f"The offer has active inventory across {total_nodes} node{'s' if total_nodes != 1 else ''}. "
        "Review the node list for per-node eligibility and sellable quantities."
    )
    actions = (
        "- For detailed lock/eligibility info at a specific node, use the node inventory tool.\n"
        "- Review nodes with zero sellable quantity to identify restocking needs."
    )

    # Show first 10 nodes inline
    node_lines = []
    for r in records[:10]:
        reg_elig = r.get("regular_eligibility")
        try:
            reg_str = str(list(reg_elig)) if reg_elig is not None else "(none)"
        except Exception:
            reg_str = str(reg_elig) if reg_elig is not None else "(none)"
        qty = int(r.get("sellable_qty") or 0)
        node_lines.append(
            f"- Node: {r['node_id']} | Sellable Qty: {qty} | Eligibility: {reg_str}"
        )

    nodes_section = (
        f"Node Inventory (showing {min(10, total_nodes)} of {total_nodes}):\n"
        + "\n".join(node_lines)
    )
    if total_nodes > 10:
        nodes_section += f"\n... ({total_nodes - 10} more nodes not shown)"

    formatted_data = (
        f"What We Found:\n{what_found}\n\n"
        f"Conclusion:\n{conclusion}\n\n"
        f"Recommended Actions:\n{actions}\n\n"
        f"Wakanda Analysis Details:\n"
        f"- Offer ID: {offer_id}\n"
        f"- Total Nodes Mapped: {total_nodes}\n"
        f"- Total Sellable Qty (all nodes): {total_sellable} units\n\n"
        f"{nodes_section}"
    )

    return {
        "status": "success",
        "offer_id": offer_id,
        "total_nodes": total_nodes,
        "total_sellable_qty": total_sellable,
        "data": formatted_data,
    }


# ── DIAG-EVENT-01 ─────────────────────────────────────────────────────────────

def get_event_inventory(
    offer_ids: list[str],
    event_id: str = "",
    event_type: str = "",
    start_time: str = "",
    end_time: str = "",
    limit: int = 100,
) -> dict[str, Any]:
    """Validate inventory for a list of offers within a specific event window.

    Returns:
        {"status": "success", "data": <formatted string>} on success
        {"status": "no_data_found", "data": None} when no event inventory records exist
        {"status": "error", "data": None, "error": "..."} on failure
    """
    try:
        from google.cloud import bigquery  # type: ignore
    except ImportError:
        return {"status": "error", "data": None,
                "error": "google-cloud-bigquery is not installed"}

    if not offer_ids or not isinstance(offer_ids, list):
        return {"status": "error", "data": None,
                "error": "offer_ids must be a non-empty list"}

    # Basic validation: keep only non-empty strings
    validated_ids = [str(oid).strip() for oid in offer_ids if str(oid).strip()]
    if not validated_ids:
        return {"status": "error", "data": None,
                "error": "No valid offer IDs provided after validation."}

    try:
        client, data_project, tables = _get_bq_setup()
    except Exception as exc:
        return {"status": "error", "data": None, "error": str(exc)}

    event_id_label    = event_id.strip() if event_id and event_id.strip() else "matbot_event_validation"
    formatted_ids     = ", ".join(f"'{oid}'" for oid in validated_ids)

    summary_sql = f"""
SELECT
  COUNTIF(m.s_national > 0)    AS Inventory_Available,
  COUNTIF(m.s_national <= 0)   AS Inventory_Not_Available,
  COUNTIF(m.s_national_vp > 0) AS Inventory_Available_VirtualPack,
  COUNTIF(m.s_wfs > 0)         AS Inventory_Available_WFS,
  COUNTIF(
    EXISTS(
      SELECT 1 FROM UNNEST(a.sCap) AS sc
      WHERE sc.quantity > 0
        AND (sc.endCap IS NULL OR SAFE.PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%E*S%Ez', sc.endCap) >= CURRENT_TIMESTAMP())
    )
  ) AS SalesCap,
  COUNTIF(
    EXISTS(
      SELECT 1 FROM UNNEST(a.sCap) AS sc
      WHERE sc.quantity = 0
        AND (sc.endCap IS NULL OR SAFE.PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%E*S%Ez', sc.endCap) >= CURRENT_TIMESTAMP())
    )
  ) AS Zero_SalesCap,
  COUNTIF(a.isPreOrderEligible = TRUE) AS PreOrder_Eligible_Items,
  ARRAY_AGG(
    CASE WHEN m.s_national <= 0 THEN a.sId END
    IGNORE NULLS
  ) AS Offers_Without_Inventory,
  ARRAY_AGG(
    CASE WHEN EXISTS(
      SELECT 1 FROM UNNEST(a.sCap) AS sc
      WHERE sc.quantity = 0
        AND (sc.endCap IS NULL OR SAFE.PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%E*S%Ez', sc.endCap) >= CURRENT_TIMESTAMP())
    ) THEN a.sId END
    IGNORE NULLS
  ) AS Offers_With_Zero_SalesCap,
  ARRAY_AGG(
    CASE WHEN a.isPreOrderEligible = TRUE
    THEN STRUCT(a.sId AS offer_id, a.releaseDate AS release_date) END
    IGNORE NULLS
  ) AS PreOrder_Offers
FROM {tables['mb_snapshot']} AS a
LEFT JOIN UNNEST(a.m) AS m
WHERE a.sId IN ({formatted_ids})
  AND a.partitionId > -1
"""

    try:
        summary_rows = list(client.query(summary_sql).result(timeout=55))
    except Exception as exc:
        return {"status": "error", "data": None, "error": str(exc)}

    if not summary_rows:
        return {"status": "no_data_found", "data": None}

    s = dict(summary_rows[0])
    inv_available = int(s.get("Inventory_Available") or 0)
    inv_missing   = int(s.get("Inventory_Not_Available") or 0)
    inv_vp        = int(s.get("Inventory_Available_VirtualPack") or 0)
    inv_wfs       = int(s.get("Inventory_Available_WFS") or 0)
    salescap      = int(s.get("SalesCap") or 0)
    zero_salescap = int(s.get("Zero_SalesCap") or 0)
    preorder      = int(s.get("PreOrder_Eligible_Items") or 0)
    offers_without = [
        str(oid) for oid in (s.get("Offers_Without_Inventory") or [])
        if oid is not None and str(oid) != "nan"
    ]
    offers_zero_cap = [
        str(oid) for oid in (s.get("Offers_With_Zero_SalesCap") or [])
        if oid is not None and str(oid) != "nan"
    ]
    preorder_offers = [
        {
            "offer_id": str(row.get("offer_id") or ""),
            "release_date": str(row.get("release_date") or "N/A"),
        }
        for row in (s.get("PreOrder_Offers") or [])
        if row is not None and row.get("offer_id")
    ]

    total_queried = len(validated_ids)

    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    lines: list[str] = [
        f"📊 Event Inventory Summary — {ts} UTC",
        "",
        f"Total Event Offers: {total_queried}",
        f"  ✅ Inventory Available: {inv_available}",
        f"  ❌ Inventory Not Available: {inv_missing}",
        f"  📦 Available (VirtualPack): {inv_vp}",
        f"  🏭 Available (WFS): {inv_wfs}",
        "",
        "SalesCaps:",
        f"  🔖 Non-Zero SalesCap (qty > 0): {salescap}",
        f"  ⛔ Zero SalesCap (blocked): {zero_salescap}",
        "",
        "PreOrder Status:",
        f"  🛍️ PreOrder Eligible: {preorder}",
    ]

    if offers_without:
        lines += [
            "",
            f"🚫 Offers Without Inventory ({len(offers_without)}):",
        ]
        for oid in offers_without[:20]:
            lines.append(f"    • {oid}")
        if len(offers_without) > 20:
            lines.append(f"    ... ({len(offers_without) - 20} more not shown)")
    else:
        lines += [
            "",
            "✅ All queried offers have inventory available.",
        ]

    if offers_zero_cap:
        lines += [
            "",
            f"⛔ Offers Blocked by Zero SalesCap ({len(offers_zero_cap)}):",
        ]
        for oid in offers_zero_cap[:20]:
            lines.append(f"    • {oid}")
        if len(offers_zero_cap) > 20:
            lines.append(f"    ... ({len(offers_zero_cap) - 20} more not shown)")

    if preorder_offers:
        lines += [
            "",
            f"🛍️ PreOrder Eligible Offers ({len(preorder_offers)}):",
        ]
        for item in preorder_offers[:20]:
            lines.append(f"    • {item['offer_id']}  (Release Date: {item['release_date']})")
        if len(preorder_offers) > 20:
            lines.append(f"    ... ({len(preorder_offers) - 20} more not shown)")

    formatted_data = "\n".join(lines)

    return {
        "status": "success",
        "event_id": event_id_label,
        "total_offers": total_queried,
        "inventory_available": inv_available,
        "inventory_not_available": inv_missing,
        "zero_salescap_count": zero_salescap,
        "data": formatted_data,
    }


# ── DIAG-ORDER-01 ─────────────────────────────────────────────────────────────

def get_order_status(offer_id: str, node_id: str, order_id: str) -> dict[str, Any]:
    """Return order status and fulfillment details for a specific reservation.

    Returns:
        {"status": "success", "data": <formatted string>} on success
        {"status": "no_data_found", "data": None} when the order is not found
        {"status": "error", "data": None, "error": "..."} on failure
    """
    try:
        from google.cloud import bigquery  # type: ignore
    except ImportError:
        return {"status": "error", "data": None,
                "error": "google-cloud-bigquery is not installed"}

    try:
        client, data_project, tables = _get_bq_setup()
    except Exception as exc:
        return {"status": "error", "data": None, "error": str(exc)}

    node_id = _resolve_node_id(node_id)
    s_id    = f"{offer_id}-fn-{node_id}"

    sql = f"""
SELECT sellingId, fnId, coId, opd, s, q, lu, fpc
FROM {tables['km_res']}
WHERE sId = '{s_id}' AND partitionId >= 0 AND coId = '{order_id}'
"""
    try:
        rows = list(client.query(sql).result(timeout=55))
    except Exception as exc:
        return {"status": "error", "data": None, "error": str(exc)}

    if not rows:
        return {
            "status": "no_data_found",
            "data": None,
            "message": f"No reservation data found for order {order_id} at offer {offer_id} / node {node_id}.",
        }

    row          = dict(rows[0])
    order_status = str(row.get("s") or "UNKNOWN")
    qty          = int(row.get("q") or 0)

    if order_status.upper() in ("RESERVED", "PENDING"):
        what_found = (
            f"Order {order_id} is currently active and waiting to be fulfilled — "
            f"{qty} unit{'s are' if qty != 1 else ' is'} being held for it."
        )
        conclusion = "This order is in progress. No stock issues have been found."
        actions    = "- No action needed if the order is progressing normally."
    elif order_status.upper() == "COMPLETED":
        what_found = (
            f"Order {order_id} has been completed — {qty} unit{'s were' if qty != 1 else ' was'} fulfilled."
        )
        conclusion = "This order is fully done."
        actions    = "- No action needed — the order is complete."
    elif order_status.upper() == "CANCELLED":
        what_found = f"Order {order_id} has been cancelled."
        conclusion = "Confirm that the held stock was released back to available."
        actions    = "- Check that stock was released correctly after cancellation."
    else:
        what_found = f"Order {order_id} has status '{order_status}' ({qty} units)."
        conclusion = f"The order status '{order_status}' needs to be reviewed."
        actions    = "- Escalate to the order management team if the status looks incorrect."

    formatted_data = (
        f"What We Found:\n{what_found}\n\n"
        f"Conclusion:\n{conclusion}\n\n"
        f"Recommended Actions:\n{actions}\n\n"
        f"Wakanda Analysis Details:\n"
        f"- Selling ID: {row.get('sellingId')}\n"
        f"- Fulfillment Node ID: {row.get('fnId')}\n"
        f"- Customer Order ID: {row.get('coId')}\n"
        f"- Order Promising Date: {row.get('opd')}\n"
        f"- Status: {order_status}\n"
        f"- Quantity: {qty} units\n"
        f"- Last Order Update: {row.get('lu')}\n"
        f"- Fulfillment Path Code: {row.get('fpc')}"
    )

    return {
        "status": "success",
        "offer_id": offer_id,
        "node_id": node_id,
        "order_id": order_id,
        "data": formatted_data,
    }


# ── DIAG-CAP-01 ───────────────────────────────────────────────────────────────

def get_salescap_details(
    offer_ids: list[str],
    node_id: str = "",
    cap_type: str = "",
) -> dict[str, Any]:
    """Return active salescap details for one or more offers.

    Returns:
        {"status": "success", "data": <list of per-offer dicts>} on success
        {"status": "no_data_found", "data": None} when no salescap records exist
        {"status": "error", "data": None, "error": "..."} on failure
    """
    try:
        from google.cloud import bigquery  # type: ignore
    except ImportError:
        return {"status": "error", "data": None,
                "error": "google-cloud-bigquery is not installed"}

    if not offer_ids or not isinstance(offer_ids, list):
        return {"status": "error", "data": None,
                "error": "offer_ids must be a non-empty list."}

    try:
        client, data_project, tables = _get_bq_setup()
    except Exception as exc:
        return {"status": "error", "data": None, "error": str(exc)}

    formatted_ids = ", ".join(f"'{oid}'" for oid in offer_ids)

    sql = f"""
SELECT
    a.sId,
    a.r AS Global_Reservations,
    a.b AS Backorder,
    m.s_national AS Inventory_Available,
    m.s_national_vp AS Inventory_Available_VirtualPack,
    m.s_wfs AS Inventory_Available_WFS,
    a.isPreOrderEligible AS PreOrder_Eligible,
    a.releaseDate AS Release_Date,
    m.acap AS Access_Capacity,
    sCap.monitorKey AS monitorKey,
    sCap.startCap AS startCap,
    sCap.endCap AS endCap,
    sCap.quantity AS cap_quantity,
    sCap.sold AS cap_sold
FROM {tables['mb_snapshot']} AS a
JOIN UNNEST(a.m) AS m
LEFT JOIN UNNEST(a.sCap) AS sCap
WHERE a.sId IN ({formatted_ids})
  AND partitionId > -1
  AND (sCap.endCap IS NULL
       OR SAFE.PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%E*S%Ez', sCap.endCap) >= CURRENT_TIMESTAMP())
"""
    try:
        rows = list(client.query(sql).result(timeout=55))
    except Exception as exc:
        return {"status": "error", "data": None, "error": str(exc)}

    if not rows:
        return {"status": "no_data_found", "data": None}

    records = [dict(r) for r in rows]

    # Group by offer ID
    from collections import defaultdict
    groups: dict[str, list] = defaultdict(list)
    for r in records:
        groups[str(r["sId"])].append(r)

    results = []
    for oid, group in groups.items():
        first       = group[0]
        inv_avail   = first.get("Inventory_Available")
        inv_vp      = first.get("Inventory_Available_VirtualPack")
        inv_wfs     = first.get("Inventory_Available_WFS")

        zero_caps, active_caps = [], []
        for r in group:
            if r.get("monitorKey") is None:
                continue
            qty  = int(r.get("cap_quantity") or 0)
            sold = int(r.get("cap_sold") or 0)
            cap  = {
                "monitorKey": str(r["monitorKey"]),
                "startCap":   str(r.get("startCap") or ""),
                "endCap":     str(r.get("endCap") or ""),
                "quantity":   qty,
                "sold":       sold,
            }
            if qty == 0:
                zero_caps.append(cap)
            else:
                active_caps.append(cap)

        has_active = len(active_caps) > 0
        has_zero   = len(zero_caps) > 0
        total_caps = len(active_caps) + len(zero_caps)

        if has_active and has_zero:
            salescap_status = f"BOTH active ({len(active_caps)}) AND zero ({len(zero_caps)}) salescaps"
        elif has_active:
            salescap_status = f"{len(active_caps)} active salescap(s)"
        elif has_zero:
            salescap_status = f"{len(zero_caps)} zero/exhausted salescap(s)"
        else:
            salescap_status = "no active salescap configured"

        cap_lines = []
        if active_caps:
            cap_lines.append(f"Active Salescaps ({len(active_caps)}):")
            for i, c in enumerate(active_caps, 1):
                cap_lines.append(
                    f"  [{i}] Key: {c['monitorKey']} | Qty: {c['quantity']} | "
                    f"Sold: {c['sold']} | Start: {c['startCap']} | End: {c['endCap']}"
                )
        if zero_caps:
            cap_lines.append(f"Zero Salescaps ({len(zero_caps)}) — EXHAUSTED:")
            for i, c in enumerate(zero_caps, 1):
                cap_lines.append(
                    f"  [{i}] Key: {c['monitorKey']} | Qty: 0 | "
                    f"Sold: {c['sold']} | Start: {c['startCap']} | End: {c['endCap']}"
                )
        if not cap_lines:
            cap_lines.append("  No salescap records found.")

        formatted_output = (
            f"Offer ID : {oid}\n"
            f"Salescap Status: {salescap_status}\n"
            f"Inventory Available (National): {inv_avail}\n"
            f"Inventory Available (VP)      : {inv_vp}\n"
            f"Inventory Available (WFS)     : {inv_wfs}\n"
            f"Total Salescaps: {total_caps}\n"
            + "\n".join(cap_lines)
        )

        results.append({
            "offer_id": oid,
            "salescap_status": salescap_status,
            "has_active_salescap": has_active,
            "has_zero_salescap": has_zero,
            "total_salescaps": total_caps,
            "active_salescaps": active_caps,
            "zero_salescaps": zero_caps,
            "formatted_output": formatted_output,
        })

    combined_output = "\n\n".join(r["formatted_output"] for r in results)

    return {
        "status": "success",
        "offer_ids": offer_ids,
        "total_offers": len(results),
        "data": results,
        "formatted_summary": combined_output,
    }


# ── DIAG-TRANS-01 ─────────────────────────────────────────────────────────────

def diagnose_transactability(offer_id: str, node_id: str = "") -> dict[str, Any]:
    """Diagnose why an offer is out of stock or not transactable at a node.

    When node_id is absent, delegates to diagnose_national_transactability.

    Returns:
        {"status": "success"/"diagnosed", "data": <formatted string>} on success
        {"status": "no_data_found", "data": None} when no record exists
        {"status": "error", "data": None, "error": "..."} on failure
    """
    if not node_id:
        return diagnose_national_transactability(offer_id)

    try:
        from google.cloud import bigquery  # type: ignore
    except ImportError:
        return {"status": "error", "data": None,
                "error": "google-cloud-bigquery is not installed"}

    try:
        client, data_project, tables = _get_bq_setup()
    except Exception as exc:
        return {"status": "error", "data": None, "error": str(exc)}

    node_id = _resolve_node_id(node_id)
    s_id    = f"{offer_id}-fn-{node_id}"

    sql = f"""
SELECT
  km.sellingId AS offerId,
  km.fnId      AS nodeId,
  km.fnType    AS fnType,
  km.f         AS feed_qty,
  km.c         AS completed_qty,
  km.r         AS reserved_qty,
  km.s         AS sellable_qty,
  km.mlu       AS last_inventory_update,
  km.ifa       AS ifa,
  km.lock      AS lock,
  mb.accModes  AS accModes,
  mb.accessModesVp AS accessModesVp,
  mb.wfsEligible   AS wfsEligible,
  mb.isAltPath     AS isAltPath,
  km.releaseDate   AS releaseDate,
  km.isPreOrderEligible AS km_isPreOrderEligible,
  km.isPreOrder    AS isPreOrder,
  km.iad           AS iad,
  km.isFAEligible  AS isFAEligible
FROM {tables['km_snapshot']} km
JOIN {tables['mb_fnfeed']} mb
  ON mb.sId = km.sellingId AND mb.fnId = km.fnId
WHERE km.sId = '{s_id}'
  AND km.partitionId >= 0
  AND mb.partitionId >= 0
ORDER BY km.mlu DESC
LIMIT 1
"""
    try:
        rows = list(client.query(sql).result(timeout=55))
    except Exception as exc:
        return {"status": "error", "data": None, "error": str(exc)}

    if not rows:
        return {
            "status": "no_data_found",
            "data": None,
            "reason": "No inventory snapshot found for this offer/node.",
            "diagnostics": {"offerId": offer_id, "nodeId": node_id},
        }

    row           = dict(rows[0])
    feed_qty      = int(row.get("feed_qty") or 0)
    completed_qty = int(row.get("completed_qty") or 0)
    reserved_qty  = int(row.get("reserved_qty") or 0)
    sellable_qty  = int(row.get("sellable_qty") or 0)
    last_update   = str(row.get("last_inventory_update") or "N/A")
    fn_type       = str(row.get("fnType") or "n/a")
    ifa           = str(row.get("ifa") or "").lower()

    # Lock
    _lock_raw = row.get("lock")
    lock = str(_lock_raw) if _lock_raw and str(_lock_raw).lower() not in ("none", "null", "") else None

    # accModes
    _acc = row.get("accModes")
    try:
        acc_modes = str(list(_acc)) if hasattr(_acc, "__len__") and not isinstance(_acc, str) and len(_acc) > 0 else (str(_acc) if _acc and str(_acc).lower() not in ("none", "null", "") else None)
    except Exception:
        acc_modes = None

    release_date    = str(row.get("releaseDate") or "") or None
    km_preorder     = str(row.get("km_isPreOrderEligible") or "n/a")
    is_preorder_km  = str(row.get("isPreOrder") or "n/a")
    iad             = str(row.get("iad") or "n/a")
    is_fa_eligible  = str(row.get("isFAEligible") or "n/a")
    access_modes_vp = str(row.get("accessModesVp") or "n/a")
    wfs_eligible    = str(row.get("wfsEligible") or "n/a")
    is_alt_path     = str(row.get("isAltPath") or "n/a")

    def _details(extra=None):
        base = (
            f"- Offer ID: {offer_id}\n"
            f"- Node ID: {node_id}\n"
            f"- Fulfillment Node Type: {fn_type}\n"
            f"- Feed Quantity: {feed_qty} units\n"
            f"- Reserved Quantity: {reserved_qty} units\n"
            f"- Completed Quantity: {completed_qty} units\n"
            f"- Sellable Quantity: {sellable_qty} units\n"
            f"- Node Enabled (ifa): {ifa}\n"
            f"- Last Inventory Update: {last_update}\n"
            f"- Active Lock: {lock or 'None'}\n"
            f"- Regular Eligibility (accModes): {acc_modes or '[]'}\n"
            f"- VirtualPack Eligibility (accessModesVp): {access_modes_vp}\n"
            f"- PreOrder Eligible: {km_preorder}\n"
            f"- Is PreOrder: {is_preorder_km}\n"
            f"- Release Date: {release_date or 'None'}\n"
            f"- IAD: {iad}\n"
            f"- FA Eligible: {is_fa_eligible}"
        )
        if extra:
            base += "\n" + "\n".join(f"- {k}: {v}" for k, v in extra.items())
        return base

    # Decision Logic B: feed_qty = 0
    if feed_qty == 0:
        formatted_data = (
            f"What We Found:\n"
            f"This offer has no stock at location {node_id} — the supplier has not sent any inventory here "
            f"(last checked: {last_update}).\n\n"
            f"Conclusion:\nThe offer is unavailable because the supplier has not provided any stock.\n\n"
            f"Recommended Actions:\n- Ask the supplier to send a stock update.\n\n"
            f"Wakanda Analysis Details:\n" + _details()
        )
        return {
            "status": "diagnosed",
            "data": formatted_data,
            "reason": f"Zero inventory update on {last_update}.",
            "remediation": "Ask seller/supplier to send an inventory update.",
            "diagnostics": {"offerId": offer_id, "nodeId": node_id, "feed_qty": feed_qty,
                            "sellable_qty": sellable_qty, "last_inventory_update": last_update},
        }

    # Decision Logic C: feed > 0, sellable <= 0, no lock
    if feed_qty > 0 and sellable_qty <= 0 and lock is None:
        formatted_data = (
            f"What We Found:\n"
            f"This offer has {feed_qty} units at location {node_id} but none are available to sell — "
            f"all stock consumed by {reserved_qty} reserved + {completed_qty} fulfilled.\n\n"
            f"Conclusion:\nOut of stock — all units tied up in existing orders.\n\n"
            f"Recommended Actions:\n- Ask supplier for more stock.\n- Review stuck reservations.\n\n"
            f"Wakanda Analysis Details:\n" + _details({"Stock Formula": "available = stock - reserved - fulfilled"})
        )
        return {
            "status": "diagnosed",
            "data": formatted_data,
            "reason": "Out of stock due to ATS calculation.",
            "remediation": "Ask seller/supplier to upload additional inventory or review open reservations.",
            "diagnostics": {"offerId": offer_id, "nodeId": node_id,
                            "feed_qty": feed_qty, "reserved_qty": reserved_qty,
                            "completed_qty": completed_qty, "sellable_qty": sellable_qty},
        }

    # Decision Logic D: feed > 0, sellable <= 0, lock present
    if feed_qty > 0 and sellable_qty <= 0 and lock is not None:
        formatted_data = (
            f"What We Found:\n"
            f"This offer has {feed_qty} units at location {node_id} but is locked ('{lock}') and cannot be sold.\n\n"
            f"Conclusion:\nStock exists but an active lock is blocking sales.\n\n"
            f"Recommended Actions:\n- Ask the inventory operations team to remove the lock ('{lock}').\n\n"
            f"Wakanda Analysis Details:\n" + _details()
        )
        return {
            "status": "diagnosed",
            "data": formatted_data,
            "reason": "Item is locked and not transactable.",
            "remediation": "Remove or resolve the lock.",
            "diagnostics": {"offerId": offer_id, "nodeId": node_id, "lock": lock,
                            "feed_qty": feed_qty, "sellable_qty": sellable_qty},
        }

    # Decision Logic E: feed > 0, sellable > 0, no accModes
    if feed_qty > 0 and sellable_qty > 0 and acc_modes is None:
        formatted_data = (
            f"What We Found:\n"
            f"This offer has {sellable_qty} units available at location {node_id} "
            "but is not set up to be sold — sales eligibility settings are missing.\n\n"
            f"Conclusion:\nStock available but missing required sales eligibility settings.\n\n"
            f"Recommended Actions:\n- Contact the onboarding or catalogue team to configure eligibility.\n\n"
            f"Wakanda Analysis Details:\n" + _details()
        )
        return {
            "status": "diagnosed",
            "data": formatted_data,
            "reason": "Not transactable — accModes is not configured.",
            "remediation": "Configure eligibility/access modes for this offer/node.",
            "diagnostics": {"offerId": offer_id, "nodeId": node_id, "accModes": "null",
                            "sellable_qty": sellable_qty},
        }

    # Decision Logic F: looks transactable
    formatted_data = (
        f"What We Found:\n"
        f"This offer has {sellable_qty} units available at location {node_id} and is properly set up to sell.\n\n"
        f"Conclusion:\nThe offer looks good at this location. If still not showing as available, the issue is elsewhere.\n\n"
        f"Recommended Actions:\n- No inventory action needed.\n"
        "- Contact the downstream fulfilment team if the offer is still not purchasable.\n\n"
        f"Wakanda Analysis Details:\n" + _details()
    )
    return {
        "status": "diagnosed",
        "data": formatted_data,
        "reason": "Item appears transactable based on current inventory and eligibility.",
        "remediation": "If still not purchasable, check frontend/config flags or recent sync status.",
        "diagnostics": {"offerId": offer_id, "nodeId": node_id,
                        "feed_qty": feed_qty, "sellable_qty": sellable_qty,
                        "accModes": acc_modes},
    }


# ── DIAG-TRANS-NAT-01 ─────────────────────────────────────────────────────────

def diagnose_national_transactability(offer_id: str) -> dict[str, Any]:
    """Run a national-level transactability diagnosis for an offer.

    Returns:
        {"status": "success", "data": <formatted string>} on success
        {"status": "no_data_found", "data": None} when no national record exists
        {"status": "error", "data": None, "error": "..."} on failure
    """
    try:
        from google.cloud import bigquery  # type: ignore
    except ImportError:
        return {"status": "error", "data": None,
                "error": "google-cloud-bigquery is not installed"}

    try:
        client, data_project, tables = _get_bq_setup()
    except Exception as exc:
        return {"status": "error", "data": None, "error": str(exc)}

    sql = f"""
WITH national_data AS (
  SELECT
    sId AS offerId,
    (SELECT f FROM UNNEST(c) WHERE c = 'NationalCarrier' LIMIT 1) AS national_feed,
    (SELECT f FROM UNNEST(c) WHERE c = 'S2S' LIMIT 1) AS s2s_feed,
    CAST(b AS FLOAT64) AS backorder_qty,
    CAST(r AS FLOAT64) AS reservation_qty,
    sCap,
    (SELECT s_national FROM UNNEST(m) WHERE m = '0' LIMIT 1) AS national_sellable,
    (SELECT s_wfs FROM UNNEST(m) WHERE m = '0' LIMIT 1) AS wfs_sellable,
    (SELECT acap FROM UNNEST(m) WHERE m = '0' LIMIT 1) AS active_cap_key,
    lure AS last_update,
    ie AS is_expired,
    isPreOrderEligible,
    isPreOrder,
    streetDate,
    releaseDate
  FROM {tables['mb_snapshot']}
  WHERE partitionId >= 0 AND sId = '{offer_id}'
  LIMIT 1
),
active_salescaps AS (
  SELECT
    nd.offerId,
    sc.monitorKey,
    CAST(sc.quantity AS FLOAT64) AS quantity,
    sc.sold AS sold,
    sc.startCap,
    sc.endCap,
    CASE
      WHEN sc.startCap IS NULL AND sc.endCap IS NULL THEN FALSE
      WHEN sc.startCap IS NULL THEN CURRENT_TIMESTAMP() <= SAFE.PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%E*S%Ez', sc.endCap)
      WHEN sc.endCap IS NULL THEN CURRENT_TIMESTAMP() >= SAFE.PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%E*S%Ez', sc.startCap)
      ELSE CURRENT_TIMESTAMP() BETWEEN SAFE.PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%E*S%Ez', sc.startCap)
                                   AND SAFE.PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%E*S%Ez', sc.endCap)
    END AS is_active
  FROM national_data nd, UNNEST(nd.sCap) AS sc
)
SELECT
  nd.*,
  ARRAY_AGG(STRUCT(sc.monitorKey, sc.quantity, sc.sold, sc.startCap, sc.endCap, sc.is_active))
    AS salescap_details
FROM national_data nd
LEFT JOIN active_salescaps sc ON nd.offerId = sc.offerId
GROUP BY nd.offerId, nd.national_feed, nd.s2s_feed, nd.backorder_qty,
         nd.reservation_qty, nd.sCap, nd.national_sellable, nd.wfs_sellable,
         nd.active_cap_key, nd.last_update, nd.is_expired, nd.isPreOrderEligible,
         nd.isPreOrder, nd.streetDate, nd.releaseDate
"""
    try:
        rows = list(client.query(sql).result(timeout=55))
    except Exception as exc:
        return {"status": "error", "data": None, "error": str(exc)}

    if not rows:
        return {"status": "no_data_found", "data": None}

    row = dict(rows[0])
    national_feed    = float(row.get("national_feed") or 0.0)
    s2s_feed         = float(row.get("s2s_feed") or 0.0)
    backorder_qty    = float(row.get("backorder_qty") or 0.0)
    reservation_qty  = float(row.get("reservation_qty") or 0.0)
    national_sellable= float(row.get("national_sellable") or 0.0)
    wfs_sellable     = float(row.get("wfs_sellable") or 0.0)
    active_cap_key   = row.get("active_cap_key")
    last_update      = row.get("last_update")
    is_preorder      = row.get("isPreOrderEligible")
    is_preorder_flag = row.get("isPreOrder")
    street_date      = str(row.get("streetDate") or "") or None
    release_date     = str(row.get("releaseDate") or "") or None

    # Parse salescap_details
    salescap_details = row.get("salescap_details") or []
    active_caps_with_qty, active_caps_zero_qty = [], []
    for sc in salescap_details:
        try:
            sc_dict = dict(sc) if not isinstance(sc, dict) else sc
        except Exception:
            continue
        if not sc_dict.get("monitorKey"):
            continue
        quantity = float(sc_dict.get("quantity") or 0)
        is_active = sc_dict.get("is_active")
        sc_info = {
            "monitorKey": sc_dict.get("monitorKey"),
            "quantity":   quantity,
            "sold":       float(sc_dict.get("sold") or 0),
            "startCap":   str(sc_dict.get("startCap") or ""),
            "endCap":     str(sc_dict.get("endCap") or ""),
        }
        if is_active:
            (active_caps_with_qty if quantity > 0 else active_caps_zero_qty).append(sc_info)

    has_active = len(active_caps_with_qty) > 0 or len(active_caps_zero_qty) > 0

    # Decision logic
    if national_sellable > 0 and not active_caps_zero_qty:
        reason = f"Wakanda has inventory available (national sellable: {national_sellable} units)"
        remediation = (
            f"From Wakanda end, inventory is available. "
            "Not seeing any issues from our end. "
            "Please reach out to downstream systems IRO/ROLLUP System for further investigation."
        )
        what_found_nl = (
            f"This offer currently has {int(national_sellable)} units available and ready to sell. "
            "No restrictions blocking it."
        )
        conclusion_nl = "Inventory is healthy — no stock or restriction issues found here."
        actions_nl    = (
            "- No inventory action needed.\n"
            "- If the offer is still not visible on the site, contact the downstream team."
        )
    elif national_feed > 0 and has_active:
        if active_caps_zero_qty:
            cap_key  = active_caps_zero_qty[0]["monitorKey"]
            end_date = active_caps_zero_qty[0]["endCap"]
            reason   = f"Blocked by active zero sales cap ({cap_key})."
            remediation = f"Zero salescap '{cap_key}' active until {end_date}. Ask business team to remove or update it."
            what_found_nl = (
                f"Stock available ({int(national_feed)} units) but sales paused by a zero salescap. "
                f"Active until {end_date}."
            )
            conclusion_nl = "Sales blocked by a salescap, not a stock issue."
            actions_nl    = (
                f"- Ask the business team to review and remove salescap key: {cap_key}.\n"
                f"- Confirm the end date ({end_date}) is correct."
            )
        else:
            cap_count    = len(active_caps_with_qty)
            total_cap_qty = int(sum(c["quantity"] for c in active_caps_with_qty))
            reason       = f"{cap_count} active sales cap(s) limiting {total_cap_qty} units."
            remediation  = f"Active salescaps limit sales. Active cap key: {active_cap_key}. Review and adjust as needed."
            what_found_nl = (
                f"Stock available but {cap_count} active sales restriction(s) allow max {total_cap_qty} units."
            )
            conclusion_nl = f"Offer can sell but limited to {total_cap_qty} units by active restrictions."
            actions_nl    = "- Review restrictions with the business team and adjust if needed."
    elif national_feed > 0 and (backorder_qty > 0 or reservation_qty > 0):
        reason      = f"Backorders ({backorder_qty}) and/or reservations ({reservation_qty}) consuming available inventory."
        remediation = "Check order fulfilment status; close or cancel stuck orders."
        parts = []
        if backorder_qty > 0:
            parts.append(f"{int(backorder_qty)} units on backorder")
        if reservation_qty > 0:
            parts.append(f"{int(reservation_qty)} units reserved")
        what_found_nl = (
            f"Stock sent ({int(national_feed)} units) but all held for existing orders — "
            + " and ".join(parts) + "."
        )
        conclusion_nl = "Out of stock — all units tied up in pending orders."
        actions_nl    = (
            "- Check pending orders are progressing normally.\n"
            "- Cancel stuck orders to free up stock."
        )
    elif national_feed > 0 and national_sellable <= 0:
        reason      = f"Feed={int(national_feed)} but sellable={int(national_sellable)} — possible ATS calculation issue."
        remediation = "Verify the ATS calculation at the national carrier level."
        what_found_nl = (
            f"Supplier sent {int(national_feed)} units but sellable is {int(national_sellable)}. "
            "Stock calculation discrepancy detected."
        )
        conclusion_nl = "Stock exists but is not showing as sellable — needs investigation."
        actions_nl    = "- Raise with the inventory operations team to investigate the stock calculation."
    else:
        reason      = "No inventory in the national carrier."
        remediation = "Verify the upstream feed from suppliers or the EI system."
        what_found_nl = (
            f"Zero stock at all levels "
            f"({int(backorder_qty)} units on backorder, {int(reservation_qty)} reserved)."
        )
        conclusion_nl = "Out of stock — no inventory received from the supplier."
        actions_nl    = (
            "- Contact the supplier to send a stock update.\n"
            "- Review open backorders to ensure they can be fulfilled once stock arrives."
        )

    # Salescap detail lines
    salescap_lines = []
    for sc in active_caps_with_qty:
        salescap_lines.append(
            f"  - Active: {sc['monitorKey']} | Qty: {sc['quantity']} | "
            f"Sold: {sc['sold']} | Start: {sc['startCap']} | End: {sc['endCap']}"
        )
    for sc in active_caps_zero_qty:
        salescap_lines.append(
            f"  - Zero: {sc['monitorKey']} | Qty: 0 (EXHAUSTED) | "
            f"Sold: {sc['sold']} | Start: {sc['startCap']} | End: {sc['endCap']}"
        )
    salescap_detail = "\n".join(salescap_lines) if salescap_lines else "  None"

    formatted_data = (
        f"What We Found:\n{what_found_nl}\n\n"
        f"Conclusion:\n{conclusion_nl}\n\n"
        f"Recommended Actions:\n{actions_nl}\n\n"
        f"Wakanda Analysis Details:\n"
        f"- Offer ID: {offer_id}\n"
        f"- National Feed Qty: {national_feed} units\n"
        f"- National Sellable Qty: {national_sellable} units\n"
        f"- WFS Sellable: {wfs_sellable} units\n"
        f"- Backorder Qty: {backorder_qty} units\n"
        f"- Reservation Qty: {reservation_qty} units\n"
        f"- Active Cap Key: {active_cap_key or 'none'}\n"
        f"- Active Salescaps (qty>0): {len(active_caps_with_qty)}\n"
        f"- Active Salescaps (qty=0): {len(active_caps_zero_qty)}\n"
        f"- PreOrder Eligible: {is_preorder}\n"
        f"- Is PreOrder: {is_preorder_flag}\n"
        f"- Street Date: {street_date or 'n/a'}\n"
        f"- Release Date: {release_date or 'n/a'}\n"
        f"- Last Update: {str(last_update) if last_update else 'Unknown'}\n"
        f"- Salescap Details:\n{salescap_detail}"
    )

    return {
        "status": "success",
        "offer_id": offer_id,
        "data": formatted_data,
        "reason": reason,
        "remediation": remediation,
        "diagnostics": {
            "national_feed": national_feed,
            "national_sellable": national_sellable,
            "backorder_qty": backorder_qty,
            "reservation_qty": reservation_qty,
            "has_active_salescap": has_active,
        },
    }


# ── DIAG-OFFRES-01 ────────────────────────────────────────────────────────────

def get_offer_reservations(offer_id: str, query_type: str = "both") -> dict[str, Any]:
    """Return offer-level reservations and backorders from mbaku_current_reservation.

    query_type: "both" (default) | "reservation" | "backorder"

    Returns:
        {"status": "success", "data": <formatted string>} on success
        {"status": "no_data_found", "data": None} when no reservation records exist
        {"status": "error", "data": None, "error": "..."} on failure
    """
    try:
        from google.cloud import bigquery  # type: ignore
    except ImportError:
        return {"status": "error", "data": None,
                "error": "google-cloud-bigquery is not installed"}

    try:
        client, _, _ = _get_bq_setup()
    except Exception as exc:
        return {"status": "error", "data": None, "error": str(exc)}

    TABLE = "wakanda-gcp-prod.mbaku_current.mbaku_current_reservation"
    qt    = query_type.lower().strip()
    dfs   = []

    if qt in ("backorder", "both"):
        sql_b = f"""
SELECT oId AS order_id, ocd AS order_created_date, b AS backorder_qty, 'backorder' AS type
FROM `{TABLE}`
WHERE sId = '{offer_id}' AND partitionId >= 0 AND b > 0 AND s = 'Reserved'
ORDER BY ocd DESC
"""
        try:
            bo_rows = [dict(r) for r in client.query(sql_b).result(timeout=55)]
            if bo_rows:
                dfs.extend(bo_rows)
        except Exception as exc:
            return {"status": "error", "data": None, "error": str(exc)}

    if qt in ("reservation", "both"):
        sql_r = f"""
SELECT oId AS order_id, ocd AS order_created_date, r AS reserved_qty, 'reservation' AS type
FROM `{TABLE}`
WHERE sId = '{offer_id}' AND partitionId >= 0 AND r > 0 AND s = 'Reserved'
ORDER BY ocd DESC
"""
        try:
            res_rows = [dict(r) for r in client.query(sql_r).result(timeout=55)]
            if res_rows:
                dfs.extend(res_rows)
        except Exception as exc:
            return {"status": "error", "data": None, "error": str(exc)}

    if not dfs:
        label = {"backorder": "backorders", "reservation": "reservations",
                 "both": "reservations or backorders"}.get(qt, "records")
        return {"status": "no_data_found", "data": None,
                "message": f"No active {label} found for offer {offer_id}."}

    total             = len(dfs)
    total_backorders  = sum(int(r.get("backorder_qty") or 0) for r in dfs if r.get("type") == "backorder")
    total_reservations= sum(int(r.get("reserved_qty") or 0)  for r in dfs if r.get("type") == "reservation")
    bo_count          = sum(1 for r in dfs if r.get("type") == "backorder")
    res_count         = sum(1 for r in dfs if r.get("type") == "reservation")

    if bo_count > 0 and res_count > 0:
        what_found = (
            f"There are {bo_count} order(s) on backorder ({total_backorders} units) "
            f"and {res_count} order(s) with stock reserved ({total_reservations} units)."
        )
        conclusion = "Multiple orders waiting or with stock held — need to be fulfilled or resolved."
        actions    = (
            "- Check all open orders are moving through the fulfilment process.\n"
            "- Cancel stuck orders to release the held stock."
        )
    elif bo_count > 0:
        what_found = (
            f"There are {bo_count} order(s) on backorder ({total_backorders} units)."
        )
        conclusion = "Customers waiting for this offer to come back in stock."
        actions    = "- Ensure a stock replenishment is in progress so backorders can be fulfilled."
    else:
        what_found = (
            f"There are {res_count} order(s) with stock reserved ({total_reservations} units)."
        )
        conclusion = "Stock held for pending orders — will free up once shipped or cancelled."
        actions    = "- Cancel stuck reservations to release stock back to available."

    analysis = (
        f"- Offer ID: {offer_id}\n"
        f"- Open Backorders: {bo_count} order(s), {total_backorders} units\n"
        f"- Open Reservations: {res_count} order(s), {total_reservations} units"
    )

    # Build inline row sections
    detail_parts = []
    bo_rows  = [r for r in dfs if r.get("type") == "backorder"][:10]
    res_rows = [r for r in dfs if r.get("type") == "reservation"][:10]
    if bo_rows:
        lines = [
            f"- Order: {r['order_id']} | Created: {r.get('order_created_date')} | "
            f"Backorder Qty: {int(r.get('backorder_qty') or 0)}"
            for r in bo_rows
        ]
        detail_parts.append("Open Backorder Details:\n" + "\n".join(lines))
    if res_rows:
        lines = [
            f"- Order: {r['order_id']} | Created: {r.get('order_created_date')} | "
            f"Reserved Qty: {int(r.get('reserved_qty') or 0)}"
            for r in res_rows
        ]
        detail_parts.append("Open Reservation Details:\n" + "\n".join(lines))
    if total > 20:
        detail_parts.append(f"... ({total - 20} more rows not shown)")

    formatted_data = (
        f"What We Found:\n{what_found}\n\n"
        f"Conclusion:\n{conclusion}\n\n"
        f"Recommended Actions:\n{actions}\n\n"
        f"Wakanda Analysis Details:\n{analysis}"
        + ("\n\n" + "\n\n".join(detail_parts) if detail_parts else "")
    )

    return {
        "status": "success",
        "offer_id": offer_id,
        "query_type": qt,
        "total_rows": total,
        "total_backorder_qty": total_backorders,
        "total_reserved_qty": total_reservations,
        "data": formatted_data,
    }


# ── DIAG-HIST-01 ──────────────────────────────────────────────────────────────

def get_offer_history_inventory(
    offer_id: str,
    days: int = 7,
    start_date: str = "",
    end_date: str = "",
) -> dict[str, Any]:
    """Return historical inventory timeline for an offer across all nodes.

    Queries mbaku_historic.mb_snapshot_* wildcard date-partitioned tables in
    BigQuery.  Accepts a relative day window (days) or an explicit
    start_date/end_date range (YYYY-MM-DD).

    Rows are ordered DESC by updateTime and grouped into consecutive
    POSITIVE/ZERO stock transition periods.

    Returns:
        {"status": "success", "data": {...}} on success
        {"status": "no_data_found", "data": None} when no history records exist
        {"status": "error", "data": None, "error": "..."} on infrastructure failure
    """
    import os
    from datetime import datetime, timedelta, timezone

    try:
        from google.cloud import bigquery  # type: ignore
    except ImportError:
        return {
            "status": "error",
            "data": None,
            "error": "google-cloud-bigquery is not installed — add it to requirements.txt",
        }

    from agent_factory.infrastructure.settings import get_config

    cfg = get_config()
    bq_cfg = getattr(cfg, "wakanda_bigquery", None)
    data_project = str(getattr(bq_cfg, "GCP_PROJECT_ID", "wakanda-gcp-prod")) if bq_cfg else "wakanda-gcp-prod"
    # Credentials: BQ_CREDENTIALS_PATH takes priority; falls back to bigquerycredentials_eventops
    # which has bigquery.jobs.create on its own project and cross-project read on data_project.
    bq_creds_path = (
        str(getattr(bq_cfg, "BQ_CREDENTIALS_PATH", "")) if bq_cfg else ""
    ) or "/etc/secrets/bigquerycredentials_eventops"
    gcp_creds_path = str(getattr(bq_cfg, "GCP_CREDENTIALS_PATH", "")) if bq_cfg else ""
    dataset = str(getattr(bq_cfg, "BQ_MBAKU_HISTORIC_DATASET", "mbaku_historic")) if bq_cfg else "mbaku_historic"
    table_prefix = str(getattr(bq_cfg, "BQ_MBAKU_HISTORIC_TABLE_PREFIX", "mb_snapshot_")) if bq_cfg else "mb_snapshot_"

    # Build date range
    now = datetime.now(timezone.utc)
    if start_date and end_date:
        try:
            dt_start = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            dt_end = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        except ValueError:
            dt_end = now
            dt_start = now - timedelta(days=max(1, days))
    else:
        dt_end = now
        dt_start = now - timedelta(days=max(1, days))

    # Tables are partitioned as mb_snapshot_M_YYYY (e.g. mb_snapshot_5_2026).
    # Enumerate all month-year suffixes that overlap the query window.
    def _month_year_suffixes(start, end):
        m, y = start.month, start.year
        em, ey = end.month, end.year
        out = []
        while (y, m) <= (ey, em):
            out.append(f"{m}_{y}")
            m = m % 12 + 1
            if m == 1:
                y += 1
        return out

    suffixes = _month_year_suffixes(dt_start, dt_end)
    suffix_in = ", ".join(f"'{s}'" for s in suffixes)

    table_ref = f"`{data_project}.{dataset}.{table_prefix}*`"
    udf_ref = f"`{data_project}.{dataset}`"

    query = f"""
SELECT
    sId          AS offer_id,
    m.s_national AS sellable_qty,
    r            AS reserved_qty,
    b            AS backorder_qty,
    updateTime
FROM {table_ref},
     UNNEST(m) AS m
WHERE sId = @offer_id
  AND partitionId = {udf_ref}.PARTITION_ID(@offer_id)
  AND _TABLE_SUFFIX IN ({suffix_in})
  AND updateTime >= @window_start
  AND updateTime <= @window_end
ORDER BY updateTime DESC
"""

    try:
        from google.oauth2 import service_account  # type: ignore

        # Prefer BQ-specific credentials; fall back to general GCP credentials.
        creds_path = bq_creds_path if os.path.exists(bq_creds_path) else gcp_creds_path
        if creds_path and os.path.exists(creds_path):
            creds = service_account.Credentials.from_service_account_file(
                creds_path,
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
            # Run jobs in the service account's own project; data is read cross-project.
            client = bigquery.Client(project=creds.project_id, credentials=creds)
        else:
            client = bigquery.Client(project=data_project)

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("offer_id", "STRING", offer_id),
                bigquery.ScalarQueryParameter("window_start", "TIMESTAMP", dt_start),
                bigquery.ScalarQueryParameter("window_end", "TIMESTAMP", dt_end),
            ]
        )
        rows = list(client.query(query, job_config=job_config).result(timeout=55))
    except Exception as exc:
        return {"status": "error", "data": None, "error": str(exc)}

    if not rows:
        return {"status": "no_data_found", "data": None}

    snapshots = [dict(r) for r in rows]

    # Group DESC-ordered snapshots into consecutive POSITIVE/ZERO transition periods.
    # cur_* values are captured at the start (newest row) of each period and held
    # fixed; cur_start_ts walks backward to the oldest row in the period.
    # BigQuery returns Decimal for numeric columns — cast to int for clean output.
    periods: list[dict] = []
    first_snap = snapshots[0]
    first_qty = int(first_snap.get("sellable_qty") or 0)
    cur_state    = "POSITIVE" if first_qty > 0 else "ZERO"
    cur_qty      = first_qty
    cur_reserved = int(first_snap.get("reserved_qty") or 0)
    cur_backorder = int(first_snap.get("backorder_qty") or 0)
    cur_end_ts   = first_snap.get("updateTime")
    cur_start_ts = first_snap.get("updateTime")

    for snap in snapshots[1:]:
        qty   = snap.get("sellable_qty") or 0
        state = "POSITIVE" if qty > 0 else "ZERO"
        ts    = snap.get("updateTime")

        if state != cur_state:
            periods.append({
                "state":        cur_state,
                "sellable_qty": cur_qty,
                "reserved_qty": cur_reserved,
                "backorder_qty": cur_backorder,
                "period_start": str(cur_start_ts),
                "period_end":   str(cur_end_ts),
            })
            cur_state     = state
            cur_qty       = int(qty)
            cur_reserved  = int(snap.get("reserved_qty") or 0)
            cur_backorder = int(snap.get("backorder_qty") or 0)
            cur_end_ts    = ts
            cur_start_ts  = ts
        else:
            cur_start_ts = ts  # extend period start backward in time

    # Append the oldest (final) period
    periods.append({
        "state":        cur_state,
        "sellable_qty": cur_qty,
        "reserved_qty": cur_reserved,
        "backorder_qty": cur_backorder,
        "period_start": str(cur_start_ts),
        "period_end":   str(cur_end_ts),
    })

    # Reverse to chronological order so Period 1 is the oldest
    periods = list(reversed(periods))

    # ── Build formatted timeline string ───────────────────────────────
    sep = "─" * 37
    header_lines = [
        "📦 Offer Inventory History",
        f"Offer ID  : {offer_id}",
        f"Period    : {dt_start.strftime('%Y-%m-%d')} to {dt_end.strftime('%Y-%m-%d')}",
        f"Snapshots : {len(snapshots):,} rows | {len(periods)} transition period(s)",
        "",
        sep,
        "Inventory Transition Timeline",
        sep,
    ]
    period_lines: list[str] = []
    for i, p in enumerate(periods, 1):
        emoji = "✅" if p["state"] == "POSITIVE" else "⚪"
        label = "Positive" if p["state"] == "POSITIVE" else "Zero"
        is_last = i == len(periods)
        period_end_label = "Present" if is_last else p["period_end"]
        period_lines += [
            f"Period {i}: {emoji} {label}",
            f"  From     : {p['period_start']}",
            f"  To       : {period_end_label}",
            f"  Sellable : {p['sellable_qty']:,} units",
            f"  Reserved : {p['reserved_qty']:,} units",
            f"  Backorder: {p['backorder_qty']:,} units",
            "",
        ]
    period_lines.append(sep)
    formatted_timeline = "\n".join(header_lines + period_lines)

    return {
        "status": "success",
        "data": {
            "offer_id": offer_id,
            "query_window": {
                "start": dt_start.isoformat(),
                "end":   dt_end.isoformat(),
                "days":  days,
            },
            "total_snapshots":    len(snapshots),
            "transition_periods": len(periods),
            "periods":            periods,
            "formatted_timeline": formatted_timeline,
        },
    }


# ── DIAG-NODEHIST-01 ──────────────────────────────────────────────────────────

def get_offer_node_inventory_history(
    offer_id: str,
    node_id: str,
    days: int = 7,
    start_date: str = "",
    end_date: str = "",
    sections: str = "all",
) -> dict[str, Any]:
    """Retrieve feed-quantity and/or eligibility transition history for an offer at a node.

    ALWAYS set the `sections` parameter based on what the user asked for:
      sections="inventory"   → feed quantity history ONLY
                               Use when the user says "inventory history", "feed history",
                               "feed quantity history", or similar inventory-focused requests.
      sections="eligibility" → eligibility history ONLY
                               Use when the user says "eligibility history",
                               "access mode history", or similar eligibility-focused requests.
      sections="all"         → both feed quantity AND eligibility (default)
                               Use only when the user asks for general history or both.

    Queries mbaku_historic.mb_fnfeed_* wildcard tables.
    Smart default: if no date params, expands 30→90→365 days until data found.

    Returns:
        {"status": "success", "data": <formatted string>} on success
        {"status": "no_data_found", "data": None} when no history records exist
        {"status": "error", "data": None, "error": "..."} on failure
    """
    import os
    from datetime import datetime, timedelta, timezone

    try:
        from google.cloud import bigquery  # type: ignore
    except ImportError:
        return {"status": "error", "data": None,
                "error": "google-cloud-bigquery is not installed — add it to requirements.txt"}

    from agent_factory.infrastructure.settings import get_config

    cfg = get_config()
    bq_cfg = getattr(cfg, "wakanda_bigquery", None)
    data_project  = str(getattr(bq_cfg, "GCP_PROJECT_ID", "wakanda-gcp-prod")) if bq_cfg else "wakanda-gcp-prod"
    bq_creds_path = (
        str(getattr(bq_cfg, "BQ_CREDENTIALS_PATH", "")) if bq_cfg else ""
    ) or "/etc/secrets/bigquerycredentials_eventops"
    gcp_creds_path = str(getattr(bq_cfg, "GCP_CREDENTIALS_PATH", "")) if bq_cfg else ""

    node_id = _resolve_node_id(node_id)

    # Build datetime window — mirrors get_offer_history_inventory exactly
    now = datetime.now(timezone.utc)
    smart_default_days: Optional[int] = None
    if start_date and end_date:
        try:
            dt_start = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            dt_end   = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        except ValueError:
            dt_end   = now
            dt_start = now - timedelta(days=max(1, days))
    else:
        dt_end   = now
        dt_start = now - timedelta(days=max(1, days) if days else 30)
        if not days:
            smart_default_days = 30

    # Enumerate month-year table suffixes that overlap the window (e.g. "5_2026")
    def _month_year_suffixes(start, end):
        m, y = start.month, start.year
        em, ey = end.month, end.year
        out = []
        while (y, m) <= (ey, em):
            out.append(f"{m}_{y}")
            m = m % 12 + 1
            if m == 1:
                y += 1
        return out

    table_ref = f"`{data_project}.mbaku_historic.mb_fnfeed_*`"
    udf_ref   = f"`{data_project}.mbaku_historic`"

    try:
        from google.oauth2 import service_account  # type: ignore

        creds_path = bq_creds_path if os.path.exists(bq_creds_path) else gcp_creds_path
        if creds_path and os.path.exists(creds_path):
            creds  = service_account.Credentials.from_service_account_file(
                creds_path, scopes=["https://www.googleapis.com/auth/cloud-platform"])
            client = bigquery.Client(project=creds.project_id, credentials=creds)
        else:
            client = bigquery.Client(project=data_project)

        def _run_query(dt_s, dt_e):
            sfx       = _month_year_suffixes(dt_s, dt_e)
            suffix_in = ", ".join(f"'{s}'" for s in sfx)
            query = f"""
SELECT sId AS OfferId,
       fnId AS NodeId,
       luf AS LastUpdatedFeedTime,
       accModes AS eligibility,
       accessModesVp AS vp_eligibility,
       updateTime AS lastUpdatedTime,
       mart.f AS feed_qty
FROM {table_ref} mb,
     UNNEST(m) AS mart
WHERE sId = @offer_id
  AND fnId = @node_id
  AND partitionId = {udf_ref}.PARTITION_ID(@offer_id)
  AND _TABLE_SUFFIX IN ({suffix_in})
  AND updateTime >= @window_start
  AND updateTime <= @window_end
ORDER BY updateTime ASC
"""
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("offer_id",     "STRING",    offer_id),
                    bigquery.ScalarQueryParameter("node_id",      "STRING",    node_id),
                    bigquery.ScalarQueryParameter("window_start", "TIMESTAMP", dt_s),
                    bigquery.ScalarQueryParameter("window_end",   "TIMESTAMP", dt_e),
                ]
            )
            return list(client.query(query, job_config=job_config).result(timeout=55))

        rows = _run_query(dt_start, dt_end)

        # Auto-expand window when day-based filter returns no rows (30→90→365)
        if not rows and not (start_date and end_date):
            _initial    = days if days else 30
            expand_list = [90, 365] if _initial <= 30 else ([365] if _initial <= 90 else [])
            for expand in expand_list:
                smart_default_days = expand
                dt_start           = now - timedelta(days=expand)
                rows               = _run_query(dt_start, dt_end)
                if rows:
                    break

    except Exception as exc:
        return {"status": "error", "data": None, "error": str(exc)}

    if not rows:
        period_label = ""
        if start_date and end_date:
            period_label = f" between {start_date} and {end_date}"
        elif days:
            period_label = f" in the last {days} day(s)"
        elif smart_default_days:
            period_label = " in the last 365 days (auto-searched 30/90/365 day windows)"
        return {
            "status": "no_data_found",
            "data": None,
            "message": (
                f"No historical inventory records found for offer {offer_id} "
                f"at node {node_id}{period_label}."
            ),
        }

    records    = [dict(r) for r in rows]
    total_rows = len(records)

    # Status label helpers
    def _feed_label(qty) -> str:
        try:
            q = float(qty)
        except (TypeError, ValueError):
            return "⚪ Unknown"
        if q > 0:  return "✅ Positive"
        if q == 0: return "⚪ Zero"
        return "❌ Negative"

    def _elig_label(modes) -> str:
        if modes is None: return "❌ Not Eligible"
        try:
            active = [m for m in list(modes) if m]
            return "✅ Eligible" if active else "❌ Not Eligible"
        except Exception:
            s = str(modes).strip()
            return "❌ Not Eligible" if not s or s.lower() in ("none", "null", "[]", "") else "✅ Eligible"

    def _modes_str(modes) -> str:
        if modes is None: return "(none)"
        try:
            active = [str(m) for m in list(modes) if m]
            return ", ".join(active) if active else "(none)"
        except Exception:
            s = str(modes).strip()
            return s if s and s.lower() not in ("none", "null", "[]", "") else "(none)"

    def _fmt_ts(raw) -> str:
        try:
            s = str(raw).split(".")[0].replace("T", " ")
            if "+" in s:
                s = s.split("+")[0]
            return s.strip() + " UTC"
        except Exception:
            return str(raw)

    # Build transition periods in one pass
    feed_periods: list[dict] = []
    elig_periods: list[dict] = []
    vp_elig_periods: list[dict] = []
    cur_feed = cur_elig = cur_vp = None
    feed_start_ts = elig_start_ts = vp_start_ts = None
    feed_start_qty = elig_start_modes = vp_start_modes = None

    for r in records:
        qty_raw   = r.get("feed_qty")
        modes_raw = r.get("eligibility")
        vp_raw    = r.get("vp_eligibility")
        ts        = r.get("lastUpdatedTime")

        feed_st = _feed_label(qty_raw)
        elig_st = _elig_label(modes_raw)
        vp_st   = _elig_label(vp_raw)

        if feed_st != cur_feed:
            if cur_feed is not None:
                feed_periods.append({"status": cur_feed, "from": str(feed_start_ts),
                                     "to": str(ts), "feed_qty": float(feed_start_qty or 0)})
            cur_feed = feed_st; feed_start_ts = ts; feed_start_qty = qty_raw

        if elig_st != cur_elig:
            if cur_elig is not None:
                elig_periods.append({"status": cur_elig, "from": str(elig_start_ts),
                                     "to": str(ts), "modes": _modes_str(elig_start_modes)})
            cur_elig = elig_st; elig_start_ts = ts; elig_start_modes = modes_raw

        if vp_st != cur_vp:
            if cur_vp is not None:
                vp_elig_periods.append({"status": cur_vp, "from": str(vp_start_ts),
                                        "to": str(ts), "modes": _modes_str(vp_start_modes)})
            cur_vp = vp_st; vp_start_ts = ts; vp_start_modes = vp_raw

    # Close open periods
    last = records[-1]
    if cur_feed is not None:
        feed_periods.append({"status": cur_feed, "from": str(feed_start_ts), "to": "present",
                             "feed_qty": float(last.get("feed_qty") or 0)})
    if cur_elig is not None:
        elig_periods.append({"status": cur_elig, "from": str(elig_start_ts), "to": "present",
                             "modes": _modes_str(last.get("eligibility"))})
    if cur_vp is not None:
        vp_elig_periods.append({"status": cur_vp, "from": str(vp_start_ts), "to": "present",
                                "modes": _modes_str(last.get("vp_eligibility"))})

    # Determine which sections to show based on the `sections` string param
    _sec = (sections or "all").strip().lower()
    show_feed = _sec in ("all", "inventory", "feed")
    show_elig = _sec in ("all", "eligibility")

    # Format period blocks
    def _fmt_feed_periods(periods):
        lines = []
        for i, p in enumerate(periods, 1):
            from_ts = _fmt_ts(p["from"])
            to_ts   = "Present" if p["to"] == "present" else _fmt_ts(p["to"])
            lines.append(
                f"Period {i}: {p['status']}\n"
                f"  From     : {from_ts}\n"
                f"  To       : {to_ts}\n"
                f"  Feed Qty : {int(p['feed_qty'])} units"
            )
        return "\n\n".join(lines) if lines else "  (no transitions found)"

    def _fmt_elig_periods(periods):
        lines = []
        for i, p in enumerate(periods, 1):
            from_ts = _fmt_ts(p["from"])
            to_ts   = "Present" if p["to"] == "present" else _fmt_ts(p["to"])
            lines.append(
                f"Period {i}: {p['status']}\n"
                f"  From  : {from_ts}\n"
                f"  To    : {to_ts}\n"
                f"  Modes : {p['modes']}"
            )
        return "\n\n".join(lines) if lines else "  (no transitions found)"

    # Date range summary
    earliest = _fmt_ts(records[0].get("lastUpdatedTime"))
    latest   = _fmt_ts(records[-1].get("lastUpdatedTime"))
    if start_date and end_date:
        range_desc = f"{start_date} to {end_date}"
    elif days:
        range_desc = f"Last {days} day(s)  ({earliest}  →  {latest})"
    elif smart_default_days:
        range_desc = (
            f"Last {smart_default_days} day(s)  ({earliest}  →  {latest})\n"
            "ℹ️  No time period specified — auto-selected. Use days=N or start_date/end_date for a specific range."
        )
    else:
        range_desc = f"{earliest}  →  {latest}"

    _title = (
        "📦 Offer-Node Eligibility History" if not show_feed
        else "📦 Offer-Node Feed Quantity History" if not show_elig
        else "📦 Offer-Node Inventory History"
    )
    summary_parts = [f"{total_rows} rows"]
    if show_feed: summary_parts.append(f"{len(feed_periods)} feed transition(s)")
    if show_elig:
        summary_parts.append(f"{len(elig_periods)} regular elig transition(s)")
        summary_parts.append(f"{len(vp_elig_periods)} vp elig transition(s)")

    sections_body = ""
    if show_feed:
        sections_body += (
            "─────────────────────────────────────\n"
            "Feed Quantity Transition Timeline\n"
            "─────────────────────────────────────\n"
            + _fmt_feed_periods(feed_periods) + "\n\n"
        )
    if show_elig:
        sections_body += (
            "─────────────────────────────────────\n"
            "Regular Eligibility Transition Timeline\n"
            "─────────────────────────────────────\n"
            + _fmt_elig_periods(elig_periods) + "\n\n"
            "─────────────────────────────────────\n"
            "VirtualPack Eligibility Transition Timeline\n"
            "─────────────────────────────────────\n"
            + _fmt_elig_periods(vp_elig_periods) + "\n"
        )

    formatted_data = (
        f"{_title}\n"
        f"Offer ID : {offer_id}\n"
        f"Node ID  : {node_id}\n"
        f"Period   : {range_desc}\n"
        f"Snapshots: {'  |  '.join(summary_parts)}\n\n"
        f"{sections_body}"
        "─────────────────────────────────────"
    )

    result: dict[str, Any] = {
        "status": "success",
        "offer_id": offer_id,
        "node_id": node_id,
        "total_rows": total_rows,
        "data": formatted_data,
    }
    if show_feed:
        result["feed_transition_count"] = len(feed_periods)
    if show_elig:
        result["elig_transition_count"] = len(elig_periods)
        result["vp_elig_transition_count"] = len(vp_elig_periods)
    return result


# ── DIAG-FEED-01 ──────────────────────────────────────────────────────────────

def _strip_suffix(value: str | None) -> str:
    """Remove the ``@<shard>`` suffix from a Killmonger batch or record ID.

    Stored values carry a shard token after the first ``@`` that is absent
    from the user-facing feed ID:

      ``18B150F08D8B5508AA71313FD6CB5AAA@0``  →  ``18B150F08D8B5508AA71313FD6CB5AAA``
      ``AQkBCgA@66u4KFq0``                    →  ``AQkBCgA``

    Returns an empty string for ``None`` or empty input.
    """
    if not value:
        return ""
    return value.split("@")[0]


def check_feed_qty_update(
    feed_id: str,
    offer_id: str,
    node_id: str,
) -> dict[str, Any]:
    """Verify whether a submitted feed qty update is recorded in Killmonger for an offer-node.

    Splits ``feed_id`` on ``@`` to derive ``expected_batch_id`` and
    ``expected_record_id``.  Queries Killmonger historic events joined with
    historic snapshots for the given offer-node partition, then compares the
    stripped ``marketplaceFeedBatchId`` and ``recordIdentifier`` columns against
    the user-submitted values.

    Args:
        feed_id:  Feed batch ID in ``<batchId>@<recordId>`` format, e.g.
                  ``18B150F08D8B5508AA71313FD6CB5AAA@AQkBCgA``.
        offer_id: 32-char hex offer/SKU ID.
        node_id:  Fulfillment node ID (numeric string).

    Returns:
        On match found:
            ``{"found": True, "feed_id": ..., "offer_id": ..., "node_id": ...,
             "partition_key": ..., "matched_rows": [...],
             "total_events_fetched": int, "total_matched": int}``
        On no match (rows exist but none match the feed):
            ``{"found": False, ..., "message": "...", "total_events_fetched": int}``
        On empty result set (offer-node unknown in Killmonger):
            ``{"found": False, ..., "message": "No Killmonger history found...",
             "total_events_fetched": 0}``
        On any exception:
            ``{"error": str, "feed_id": ..., "offer_id": ..., "node_id": ...}``
    """
    try:
        from google.cloud import bigquery  # type: ignore
    except ImportError:
        return {
            "error": "google-cloud-bigquery is not installed",
            "feed_id": feed_id,
            "offer_id": offer_id,
            "node_id": node_id,
        }

    # Split feed_id into batch and record components.
    parts = feed_id.split("@", 1)
    expected_batch_id = parts[0]
    expected_record_id = parts[1] if len(parts) > 1 else None

    partition_key = f"{offer_id}-fn-{node_id}"

    try:
        client, data_project, _ = _get_bq_setup()
    except Exception as exc:
        return {
            "error": str(exc),
            "feed_id": feed_id,
            "offer_id": offer_id,
            "node_id": node_id,
        }

    events_ref  = f"`{data_project}.killmonger_historic.killmonger-events_*`"
    dataset_ref = f"`{data_project}.killmonger_historic`"

    query = f"""
SELECT
  e.id,
  e.sId,
  e.ssn,
  e.et,
  e.ts,
  JSON_VALUE(e.ed, '$.skuId')                   AS skuId,
  SAFE_CAST(JSON_VALUE(e.ed, '$.f') AS FLOAT64) AS feedreceived,
  JSON_VALUE(e.ed, '$.marketplaceFeedBatchId')   AS marketplaceFeedBatchId,
  JSON_VALUE(e.ed, '$.recordIdentifier')         AS recordIdentifier

FROM {events_ref} e

WHERE
  e.partitionId = {dataset_ref}.PARTITION_ID(@partition_key)
  AND e.sId = @sid

ORDER BY e.ts DESC
"""

    try:
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("partition_key", "STRING", partition_key),
                bigquery.ScalarQueryParameter("sid",           "STRING", partition_key),
            ]
        )
        rows = list(client.query(query, job_config=job_config).result(timeout=55))
    except Exception as exc:
        return {
            "error": str(exc),
            "feed_id": feed_id,
            "offer_id": offer_id,
            "node_id": node_id,
        }

    total_fetched = len(rows)

    if total_fetched == 0:
        return {
            "found": False,
            "feed_id": feed_id,
            "offer_id": offer_id,
            "node_id": node_id,
            "partition_key": partition_key,
            "message": (
                f"No Killmonger history found for offer '{offer_id}' at node '{node_id}'. "
                "Confirm the offer ID and node ID are correct."
            ),
            "total_events_fetched": 0,
        }

    matched: list[dict] = []
    for row in rows:
        row_dict = dict(row)
        batch_match  = _strip_suffix(row_dict.get("marketplaceFeedBatchId")) == expected_batch_id
        record_match = (
            expected_record_id is None
            or _strip_suffix(row_dict.get("recordIdentifier")) == expected_record_id
        )
        if batch_match and record_match:
            matched.append(row_dict)

    if matched:
        # ── Phase 2: snapshot history around the feed event timestamp ──────────
        # Derive a UTC datetime from the matched event's `ts` column.
        # Killmonger stores `ts` as INT64 epoch-milliseconds; BigQuery may also
        # return it as a Python datetime when the column is typed TIMESTAMP.
        from datetime import datetime, timezone, timedelta

        def _to_utc_dt(ts_val) -> "datetime | None":
            if ts_val is None:
                return None
            if isinstance(ts_val, datetime):
                return ts_val if ts_val.tzinfo else ts_val.replace(tzinfo=timezone.utc)
            if isinstance(ts_val, (int, float)):
                # Heuristic: >1e12 → milliseconds, >1e9 → seconds.
                if ts_val > 1e12:
                    return datetime.fromtimestamp(ts_val / 1000.0, tz=timezone.utc)
                return datetime.fromtimestamp(float(ts_val), tz=timezone.utc)
            return None

        # Use the earliest matched event as the anchor for the snapshot window.
        event_dt: "datetime | None" = None
        for row in matched:
            dt = _to_utc_dt(row.get("ts"))
            if dt and (event_dt is None or dt < event_dt):
                event_dt = dt

        # ── Phase 2: mbaku fnfeed history around the feed event date ─────────
        # Reuse the existing get_offer_node_inventory_history() which queries
        # mbaku_historic.mb_fnfeed_* — the canonical source for what qty
        # Wakanda applied to its inventory after receiving the feed.
        mbaku_history: dict = {}

        if event_dt is not None:
            # Use a ±1-day window centred on the feed event date so the table
            # suffix enumeration in get_offer_node_inventory_history() covers
            # the right monthly partitions without pulling unnecessary data.
            start_date_str = (event_dt - timedelta(days=1)).strftime("%Y-%m-%d")
            end_date_str   = (event_dt + timedelta(days=1)).strftime("%Y-%m-%d")

            try:
                mbaku_history = get_offer_node_inventory_history(
                    offer_id=offer_id,
                    node_id=node_id,
                    start_date=start_date_str,
                    end_date=end_date_str,
                    sections="inventory",   # feed quantity only
                )
            except Exception:
                # Best-effort — don't fail the overall response.
                mbaku_history = {
                    "status": "error",
                    "data": None,
                    "error": "mbaku fnfeed history query failed",
                }

        return {
            "found": True,
            "feed_id": feed_id,
            "offer_id": offer_id,
            "node_id": node_id,
            "partition_key": partition_key,
            # ── Phase 1: feed event confirmation ──────────────────────────────
            "feed_events": {
                "summary": (
                    f"Feed '{feed_id}' was received by Wakanda with "
                    f"{len(matched)} matching event(s). "
                    f"Feed quantity reported in the event: "
                    f"{matched[0].get('feedreceived')} unit(s). "
                    f"Event timestamp: {_to_utc_dt(matched[0].get('ts'))} UTC."
                ),
                "matched_rows": matched,
                "total_events_fetched": total_fetched,
                "total_matched": len(matched),
            },
            # ── Phase 2: mbaku fnfeed qty updated in Wakanda at that time ─────
            "mbaku_fnfeed_history": {
                "description": (
                    "Feed quantity transitions recorded in mbaku fnfeed "
                    f"(±1 day around feed event: {start_date_str} → {end_date_str})."
                    if event_dt else
                    "Could not determine event timestamp — mbaku history skipped."
                ),
                "window_start": start_date_str if event_dt else None,
                "window_end":   end_date_str   if event_dt else None,
                "result": mbaku_history,
            },
        }

    return {
        "found": False,
        "feed_id": feed_id,
        "offer_id": offer_id,
        "node_id": node_id,
        "partition_key": partition_key,
        "message": (
            f"No events found matching feed '{feed_id}' for offer '{offer_id}' "
            f"at node '{node_id}'. Please verify the feed ID and offer-node "
            "combination and try again."
        ),
        "total_events_fetched": total_fetched,
    }


# ── DIAG-PREORDER-01: Preorder Eligibility ────────────────────────────────────

def get_preorder_info(offer_id: str) -> dict[str, Any]:
    """Return preorder eligibility and release date for an offer from the mbaku snapshot.

    Queries the mbaku_current_snapshot table for the given offer_id and returns
    isPreOrderEligible and releaseDate.

    Args:
        offer_id: 32-character hex Offer ID.

    Returns:
        {"status": "success", "data": <formatted string>} on success
        {"status": "no_data_found", "data": None} when the offer has no mbaku record
        {"status": "error", "data": None, "error": "..."} on failure
    """
    try:
        from google.cloud import bigquery  # type: ignore
    except ImportError:
        return {"status": "error", "data": None,
                "error": "google-cloud-bigquery is not installed"}

    if not offer_id or not str(offer_id).strip():
        return {"status": "error", "data": None, "error": "offer_id is required"}

    try:
        client, data_project, tables = _get_bq_setup()
    except Exception as exc:
        return {"status": "error", "data": None, "error": str(exc)}

    offer_id = str(offer_id).strip()

    sql = f"""
SELECT
  sId              AS offer_id,
  isPreOrderEligible,
  releaseDate
FROM {tables['mb_snapshot']}
WHERE sId = '{offer_id}'
  AND partitionId > -1
LIMIT 1
"""
    try:
        rows = list(client.query(sql).result(timeout=55))
    except Exception as exc:
        return {"status": "error", "data": None, "error": str(exc)}

    if not rows:
        return {"status": "no_data_found", "data": None}

    row = dict(rows[0])
    is_preorder_eligible = row.get("isPreOrderEligible")
    release_date         = str(row.get("releaseDate") or "") or None

    eligible_str = (
        "✅ Yes" if is_preorder_eligible is True else
        "❌ No"  if is_preorder_eligible is False else
        "Unknown"
    )

    lines: list[str] = [
        f"🛍️ Preorder Info — Offer: {offer_id}",
        "",
        f"- PreOrder Eligible : {eligible_str}",
        f"- Release Date      : {release_date or 'N/A'}",
    ]

    return {"status": "success", "data": "\n".join(lines)}
