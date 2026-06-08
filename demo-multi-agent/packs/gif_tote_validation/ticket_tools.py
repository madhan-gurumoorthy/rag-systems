"""Ticket helpers for the GIF tote validation pack.

Thin async wrappers around :class:`MatBotServicesClient` that the
pack's ``tools.yaml`` references via ``type: python_function``.

Two groups of functions:

  • **Diagnostic tools** (``fetch_ticket``, ``update_ticket``,
    ``resolve_ticket``) — called by the LangChain evidence agent via
    tool-calling.  Signatures match what the LLM passes.
  • **Action tools** (``add_work_notes``, ``set_ticket_pending``) —
    called by the post-approval action node.  Signatures match
    the kwargs that ``_resolve_state_params`` builds from the
    ``approved_actions`` config in pack.yaml.
"""
from __future__ import annotations

from typing import Any

from agent_factory.integrations.matbot_services import (
    MatBotServicesClient,
    MatBotServicesError,
)


# ── Diagnostic tools (LangChain agent calls these) ──────────────────


async def fetch_ticket(ticket_ref: str) -> dict[str, Any]:
    """Fetch a ticket by its reference number."""
    client = MatBotServicesClient(agent="DIAG-TICKET-01")
    try:
        data = await client.ticket_get(ticket_ref)
        return {"data": data, "outcome": "TICKET_FOUND"}
    except MatBotServicesError as exc:
        return {"error": str(exc), "outcome": "SERVICE_ERROR"}


async def update_ticket(ticket_ref: str, comment: str) -> dict[str, Any]:
    """Add a work note / comment to an existing ticket."""
    client = MatBotServicesClient(agent="QRY-TICKET-01")
    try:
        data = await client.ticket_update(ticket_ref, comment)
        return {"data": data, "outcome": "UPDATE_SUCCESS"}
    except MatBotServicesError as exc:
        return {"error": str(exc), "outcome": "UPDATE_FAILED"}


async def resolve_ticket(
    ticket_ref: str, description: str = ""
) -> dict[str, Any]:
    """Resolve / close a ticket with optional resolution notes."""
    client = MatBotServicesClient(agent="QRY-TICKET-02")
    try:
        data = await client.ticket_resolve(ticket_ref, description or None)
        return {"data": data, "outcome": "RESOLVE_SUCCESS"}
    except MatBotServicesError as exc:
        return {"error": str(exc), "outcome": "RESOLVE_FAILED"}


# ── Action tools (post-approval action node calls these) ────────────
# Param names match what ``_resolve_state_params`` builds from the
# ``approved_actions`` config: static ``params`` + ``external_ref``
# from state (via ``requires_external_id``).


async def add_work_notes(
    external_ref: str,
    closure_content: str = "",
    **_kwargs: Any,
) -> dict[str, Any]:
    """Add work notes to a ticket (post-approval action).

    ``external_ref`` comes from state via ``requires_external_id``.
    ``closure_content`` comes from state via ``state_params``.
    Any extra kwargs from the action config are absorbed by ``**_kwargs``.
    """
    comment = closure_content or "Automated tote validation completed."
    client = MatBotServicesClient(agent="QRY-TICKET-01")
    try:
        data = await client.ticket_update(external_ref, comment)
        return {"data": data, "outcome": "UPDATE_SUCCESS"}
    except MatBotServicesError as exc:
        return {"error": str(exc), "outcome": "UPDATE_FAILED"}


async def set_ticket_pending(
    external_ref: str, **_kwargs: Any,
) -> dict[str, Any]:
    """Set a ticket to Pending status (post-approval action).

    Uses ``ticket_update`` to add a status-change work note.
    The actual state transition depends on the upstream ticket
    system's automation rules.
    """
    client = MatBotServicesClient(agent="QRY-TICKET-01")
    try:
        data = await client.ticket_update(
            external_ref,
            "Status changed to Pending — Awaiting Merchant Response "
            "(automated by GIF Tote Validation agent)",
        )
        return {"data": data, "outcome": "SET_PENDING_SUCCESS"}
    except MatBotServicesError as exc:
        return {"error": str(exc), "outcome": "SET_PENDING_FAILED"}


__all__ = [
    "fetch_ticket", "update_ticket", "resolve_ticket",
    "add_work_notes", "set_ticket_pending",
]
