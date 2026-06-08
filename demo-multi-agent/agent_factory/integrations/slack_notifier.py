"""Slack thread notifier — REST client to MatBot Common Services.

Drives the Slack side of a work-item thread: opens the root message on
``/slack/post``, replies into the thread on ``/slack/reply``.  All
transport, auth, and policy live in the common service.

Thread tracking is layered:

  1. In-memory ``_thread_cache`` — hot path within a single process run.
  2. ``work_item.kind_data.slack_thread`` — cold-start recovery across
     process restarts; populated on the same call that creates the
     thread so any work_item tied to ``external_ref`` can recover it.
  3. Fresh ``/slack/post`` — only when both layers above miss.

Pack-level identity / formatting (``client_name``, ``thread_title_*``)
comes in via ``SlackConfig`` from pack.yaml; channel and service URL
come from settings.
"""
from __future__ import annotations

from typing import Any

from agent_factory.common.logging import get_logger
from agent_factory.infrastructure.settings import get_config
from agent_factory.integrations.matbot_services import (
    MatBotServicesClient,
    MatBotServicesError,
)

logger = get_logger("integrations.slack_notifier")


class SlackNotifier:
    """Per-work-item Slack notifier with durable thread recovery."""

    _thread_cache: dict[str, tuple[str, str]] = {}

    def __init__(self, *, slack_config: Any | None = None) -> None:
        self._channel_id = self._load_channel_id()
        # Pack-level Slack config (SlackConfig from pack.yaml)
        self._pack_slack = slack_config
        self._client = MatBotServicesClient(agent=self._agent_name())

    @staticmethod
    def _load_channel_id() -> str:
        config = get_config()
        slack_cfg = getattr(config, "slack", None)
        if slack_cfg is None:
            return ""
        return str(
            getattr(slack_cfg, "SSOT_CHANNEL_ID", "")
            or getattr(slack_cfg, "channelId", "")
            or ""
        )

    def _agent_name(self) -> str:
        if self._pack_slack is not None:
            name = getattr(self._pack_slack, "client_name", None)
            if name:
                return str(name)
        return "agent-factory"

    @property
    def enabled(self) -> bool:
        return bool(self._channel_id and self._client.enabled)

    # ── Thread resolution ──────────────────────────────────────────

    async def _resolve_or_create_thread(
        self, external_ref: str, title: str,
    ) -> tuple[str, str] | None:
        """Resolve the Slack thread for ``external_ref``, creating it if needed.

        Returns ``(channel_id, thread_ts)`` or ``None`` on failure.
        """
        if not self.enabled:
            return None

        cached = self._thread_cache.get(external_ref)
        if cached:
            return cached

        persisted = await self._load_persisted_thread(external_ref)
        if persisted:
            self._thread_cache[external_ref] = persisted
            return persisted

        channel_id = self._channel_id
        try:
            resp = await self._client.slack_post(channel=channel_id, text=title)
        except MatBotServicesError as exc:
            logger.warning(
                "slack post failed (non-fatal) external_ref=%s err=%s",
                external_ref, exc,
            )
            return None

        ts = str(resp.get("message_ts") or "")
        ch = str(resp.get("channel") or channel_id)
        if not ts:
            return None

        thread = (ch, ts)
        self._thread_cache[external_ref] = thread
        await self._persist_thread(external_ref, ch, ts)
        return thread

    @staticmethod
    async def _load_persisted_thread(
        external_ref: str,
    ) -> tuple[str, str] | None:
        """Look up ``kind_data.slack_thread`` on the work_item for this
        ``external_ref`` and return ``(channel_id, ts)`` if present.

        Returns None on any error — the caller falls through to creating
        a new thread.  This keeps Slack delivery working even when the
        work_item store is unavailable.
        """
        try:
            from storage.work_item_store import work_item_store
            if not work_item_store.is_available:
                return None
            row = await work_item_store.find_by_external_ref(external_ref)
            if not row:
                return None
            kind_data = row.get("kind_data") or {}
            saved = kind_data.get("slack_thread") if isinstance(kind_data, dict) else None
            if not isinstance(saved, dict):
                return None
            ch = saved.get("channel_id")
            ts = saved.get("ts")
            if ch and ts:
                return (str(ch), str(ts))
            return None
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "slack thread load from work_item failed (non-fatal) "
                "external_ref=%s err=%s",
                external_ref, exc,
            )
            return None

    @staticmethod
    async def _persist_thread(
        external_ref: str,
        channel_id: str,
        ts: str,
    ) -> None:
        """Merge ``slack_thread`` into the work_item's kind_data so a
        process restart can recover the thread.

        Best-effort: no-op when no work_item exists yet (typical for the
        very first ``start_thread`` call before an approval gate creates
        the row) or when the store is unavailable.
        """
        try:
            from storage.work_item_store import work_item_store
            if not work_item_store.is_available:
                return
            row = await work_item_store.find_by_external_ref(external_ref)
            if not row:
                return
            await work_item_store.merge_kind_data(
                row["work_item_id"],
                {"slack_thread": {"channel_id": channel_id, "ts": ts}},
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "slack thread persist to work_item failed (non-fatal) "
                "external_ref=%s err=%s",
                external_ref, exc,
            )

    # ── Thread title builders ──────────────────────────────────────

    def _thread_title(self, external_ref: str, ref_link: str) -> str:
        """Build thread title from pack config template or generic fallback."""
        tpl = getattr(self._pack_slack, "thread_title_template", None) if self._pack_slack else None
        if tpl:
            return tpl.format(ref_link=ref_link, external_ref=external_ref)
        return f"🔍 {ref_link} — Investigation"

    def _thread_title_fallback(self, external_ref: str) -> str:
        """Build fallback thread title (no record URL available)."""
        tpl = getattr(self._pack_slack, "thread_title_fallback", None) if self._pack_slack else None
        if tpl:
            return tpl.format(external_ref=external_ref)
        return f"🔍 *{external_ref}* — Investigation"

    # ── Public API ─────────────────────────────────────────────────

    async def start_thread(
        self,
        external_ref: str,
        short_description: str,
        record_url: str = "",
    ) -> bool:
        """Open the root Slack message for ``external_ref``."""
        if not self.enabled:
            return False
        desc_clean = short_description.strip()[:200]
        if record_url:
            ref_link = f"<{record_url}|{external_ref}>"
        else:
            ref_link = f"*{external_ref}*"
        title = self._thread_title(external_ref, ref_link)
        thread = await self._resolve_or_create_thread(
            external_ref,
            f"{title}\n{desc_clean}",
        )
        return bool(thread)

    async def reply(
        self, external_ref: str, update_text: str,
    ) -> bool:
        """Post a threaded reply for ``external_ref``."""
        if not self.enabled:
            return False
        thread = await self._resolve_or_create_thread(
            external_ref,
            self._thread_title_fallback(external_ref),
        )
        if not thread:
            return False

        channel_id, thread_ts = thread
        try:
            await self._client.slack_reply(
                channel=channel_id,
                thread_ts=thread_ts,
                text=update_text[:3000],
            )
        except MatBotServicesError as exc:
            logger.warning(
                "slack reply failed (non-fatal) external_ref=%s err=%s",
                external_ref, exc,
            )
            return False
        return True


__all__ = ["SlackNotifier"]
