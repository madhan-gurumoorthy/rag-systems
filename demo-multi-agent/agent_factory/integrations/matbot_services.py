"""HTTP client for the MatBot Common Services API (email, Slack, tickets).

All outbound email, Slack, and ticket-management traffic from agent
packs goes through the centralised MatBot Common Services layer
(FastAPI, internal-only) which enforces policy, allowlisting, and
audit logging on the server side.

Configuration (``[default.matbot_services]`` in secrets.toml):

    URL              — Base URL of the service, e.g. ``http://matbot-agent.walmart.com``
    TIMEOUT_SECONDS  — HTTP timeout (default: ``30``)

Per-call attribution flows through the ``X-MatBot-Agent`` request header
so the server-side audit can attribute every send to a specific pack.
"""
from __future__ import annotations

from typing import Any, Optional

import httpx

from agent_factory.common.logging import get_logger
from agent_factory.infrastructure.settings import get_config

logger = get_logger("integrations.matbot_services")

_DEFAULT_TIMEOUT_SECONDS = 30.0


class MatBotServicesError(Exception):
    """Raised when a MatBot Common Services call fails or returns a non-2xx."""


class MatBotServicesClient:
    """Async REST client for the MatBot Common Services API.

    Provides generic ticket, Slack, and email operations.  All API
    endpoint paths and field names are read from
    ``[default.matbot_services]`` in secrets.toml so zero upstream
    vocabulary leaks into framework code.

    Each instance is bound to a single ``agent`` name (sent as
    ``X-MatBot-Agent`` on every request).  Instances are cheap to
    construct — an ``httpx.AsyncClient`` is opened per request to
    avoid long-lived connection state across request handlers.
    """

    def __init__(
        self,
        *,
        agent: str,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> None:
        cfg = self._load_config()
        self._base_url = (base_url or cfg["url"]).rstrip("/")
        self._timeout = timeout if timeout is not None else cfg["timeout"]
        self._agent = agent
        # Ticket API contract — paths and field names from config.
        self._ticket_paths: dict[str, str] = cfg.get("ticket_paths", {})
        self._ticket_ref_param: str = cfg.get("ticket_ref_param", "ticket_ref")

    @staticmethod
    def _load_config() -> dict[str, Any]:
        config = get_config()
        section = getattr(config, "matbot_services", None)
        url = ""
        timeout = _DEFAULT_TIMEOUT_SECONDS
        ticket_paths: dict[str, str] = {}
        ticket_ref_param = "ticket_ref"
        if section is not None:
            url = str(getattr(section, "URL", "") or "")
            raw_timeout = getattr(section, "TIMEOUT_SECONDS", None)
            if raw_timeout is not None:
                try:
                    timeout = float(raw_timeout)
                except (TypeError, ValueError):
                    timeout = _DEFAULT_TIMEOUT_SECONDS
            # Ticket endpoint paths — upstream-specific vocabulary
            # stays in secrets.toml, never in framework code.
            ticket_paths = {
                "get": str(getattr(section, "TICKET_GET_PATH", "") or ""),
                "create": str(getattr(section, "TICKET_CREATE_PATH", "") or ""),
                "update": str(getattr(section, "TICKET_UPDATE_PATH", "") or ""),
                "resolve": str(getattr(section, "TICKET_RESOLVE_PATH", "") or ""),
            }
            ticket_ref_param = str(
                getattr(section, "TICKET_REF_PARAM", "") or "ticket_ref"
            )
        return {
            "url": url,
            "timeout": timeout,
            "ticket_paths": ticket_paths,
            "ticket_ref_param": ticket_ref_param,
        }

    @property
    def enabled(self) -> bool:
        return bool(self._base_url)

    def _headers(self, extra: Optional[dict[str, str]] = None) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-MatBot-Agent": self._agent,
        }
        if extra:
            headers.update(extra)
        return headers

    async def _post_json(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        extra_headers: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        if not self.enabled:
            raise MatBotServicesError(
                "matbot_services.URL not configured — add [default.matbot_services] "
                "section to secrets.toml"
            )
        url = f"{self._base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    url,
                    json=payload,
                    headers=self._headers(extra_headers),
                )
        except httpx.HTTPError as exc:
            raise MatBotServicesError(f"transport error: {exc}") from exc

        if resp.status_code >= 400:
            raise MatBotServicesError(
                f"{path} returned {resp.status_code}: {resp.text[:500]}"
            )
        try:
            return resp.json()
        except ValueError as exc:
            raise MatBotServicesError(
                f"{path} returned non-JSON body: {resp.text[:500]}"
            ) from exc

    async def _get_json(
        self,
        path: str,
        params: Optional[dict[str, str]] = None,
        *,
        extra_headers: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """HTTP GET returning JSON — used by ticket read operations."""
        if not self.enabled:
            raise MatBotServicesError(
                "matbot_services.URL not configured — add [default.matbot_services] "
                "section to secrets.toml"
            )
        url = f"{self._base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(
                    url,
                    params=params,
                    headers=self._headers(extra_headers),
                )
        except httpx.HTTPError as exc:
            raise MatBotServicesError(f"transport error: {exc}") from exc

        if resp.status_code >= 400:
            raise MatBotServicesError(
                f"{path} returned {resp.status_code}: {resp.text[:500]}"
            )
        try:
            return resp.json()
        except ValueError as exc:
            raise MatBotServicesError(
                f"{path} returned non-JSON body: {resp.text[:500]}"
            ) from exc

    # ── Ticket operations ─────────────────────────────────────────
    #
    # All endpoint paths and the reference-field name are read from
    # ``[default.matbot_services]`` in secrets.toml so the framework
    # never contains upstream-specific vocabulary.

    def _ticket_path(self, op: str) -> str:
        """Return the configured API path for a ticket operation.

        Raises ``MatBotServicesError`` when the path is not configured.
        """
        path = self._ticket_paths.get(op, "")
        if not path:
            raise MatBotServicesError(
                f"TICKET_{op.upper()}_PATH not configured in "
                "[default.matbot_services] — add it to secrets.toml"
            )
        return path

    async def ticket_get(
        self,
        ticket_ref: str,
    ) -> dict[str, Any]:
        """Fetch a ticket by its reference number.

        Uses ``TICKET_GET_PATH`` and ``TICKET_REF_PARAM`` from config.
        """
        return await self._get_json(
            self._ticket_path("get"),
            params={self._ticket_ref_param: ticket_ref},
        )

    async def ticket_create(
        self,
        description: str,
        team: str,
        summary: Optional[str] = None,
    ) -> dict[str, Any]:
        """Create a new ticket.

        Uses ``TICKET_CREATE_PATH`` from config.
        """
        payload: dict[str, Any] = {"description": description, "team": team}
        if summary:
            payload["summary"] = summary
        return await self._post_json(self._ticket_path("create"), payload)

    async def ticket_update(
        self,
        ticket_ref: str,
        comment: str,
    ) -> dict[str, Any]:
        """Add a work note / comment to an existing ticket.

        Uses ``TICKET_UPDATE_PATH`` and ``TICKET_REF_PARAM`` from config.
        """
        payload: dict[str, Any] = {
            self._ticket_ref_param: ticket_ref,
            "comment": comment,
        }
        return await self._post_json(self._ticket_path("update"), payload)

    async def ticket_resolve(
        self,
        ticket_ref: str,
        description: Optional[str] = None,
    ) -> dict[str, Any]:
        """Resolve/close a ticket by its reference number.

        Uses ``TICKET_RESOLVE_PATH`` and ``TICKET_REF_PARAM`` from config.
        """
        payload: dict[str, Any] = {self._ticket_ref_param: ticket_ref}
        if description:
            payload["description"] = description
        return await self._post_json(self._ticket_path("resolve"), payload)

    # ── Slack ──────────────────────────────────────────────────────

    async def slack_post(
        self,
        *,
        channel: str,
        text: str,
        blocks: Optional[list[dict[str, Any]]] = None,
        idempotency_key: Optional[str] = None,
    ) -> dict[str, Any]:
        """``POST /slack/post`` — open a top-level message in a channel."""
        payload: dict[str, Any] = {"channel": channel, "text": text}
        if blocks is not None:
            payload["blocks"] = blocks
        extra = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        return await self._post_json("/slack/post", payload, extra_headers=extra)

    async def slack_reply(
        self,
        *,
        channel: str,
        thread_ts: str,
        text: str,
        blocks: Optional[list[dict[str, Any]]] = None,
        broadcast: bool = False,
        idempotency_key: Optional[str] = None,
    ) -> dict[str, Any]:
        """``POST /slack/reply`` — threaded reply to an existing message."""
        payload: dict[str, Any] = {
            "channel": channel,
            "thread_ts": thread_ts,
            "text": text,
        }
        if blocks is not None:
            payload["blocks"] = blocks
        if broadcast:
            payload["broadcast"] = True
        extra = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        return await self._post_json("/slack/reply", payload, extra_headers=extra)

    # ── Email ──────────────────────────────────────────────────────

    async def email_send(
        self,
        *,
        to: list[str],
        subject: str,
        body: str,
        is_html: bool = False,
        cc: Optional[list[str]] = None,
        bcc: Optional[list[str]] = None,
        from_address: Optional[str] = None,
        reply_to: Optional[str] = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """``POST /email/send`` — send an email through the SMTP relay.

        Pass ``is_html=True`` when ``body`` is HTML.  The service derives
        the plain-text fallback automatically when only HTML is provided.
        """
        payload: dict[str, Any] = {
            "to": list(to),
            "subject": subject,
            "body": body,
            "is_html": is_html,
        }
        if cc:
            payload["cc"] = list(cc)
        if bcc:
            payload["bcc"] = list(bcc)
        if from_address:
            payload["from_address"] = from_address
        if reply_to:
            payload["reply_to"] = reply_to
        if dry_run:
            payload["dry_run"] = True
        return await self._post_json("/email/send", payload)


__all__ = ["MatBotServicesClient", "MatBotServicesError"]
