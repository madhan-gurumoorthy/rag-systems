"""Tests for ``agent_factory.integrations.email.send_email``.

``send_email`` is a thin adapter onto :class:`MatBotServicesClient`.
These tests pin the contract:

  • Caller signature stays ``(to_address, subject, body_html, cc_address)``.
  • Body always sent as HTML (``is_html=True``).
  • ``cc_address`` is split on commas into a list.
  • The legacy return shape (``success``/``to``/``cc``/``subject``/``error``)
    is preserved for pack-side callers (``send_merchant_outreach``).
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_factory.integrations import email as email_module
from agent_factory.integrations.email import send_email
from agent_factory.integrations.matbot_services import MatBotServicesError


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _patch_client(monkeypatch, *, enabled=True, send_side_effect=None, send_return=None):
    """Replace the MatBotServicesClient with an AsyncMock-bearing stub."""
    fake = SimpleNamespace(
        enabled=enabled,
        email_send=AsyncMock(
            side_effect=send_side_effect,
            return_value=send_return if send_return is not None else {"sent": True},
        ),
    )
    monkeypatch.setattr(
        email_module, "MatBotServicesClient", lambda **kwargs: fake,
    )
    return fake


class TestSendEmailSuccess:
    def test_returns_success_shape(self, monkeypatch):
        fake = _patch_client(monkeypatch)
        result = _run(send_email(
            to_address="merchant@example.com",
            subject="Subj",
            body_html="<p>hi</p>",
        ))
        assert result == {
            "success": True,
            "to": "merchant@example.com",
            "cc": None,
            "subject": "Subj",
        }

    def test_calls_client_with_html_flag(self, monkeypatch):
        fake = _patch_client(monkeypatch)
        _run(send_email(
            to_address="m@x.com",
            subject="s",
            body_html="<p>b</p>",
        ))
        call = fake.email_send.await_args
        assert call.kwargs["to"] == ["m@x.com"]
        assert call.kwargs["subject"] == "s"
        assert call.kwargs["body"] == "<p>b</p>"
        assert call.kwargs["is_html"] is True
        assert call.kwargs["cc"] is None

    def test_cc_address_split_on_commas(self, monkeypatch):
        fake = _patch_client(monkeypatch)
        result = _run(send_email(
            to_address="m@x.com",
            subject="s",
            body_html="<p>b</p>",
            cc_address="a@x.com, b@x.com , c@x.com",
        ))
        # Legacy return preserves the comma-joined string verbatim
        assert result["cc"] == "a@x.com, b@x.com , c@x.com"
        # But the wire payload uses a clean list
        assert fake.email_send.await_args.kwargs["cc"] == [
            "a@x.com", "b@x.com", "c@x.com",
        ]

    def test_empty_cc_passes_none(self, monkeypatch):
        fake = _patch_client(monkeypatch)
        _run(send_email("m@x.com", "s", "<p>b</p>", cc_address=""))
        assert fake.email_send.await_args.kwargs["cc"] is None


class TestSendEmailFailures:
    def test_client_disabled_returns_failure(self, monkeypatch):
        _patch_client(monkeypatch, enabled=False)
        result = _run(send_email(
            to_address="m@x.com",
            subject="s",
            body_html="<p>b</p>",
        ))
        assert result["success"] is False
        assert "not configured" in result["error"]
        assert result["to"] == "m@x.com"
        assert result["subject"] == "s"

    def test_service_error_returns_failure_with_message(self, monkeypatch):
        _patch_client(
            monkeypatch,
            send_side_effect=MatBotServicesError("503 service unavailable"),
        )
        result = _run(send_email(
            to_address="m@x.com",
            subject="s",
            body_html="<p>b</p>",
        ))
        assert result["success"] is False
        assert "503 service unavailable" in result["error"]
        assert result["to"] == "m@x.com"
        assert result["subject"] == "s"
