"""Tests for ``agent_factory.integrations.slack_notifier.SlackNotifier``.

Thread tracking is layered:

  1. In-memory ``_thread_cache`` — hot path within a single process run.
  2. ``work_item.kind_data.slack_thread`` — cold-start recovery across
     process restarts; populated on the same call that creates the
     thread so any work_item tied to ``external_ref`` can recover it.
  3. Fresh ``/slack/post`` — only when both layers above miss.

These tests pin that contract:

  • Cache hit short-circuits: no work_item lookup, no REST round-trip.
  • ``work_item.kind_data.slack_thread`` hydration on cold-start (cache
    miss but persisted state present).
  • Total miss → ``/slack/post`` + cache populate + best-effort persist
    into ``work_item.kind_data`` via ``merge_kind_data``.
  • The module must not reference a persistent thread store (thread
    state lives only on the work_item row).
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_factory.integrations import slack_notifier as slack_notifier_module
from agent_factory.integrations.slack_notifier import SlackNotifier


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_notifier(monkeypatch) -> SlackNotifier:
    """Build a notifier with a stubbed channel + REST client so we can
    exercise ``_resolve_or_create_thread`` without any network."""
    # Reset class-level cache between tests
    SlackNotifier._thread_cache = {}

    notifier = SlackNotifier.__new__(SlackNotifier)
    notifier._channel_id = "C123"
    notifier._pack_slack = None
    notifier._client = SimpleNamespace(
        enabled=True,
        slack_post=AsyncMock(return_value={"message_ts": "1700.123", "channel": "C123"}),
        slack_reply=AsyncMock(return_value={"ok": True}),
    )
    return notifier


def _get_wis_module():
    """Return the actual ``storage.work_item_store`` module object.

    The ``storage/__init__.py`` re-exports ``work_item_store`` as an
    attribute, which shadows the module attribute on the parent package.
    Reading it via ``sys.modules`` avoids that aliasing and gives us the
    module that slack_notifier's lazy ``from storage.work_item_store
    import work_item_store`` actually consults.
    """
    import importlib
    if "storage.work_item_store" not in sys.modules:
        importlib.import_module("storage.work_item_store")
    return sys.modules["storage.work_item_store"]


def _patch_work_item_store(
    monkeypatch,
    *,
    available: bool = True,
    row_by_external_ref: dict | None = None,
    merge_recorder: list | None = None,
):
    """Stub the ``storage.work_item_store`` singleton.

    ``slack_notifier`` imports ``work_item_store`` lazily inside the
    persistence helpers; patching the attribute on the real storage
    module ensures the lazy import sees our stub.
    """
    wis_module = _get_wis_module()

    async def fake_find(external_ref, **kwargs):
        return row_by_external_ref

    async def fake_merge(work_item_id, patch, **kwargs):
        if merge_recorder is not None:
            merge_recorder.append((work_item_id, patch))
        return True

    stub = SimpleNamespace(
        is_available=available,
        find_by_external_ref=fake_find,
        merge_kind_data=fake_merge,
    )
    monkeypatch.setattr(wis_module, "work_item_store", stub)


# ─────────────────────────────────────────────────────────────────────
# Layer 1 — in-memory cache short-circuits everything else
# ─────────────────────────────────────────────────────────────────────


class TestResolveOrCreateThreadCacheHotPath:
    def test_cache_hit_skips_work_item_and_rest(self, monkeypatch):
        """If the external_ref is already in _thread_cache,
        _resolve_or_create_thread returns it verbatim without any
        work_item lookup or REST call."""
        notifier = _make_notifier(monkeypatch)
        SlackNotifier._thread_cache["INC42"] = ("C123", "1700.123")

        # Any work_item lookup / merge would be a violation of the hot-path
        merge_recorder: list = []

        async def fail_find(*a, **kw):
            raise AssertionError("work_item lookup must not happen on cache hit")

        async def fail_merge(*a, **kw):
            merge_recorder.append(a)
            return True

        wis_module = _get_wis_module()
        monkeypatch.setattr(
            wis_module,
            "work_item_store",
            SimpleNamespace(
                is_available=True,
                find_by_external_ref=fail_find,
                merge_kind_data=fail_merge,
            ),
        )

        async def fail_slack_post(**kwargs):
            raise AssertionError("slack_post must not be called on cache hit")

        notifier._client.slack_post = AsyncMock(side_effect=fail_slack_post)

        result = _run(notifier._resolve_or_create_thread("INC42", "Title"))
        assert result == ("C123", "1700.123")
        assert merge_recorder == []


# ─────────────────────────────────────────────────────────────────────
# Layer 2 — cold-start recovery from work_item.kind_data.slack_thread
# ─────────────────────────────────────────────────────────────────────


class TestResolveOrCreateThreadColdStartRecovery:
    def test_hydrates_cache_from_work_item_kind_data(self, monkeypatch):
        """After a process restart the in-memory cache is empty but the
        work_item row still carries kind_data.slack_thread — we must
        hydrate from there instead of creating a new thread."""
        notifier = _make_notifier(monkeypatch)

        _patch_work_item_store(
            monkeypatch,
            row_by_external_ref={
                "work_item_id": "wi-1",
                "kind_data": {
                    "external_ref": "INC55",
                    "slack_thread": {"channel_id": "C123", "ts": "1690.111"},
                },
            },
        )

        async def fail_slack_post(**kwargs):
            raise AssertionError(
                "slack_post must NOT be called when a thread is already "
                "persisted on the work_item — cold start should rehydrate, "
                "not duplicate the thread.",
            )
        notifier._client.slack_post = AsyncMock(side_effect=fail_slack_post)

        result = _run(notifier._resolve_or_create_thread("INC55", "Title-ignored"))
        assert result == ("C123", "1690.111")
        # In-memory cache should now be populated for the rest of the run
        assert SlackNotifier._thread_cache["INC55"] == ("C123", "1690.111")

    def test_work_item_without_slack_thread_falls_through_to_create(
        self, monkeypatch,
    ):
        """If the work_item exists but has no slack_thread yet, we must
        create a fresh thread and persist it."""
        notifier = _make_notifier(monkeypatch)

        merge_calls: list = []
        _patch_work_item_store(
            monkeypatch,
            row_by_external_ref={
                "work_item_id": "wi-2",
                "kind_data": {"external_ref": "INC66"},  # no slack_thread
            },
            merge_recorder=merge_calls,
        )

        notifier._client.slack_post = AsyncMock(
            return_value={"message_ts": "1700.222", "channel": "C123"},
        )

        result = _run(notifier._resolve_or_create_thread("INC66", "Investigation"))
        assert result == ("C123", "1700.222")
        # Persistence kicked in — merge_kind_data called once
        assert len(merge_calls) == 1
        wi_id, patch = merge_calls[0]
        assert wi_id == "wi-2"
        assert patch == {"slack_thread": {"channel_id": "C123", "ts": "1700.222"}}


# ─────────────────────────────────────────────────────────────────────
# Layer 3 — fresh /slack/post when nothing is cached/persisted
# ─────────────────────────────────────────────────────────────────────


class TestResolveOrCreateThreadFreshCreation:
    def test_no_work_item_yet_caches_only(self, monkeypatch):
        """First message in a work-item lifecycle: no work_item exists
        yet (approval gate hasn't fired).  Thread gets created and cached
        in-memory only — persistence is a best-effort no-op."""
        notifier = _make_notifier(monkeypatch)

        merge_calls: list = []
        _patch_work_item_store(
            monkeypatch,
            row_by_external_ref=None,  # no work_item yet
            merge_recorder=merge_calls,
        )

        notifier._client.slack_post = AsyncMock(
            return_value={"message_ts": "1700.999", "channel": "C123"},
        )

        result = _run(notifier._resolve_or_create_thread("INC99", "Investigation"))
        assert result == ("C123", "1700.999")
        assert SlackNotifier._thread_cache["INC99"] == ("C123", "1700.999")
        # No work_item, no merge call
        assert merge_calls == []

    def test_no_ts_returns_none_and_does_not_cache_or_persist(
        self, monkeypatch,
    ):
        """If ``/slack/post`` returns no usable ts,
        _resolve_or_create_thread returns None and neither the cache nor
        the work_item gets touched."""
        notifier = _make_notifier(monkeypatch)

        merge_calls: list = []
        _patch_work_item_store(
            monkeypatch,
            row_by_external_ref={"work_item_id": "wi-x", "kind_data": {}},
            merge_recorder=merge_calls,
        )

        notifier._client.slack_post = AsyncMock(return_value={})

        result = _run(notifier._resolve_or_create_thread("INC404", "Title"))
        assert result is None
        assert "INC404" not in SlackNotifier._thread_cache
        assert merge_calls == []

    def test_work_item_store_unavailable_falls_back_to_cache_only(
        self, monkeypatch,
    ):
        """If the work_item store isn't bound (e.g. DB outage at boot),
        _resolve_or_create_thread must still create the thread and cache
        it in memory — Slack delivery is best-effort but must not 500."""
        notifier = _make_notifier(monkeypatch)

        merge_calls: list = []
        _patch_work_item_store(
            monkeypatch,
            available=False,
            merge_recorder=merge_calls,
        )

        notifier._client.slack_post = AsyncMock(
            return_value={"message_ts": "1701.000", "channel": "C123"},
        )

        result = _run(notifier._resolve_or_create_thread("INC77", "Title"))
        assert result == ("C123", "1701.000")
        assert SlackNotifier._thread_cache["INC77"] == ("C123", "1701.000")
        assert merge_calls == []

    def test_slack_post_error_returns_none(self, monkeypatch):
        """A transport error from MatBot Common Services must be swallowed
        and surfaced as a None thread — the caller treats Slack as
        best-effort observability."""
        from agent_factory.integrations.matbot_services import MatBotServicesError

        notifier = _make_notifier(monkeypatch)
        _patch_work_item_store(monkeypatch, row_by_external_ref=None)

        notifier._client.slack_post = AsyncMock(
            side_effect=MatBotServicesError("503 service unavailable"),
        )

        result = _run(notifier._resolve_or_create_thread("INC500", "Title"))
        assert result is None
        assert "INC500" not in SlackNotifier._thread_cache


# ─────────────────────────────────────────────────────────────────────
# Public API — start_thread / reply
# ─────────────────────────────────────────────────────────────────────


class TestPublicApi:
    def test_start_thread_uses_record_url_link(self, monkeypatch):
        notifier = _make_notifier(monkeypatch)
        _patch_work_item_store(monkeypatch, row_by_external_ref=None)

        notifier._client.slack_post = AsyncMock(
            return_value={"message_ts": "1700.111", "channel": "C123"},
        )

        ok = _run(notifier.start_thread(
            "INC10", "Tote validation failed", record_url="https://snow/INC10",
        ))
        assert ok is True
        call = notifier._client.slack_post.await_args
        assert call.kwargs["channel"] == "C123"
        # Title carries the markdown link and the short description
        assert "<https://snow/INC10|INC10>" in call.kwargs["text"]
        assert "Tote validation failed" in call.kwargs["text"]

    def test_start_thread_without_record_url_uses_plain_label(
        self, monkeypatch,
    ):
        notifier = _make_notifier(monkeypatch)
        _patch_work_item_store(monkeypatch, row_by_external_ref=None)

        notifier._client.slack_post = AsyncMock(
            return_value={"message_ts": "1700.111", "channel": "C123"},
        )

        ok = _run(notifier.start_thread("INC10", "Tote failed"))
        assert ok is True
        text = notifier._client.slack_post.await_args.kwargs["text"]
        assert "*INC10*" in text

    def test_reply_in_existing_thread(self, monkeypatch):
        notifier = _make_notifier(monkeypatch)
        SlackNotifier._thread_cache["INC20"] = ("C123", "1700.222")
        _patch_work_item_store(monkeypatch, row_by_external_ref=None)

        notifier._client.slack_reply = AsyncMock(return_value={"ok": True})

        ok = _run(notifier.reply("INC20", "Diagnostics complete"))
        assert ok is True
        call = notifier._client.slack_reply.await_args
        assert call.kwargs["channel"] == "C123"
        assert call.kwargs["thread_ts"] == "1700.222"
        assert call.kwargs["text"] == "Diagnostics complete"

    def test_reply_truncates_long_text(self, monkeypatch):
        notifier = _make_notifier(monkeypatch)
        SlackNotifier._thread_cache["INC21"] = ("C123", "1700.333")
        _patch_work_item_store(monkeypatch, row_by_external_ref=None)

        notifier._client.slack_reply = AsyncMock(return_value={"ok": True})

        ok = _run(notifier.reply("INC21", "x" * 5000))
        assert ok is True
        sent = notifier._client.slack_reply.await_args.kwargs["text"]
        assert len(sent) == 3000

    def test_reply_disabled_returns_false(self, monkeypatch):
        notifier = _make_notifier(monkeypatch)
        notifier._channel_id = ""  # disabled

        ok = _run(notifier.reply("INC30", "anything"))
        assert ok is False

    def test_reply_swallows_reply_error(self, monkeypatch):
        """A failed reply must surface as ``False`` — the caller path
        must never see the underlying ``MatBotServicesError``."""
        from agent_factory.integrations.matbot_services import MatBotServicesError

        notifier = _make_notifier(monkeypatch)
        SlackNotifier._thread_cache["INC31"] = ("C123", "1700.444")
        _patch_work_item_store(monkeypatch, row_by_external_ref=None)

        notifier._client.slack_reply = AsyncMock(
            side_effect=MatBotServicesError("502 bad gateway"),
        )

        ok = _run(notifier.reply("INC31", "update text"))
        assert ok is False


# ─────────────────────────────────────────────────────────────────────
# Pack-level identity (X-MatBot-Agent) and title templates
# ─────────────────────────────────────────────────────────────────────


class TestPackConfig:
    def test_agent_name_defaults_to_agent_factory(self, monkeypatch):
        notifier = _make_notifier(monkeypatch)
        assert notifier._agent_name() == "agent-factory"

    def test_agent_name_uses_pack_client_name(self, monkeypatch):
        notifier = _make_notifier(monkeypatch)
        notifier._pack_slack = SimpleNamespace(client_name="gif-tote-pack")
        assert notifier._agent_name() == "gif-tote-pack"

    def test_thread_title_uses_pack_template(self, monkeypatch):
        notifier = _make_notifier(monkeypatch)
        notifier._pack_slack = SimpleNamespace(
            thread_title_template="🚨 {ref_link} GIF tote review",
        )
        title = notifier._thread_title("INC10", "<url|INC10>")
        assert title == "🚨 <url|INC10> GIF tote review"

    def test_thread_title_fallback_uses_pack_template(self, monkeypatch):
        notifier = _make_notifier(monkeypatch)
        notifier._pack_slack = SimpleNamespace(
            thread_title_fallback="🚨 {external_ref} fallback",
        )
        assert notifier._thread_title_fallback("INC10") == "🚨 INC10 fallback"


# ─────────────────────────────────────────────────────────────────────
# Regression guard: no persistent thread store
# ─────────────────────────────────────────────────────────────────────


class TestNoSlackThreadStoreImport:
    """Slack thread persistence lives only on ``work_item.kind_data``.
    Guard against accidentally introducing a separate ``slack_thread_store``."""

    def test_module_does_not_reference_slack_thread_store(self):
        src = Path(slack_notifier_module.__file__).read_text(encoding="utf-8")
        assert "slack_thread_store" not in src, (
            "slack_notifier.py must not import or reference slack_thread_store — "
            "thread persistence lives on work_item.kind_data.slack_thread."
        )

    def test_storage_package_does_not_expose_slack_thread_store(self):
        """``storage`` must not expose a ``slack_thread_store`` attribute."""
        import storage
        assert not hasattr(storage, "slack_thread_store")
