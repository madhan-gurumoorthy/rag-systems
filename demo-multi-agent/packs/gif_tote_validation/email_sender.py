from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from agent_factory.common.logging import get_logger
from agent_factory.integrations.email import send_email

logger = get_logger("packs.gif_tote_validation.email_sender")

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_MERCHANT_OUTREACH_TEMPLATE = "merchant_outreach.html.j2"

_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "j2"]),
)


async def send_merchant_outreach(
    *,
    external_ref: str = "",
    merchant_email: str = "",
    gtin: str = "",
    dimensions: str = "",
    # Legacy positional-style callers (LangChain evidence agent)
    to_address: str = "",
    incident_number: str = "",
    item_dims: str = "",
    tote_dims: str = "10.5 × 13.0 × 20.5 IN, 34.55 LB max",
    gold_dims: str = "",
    supplier_dims: str = "",
    item_id: str = "",
    item_description: str = "",
    store_report: str = "",
    additional_context: str = "",
    cc_address: str = "",
    is_gold: str = "true",
    **_kwargs: Any,
) -> dict[str, Any]:
    """Render the merchant outreach template and send via MatBot Common Services.

    Accepts both action-node style kwargs (``external_ref``,
    ``merchant_email``, ``gtin``, ``dimensions``) and legacy
    LangChain-style kwargs (``to_address``, ``incident_number``,
    ``item_dims``).  Action-node names take precedence.
    """
    # Resolve to canonical names — action-node names win over legacy.
    resolved_to = merchant_email or to_address
    resolved_ref = external_ref or incident_number
    resolved_dims = dimensions or item_dims
    resolved_gtin = gtin

    if not resolved_to:
        return {"error": "no merchant email address available", "outcome": "SKIPPED"}
    if not resolved_gtin:
        return {"error": "no GTIN available", "outcome": "SKIPPED"}

    gold_flag = str(is_gold).lower() in ("true", "yes", "1")
    subject = (
        f"[Action Required] Item Dimension Review — "
        f"{resolved_ref} (GTIN: {resolved_gtin})"
    )

    body_html = _env.get_template(_MERCHANT_OUTREACH_TEMPLATE).render(
        incident_number=resolved_ref,
        gtin=resolved_gtin,
        item_dims=resolved_dims,
        tote_dims=tote_dims,
        merchant_email=resolved_to,
        gold_dims=gold_dims,
        supplier_dims=supplier_dims,
        item_id=item_id,
        item_description=item_description,
        store_report=store_report,
        additional_context=additional_context,
        is_gold=gold_flag,
    )

    return await send_email(
        to_address=resolved_to,
        subject=subject,
        body_html=body_html,
        cc_address=cc_address,
    )


__all__ = ["send_merchant_outreach"]
