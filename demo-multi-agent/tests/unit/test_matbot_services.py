"""Tests for ``agent_factory.integrations.matbot_services.MatBotServicesClient``.

The client is an async REST adapter for the MatBot Common Services
FastAPI: ``/email/send``, ``/slack/post``, ``/slack/reply``.  Tests pin
the wire contract — payload shape, headers, error mapping — without
hitting the network.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_factory.integrations.matbot_services import (
    MatBotServicesClient,
    MatBotServicesError,
)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _stub_config(url: str = "http://matbot.test", timeout: float | str = 30.0):
    """Patch ``get_config`` so the client reads predictable values."""
    section = SimpleNamespace(URL=url, TIMEOUT_SECONDS=timeout)
    config = SimpleNamespace(matbot_services=section)
    return patch(
        "agent_factory.integrations.matbot_services.get_config",
        return_value=config,
    )


class _FakeResponse:
    def __init__(self, status_code: int, body: dict | str | None = None):
        self.status_code = status_code
        self._body = body
        self.text = body if isinstance(body, str) else ""

    def json(self):
        if isinstance(self._body, dict):
            return self._body
        if self._body is None:
            return {}
        raise ValueError("not JSON")


class _FakeAsyncClient:
    """Drop-in for ``httpx.AsyncClient`` that records the last POST."""

    last_call: dict = {}

    def __init__(self, *args, **kwargs):
        self.timeout = kwargs.get("timeout")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, *, json, headers):
        _FakeAsyncClient.last_call = {
            "url": url,
            "json": json,
            "headers": headers,
            "timeout": self.timeout,
        }
        return _FakeAsyncClient.next_response


# ─────────────────────────────────────────────────────────────────────
# Configuration loading
# ─────────────────────────────────────────────────────────────────────


class TestConfigLoading:
    def test_reads_url_and_timeout_from_config(self):
        with _stub_config("http://matbot.test", "45"):
            client = MatBotServicesClient(agent="agent-factory")
            assert client._base_url == "http://matbot.test"
            assert client._timeout == 45.0

    def test_trailing_slash_stripped(self):
        with _stub_config("http://matbot.test/"):
            client = MatBotServicesClient(agent="agent-factory")
            assert client._base_url == "http://matbot.test"

    def test_timeout_falls_back_to_default_on_invalid_value(self):
        with _stub_config("http://matbot.test", "not-a-number"):
            client = MatBotServicesClient(agent="agent-factory")
            assert client._timeout == 30.0

    def test_enabled_false_when_url_missing(self):
        with _stub_config(""):
            client = MatBotServicesClient(agent="agent-factory")
            assert client.enabled is False

    def test_enabled_true_when_url_present(self):
        with _stub_config("http://matbot.test"):
            client = MatBotServicesClient(agent="agent-factory")
            assert client.enabled is True

    def test_explicit_base_url_overrides_config(self):
        with _stub_config("http://from-config"):
            client = MatBotServicesClient(
                agent="agent-factory", base_url="http://override",
            )
            assert client._base_url == "http://override"


# ─────────────────────────────────────────────────────────────────────
# Headers
# ─────────────────────────────────────────────────────────────────────


class TestHeaders:
    def test_default_headers_include_agent(self):
        with _stub_config("http://matbot.test"):
            client = MatBotServicesClient(agent="my-pack")
            headers = client._headers()
            assert headers["Content-Type"] == "application/json"
            assert headers["Accept"] == "application/json"
            assert headers["X-MatBot-Agent"] == "my-pack"

    def test_extra_headers_merged(self):
        with _stub_config("http://matbot.test"):
            client = MatBotServicesClient(agent="my-pack")
            headers = client._headers({"Idempotency-Key": "abc"})
            assert headers["Idempotency-Key"] == "abc"
            assert headers["X-MatBot-Agent"] == "my-pack"


# ─────────────────────────────────────────────────────────────────────
# _post_json — transport + error mapping
# ─────────────────────────────────────────────────────────────────────


class TestPostJson:
    def test_raises_when_not_configured(self):
        with _stub_config(""):
            client = MatBotServicesClient(agent="x")
            with pytest.raises(MatBotServicesError, match="not configured"):
                _run(client._post_json("/slack/post", {"foo": "bar"}))

    def test_posts_to_full_url_with_payload_and_headers(self, monkeypatch):
        _FakeAsyncClient.next_response = _FakeResponse(200, {"ok": True})
        with _stub_config("http://matbot.test"):
            monkeypatch.setattr(
                "agent_factory.integrations.matbot_services.httpx.AsyncClient",
                _FakeAsyncClient,
            )
            client = MatBotServicesClient(agent="agent-factory")
            result = _run(client._post_json("/slack/post", {"channel": "C1"}))
            assert result == {"ok": True}
            assert _FakeAsyncClient.last_call["url"] == "http://matbot.test/slack/post"
            assert _FakeAsyncClient.last_call["json"] == {"channel": "C1"}
            assert _FakeAsyncClient.last_call["headers"]["X-MatBot-Agent"] == "agent-factory"

    def test_transport_error_wrapped(self, monkeypatch):
        class _BrokenClient(_FakeAsyncClient):
            async def post(self, url, *, json, headers):
                raise httpx.ConnectError("unreachable")

        with _stub_config("http://matbot.test"):
            monkeypatch.setattr(
                "agent_factory.integrations.matbot_services.httpx.AsyncClient",
                _BrokenClient,
            )
            client = MatBotServicesClient(agent="agent-factory")
            with pytest.raises(MatBotServicesError, match="transport error"):
                _run(client._post_json("/slack/post", {}))

    def test_non_2xx_status_raised(self, monkeypatch):
        _FakeAsyncClient.next_response = _FakeResponse(500, "internal error")
        with _stub_config("http://matbot.test"):
            monkeypatch.setattr(
                "agent_factory.integrations.matbot_services.httpx.AsyncClient",
                _FakeAsyncClient,
            )
            client = MatBotServicesClient(agent="agent-factory")
            with pytest.raises(MatBotServicesError, match="500"):
                _run(client._post_json("/slack/post", {}))

    def test_non_json_body_raised(self, monkeypatch):
        _FakeAsyncClient.next_response = _FakeResponse(200, "not json")
        with _stub_config("http://matbot.test"):
            monkeypatch.setattr(
                "agent_factory.integrations.matbot_services.httpx.AsyncClient",
                _FakeAsyncClient,
            )
            client = MatBotServicesClient(agent="agent-factory")
            with pytest.raises(MatBotServicesError, match="non-JSON"):
                _run(client._post_json("/slack/post", {}))


# ─────────────────────────────────────────────────────────────────────
# slack_post / slack_reply payload shape
# ─────────────────────────────────────────────────────────────────────


class TestSlackEndpoints:
    def test_slack_post_minimal_payload(self, monkeypatch):
        _FakeAsyncClient.next_response = _FakeResponse(
            200, {"message_ts": "1700.1", "channel": "C123"},
        )
        with _stub_config("http://matbot.test"):
            monkeypatch.setattr(
                "agent_factory.integrations.matbot_services.httpx.AsyncClient",
                _FakeAsyncClient,
            )
            client = MatBotServicesClient(agent="agent-factory")
            result = _run(client.slack_post(channel="C123", text="hi"))
            assert result == {"message_ts": "1700.1", "channel": "C123"}
            assert _FakeAsyncClient.last_call["url"].endswith("/slack/post")
            assert _FakeAsyncClient.last_call["json"] == {
                "channel": "C123", "text": "hi",
            }
            # No idempotency header unless requested
            assert "Idempotency-Key" not in _FakeAsyncClient.last_call["headers"]

    def test_slack_post_with_blocks_and_idempotency_key(self, monkeypatch):
        _FakeAsyncClient.next_response = _FakeResponse(200, {})
        with _stub_config("http://matbot.test"):
            monkeypatch.setattr(
                "agent_factory.integrations.matbot_services.httpx.AsyncClient",
                _FakeAsyncClient,
            )
            client = MatBotServicesClient(agent="agent-factory")
            _run(client.slack_post(
                channel="C1",
                text="hi",
                blocks=[{"type": "section"}],
                idempotency_key="key-abc",
            ))
            assert _FakeAsyncClient.last_call["json"]["blocks"] == [{"type": "section"}]
            assert _FakeAsyncClient.last_call["headers"]["Idempotency-Key"] == "key-abc"

    def test_slack_reply_required_fields(self, monkeypatch):
        _FakeAsyncClient.next_response = _FakeResponse(200, {"ok": True})
        with _stub_config("http://matbot.test"):
            monkeypatch.setattr(
                "agent_factory.integrations.matbot_services.httpx.AsyncClient",
                _FakeAsyncClient,
            )
            client = MatBotServicesClient(agent="agent-factory")
            _run(client.slack_reply(
                channel="C1", thread_ts="1700.0", text="update",
            ))
            payload = _FakeAsyncClient.last_call["json"]
            assert payload == {
                "channel": "C1", "thread_ts": "1700.0", "text": "update",
            }

    def test_slack_reply_broadcast_flag(self, monkeypatch):
        _FakeAsyncClient.next_response = _FakeResponse(200, {})
        with _stub_config("http://matbot.test"):
            monkeypatch.setattr(
                "agent_factory.integrations.matbot_services.httpx.AsyncClient",
                _FakeAsyncClient,
            )
            client = MatBotServicesClient(agent="agent-factory")
            _run(client.slack_reply(
                channel="C1", thread_ts="1700.0", text="up", broadcast=True,
            ))
            assert _FakeAsyncClient.last_call["json"]["broadcast"] is True


# ─────────────────────────────────────────────────────────────────────
# email_send payload shape
# ─────────────────────────────────────────────────────────────────────


class TestEmailEndpoint:
    def test_email_send_minimal_payload(self, monkeypatch):
        _FakeAsyncClient.next_response = _FakeResponse(200, {"sent": True})
        with _stub_config("http://matbot.test"):
            monkeypatch.setattr(
                "agent_factory.integrations.matbot_services.httpx.AsyncClient",
                _FakeAsyncClient,
            )
            client = MatBotServicesClient(agent="agent-factory")
            result = _run(client.email_send(
                to=["a@example.com"],
                subject="Hello",
                body="World",
            ))
            assert result == {"sent": True}
            assert _FakeAsyncClient.last_call["url"].endswith("/email/send")
            assert _FakeAsyncClient.last_call["json"] == {
                "to": ["a@example.com"],
                "subject": "Hello",
                "body": "World",
                "is_html": False,
            }

    def test_email_send_with_html_and_cc_bcc(self, monkeypatch):
        _FakeAsyncClient.next_response = _FakeResponse(200, {"sent": True})
        with _stub_config("http://matbot.test"):
            monkeypatch.setattr(
                "agent_factory.integrations.matbot_services.httpx.AsyncClient",
                _FakeAsyncClient,
            )
            client = MatBotServicesClient(agent="agent-factory")
            _run(client.email_send(
                to=["a@example.com"],
                subject="Hi",
                body="<p>hi</p>",
                is_html=True,
                cc=["b@example.com"],
                bcc=["c@example.com"],
                from_address="agent@walmart.com",
                reply_to="noreply@walmart.com",
                dry_run=True,
            ))
            payload = _FakeAsyncClient.last_call["json"]
            assert payload["is_html"] is True
            assert payload["cc"] == ["b@example.com"]
            assert payload["bcc"] == ["c@example.com"]
            assert payload["from_address"] == "agent@walmart.com"
            assert payload["reply_to"] == "noreply@walmart.com"
            assert payload["dry_run"] is True

    def test_email_send_omits_empty_optional_fields(self, monkeypatch):
        _FakeAsyncClient.next_response = _FakeResponse(200, {"sent": True})
        with _stub_config("http://matbot.test"):
            monkeypatch.setattr(
                "agent_factory.integrations.matbot_services.httpx.AsyncClient",
                _FakeAsyncClient,
            )
            client = MatBotServicesClient(agent="agent-factory")
            _run(client.email_send(
                to=["a@example.com"],
                subject="x",
                body="y",
                cc=None,
                bcc=None,
                dry_run=False,
            ))
            payload = _FakeAsyncClient.last_call["json"]
            assert "cc" not in payload
            assert "bcc" not in payload
            assert "from_address" not in payload
            assert "reply_to" not in payload
            assert "dry_run" not in payload
