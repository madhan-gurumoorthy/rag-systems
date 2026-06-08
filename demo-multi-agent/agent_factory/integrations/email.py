"""Email sender — REST client to MatBot Common Services.

Delegates outbound email to the centralised MatBot Common Services
``/email/send`` endpoint.  All SMTP policy, allowlisting, and audit
logging live in the common service; this module is a thin adapter that
maps the pack-facing ``send_email`` contract onto the service payload.

Per-call attribution flows through ``X-MatBot-Agent`` on the service
client (defaults to ``agent-factory``).
"""
from __future__ import annotations

from typing import Any

from agent_factory.common.logging import get_logger
from agent_factory.integrations.matbot_services import (
    MatBotServicesClient,
    MatBotServicesError,
)

logger = get_logger("integrations.email")


def _split_recipients(addr: str) -> list[str]:
    """Split a comma-separated address string into a clean list."""
    if not addr:
        return []
    return [piece.strip() for piece in addr.split(",") if piece.strip()]


async def send_email(
    to_address: str,
    subject: str,
    body_html: str,
    cc_address: str = "",
) -> dict[str, Any]:
    """Send an HTML email through MatBot Common Services.

    Args:
        to_address: Primary recipient email address.
        subject: Email subject line.
        body_html: Full HTML body content.
        cc_address: Optional CC recipient(s), comma-separated.

    Returns:
        dict with keys: ``success`` (bool), ``to``, ``cc``, ``subject``,
        ``error`` (str, only on failure).
    """
    client = MatBotServicesClient(agent="agent-factory")
    if not client.enabled:
        return {
            "success": False,
            "error": (
                "matbot_services.URL not configured — add "
                "[default.matbot_services] section to secrets.toml"
            ),
            "to": to_address,
            "cc": cc_address or None,
            "subject": subject,
        }

    cc_list = _split_recipients(cc_address)

    try:
        await client.email_send(
            to=[to_address],
            subject=subject,
            body=body_html,
            is_html=True,
            cc=cc_list or None,
        )
    except MatBotServicesError as exc:
        logger.error("Email send failed to=%s err=%s", to_address, exc)
        return {
            "success": False,
            "error": str(exc),
            "to": to_address,
            "cc": cc_address or None,
            "subject": subject,
        }

    logger.info("Email sent to=%s subject=%r", to_address, subject)
    return {
        "success": True,
        "to": to_address,
        "cc": cc_address or None,
        "subject": subject,
    }


__all__ = ["send_email"]
