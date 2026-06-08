"""Per-method unit tests for the GIF tote validation pack tools.

Covers the three pack-local modules called by ``tools.yaml``:

* ``ticket_tools.py`` — diagnostic + action wrappers around
  :class:`MatBotServicesClient`.
* ``email_sender.py`` — merchant outreach Jinja2 render + send via
  :func:`agent_factory.integrations.email.send_email`.
* ``isam_mock.py`` — thin wrapper around the shared iSAM mock that
  pins the merchant email constant.

Each test exercises one method's contract: input shape, the outcome
strings the decision matrix relies on, and the error branches the
LangChain evidence agent will see.  All upstream HTTP / Jinja2 /
config is patched so the suite never touches the network.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

# Tests under packs/<pack_id>/tests/ are 3 levels below the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from packs.gif_tote_validation import (
    email_sender as email_sender_mod,
    isam_mock,
    ticket_tools,
)
from packs.gif_tote_validation.email_sender import send_merchant_outreach
from packs.gif_tote_validation.isam_mock import (
    MOCK_MERCHANT_EMAIL,
    mock_isam_lookup,
)
from packs.gif_tote_validation.ticket_tools import (
    add_work_notes,
    fetch_ticket,
    resolve_ticket,
    set_ticket_pending,
    update_ticket,
)


# ─────────────────────────────────────────────────────────────────────
# Test doubles
# ─────────────────────────────────────────────────────────────────────


class _FakeClient:
    """Records every call and returns scripted responses or raises."""

    def __init__(
        self,
        *,
        agent: str = "",
        get_response: Any = None,
        update_response: Any = None,
        resolve_response: Any = None,
        email_response: Any = None,
        get_raise: Exception | None = None,
        update_raise: Exception | None = None,
        resolve_raise: Exception | None = None,
        email_raise: Exception | None = None,
    ) -> None:
        self.agent = agent
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._get_response = get_response or {"data": "fetched"}
        self._update_response = update_response or {"data": "updated"}
        self._resolve_response = resolve_response or {"data": "resolved"}
        self._email_response = email_response or {"success": True}
        self._get_raise = get_raise
        self._update_raise = update_raise
        self._resolve_raise = resolve_raise
        self._email_raise = email_raise

    async def ticket_get(self, ticket_ref):
        self.calls.append(("ticket_get", {"ticket_ref": ticket_ref}))
        if self._get_raise is not None:
            raise self._get_raise
        return self._get_response

    async def ticket_update(self, ticket_ref, comment):
        self.calls.append(
            ("ticket_update", {"ticket_ref": ticket_ref, "comment": comment})
        )
        if self._update_raise is not None:
            raise self._update_raise
        return self._update_response

    async def ticket_resolve(self, ticket_ref, description):
        self.calls.append(
            ("ticket_resolve",
             {"ticket_ref": ticket_ref, "description": description})
        )
        if self._resolve_raise is not None:
            raise self._resolve_raise
        return self._resolve_response


def _patch_matbot_client(monkeypatch, fake: _FakeClient) -> dict[str, Any]:
    """Replace ``MatBotServicesClient`` in ``ticket_tools`` with a recorder.

    Returns a dict ``{"agents": [...]}`` capturing every agent string
    the wrappers passed when constructing the client — proves each
    wrapper used the right per-tool attribution.
    """
    seen = {"agents": []}

    def _factory(*, agent: str):
        seen["agents"].append(agent)
        fake.agent = agent
        return fake

    monkeypatch.setattr(ticket_tools, "MatBotServicesClient", _factory)
    return seen


# ─────────────────────────────────────────────────────────────────────
# ticket_tools.py — diagnostic wrappers
# ─────────────────────────────────────────────────────────────────────


class TestFetchTicket:
    @pytest.mark.asyncio
    async def test_returns_ticket_found_envelope(self, monkeypatch):
        fake = _FakeClient(get_response={"number": "INC1", "state": "New"})
        seen = _patch_matbot_client(monkeypatch, fake)

        result = await fetch_ticket("INC1")

        assert result == {
            "data": {"number": "INC1", "state": "New"},
            "outcome": "TICKET_FOUND",
        }
        assert seen["agents"] == ["DIAG-TICKET-01"]
        assert fake.calls == [("ticket_get", {"ticket_ref": "INC1"})]

    @pytest.mark.asyncio
    async def test_service_error_returns_service_error_outcome(self, monkeypatch):
        fake = _FakeClient(
            get_raise=ticket_tools.MatBotServicesError("upstream 500")
        )
        _patch_matbot_client(monkeypatch, fake)

        result = await fetch_ticket("INC999")

        assert result["outcome"] == "SERVICE_ERROR"
        assert "upstream 500" in result["error"]
        assert "data" not in result


class TestUpdateTicket:
    @pytest.mark.asyncio
    async def test_passes_comment_through_with_qry_agent(self, monkeypatch):
        fake = _FakeClient(update_response={"updated": True})
        seen = _patch_matbot_client(monkeypatch, fake)

        result = await update_ticket("INC2", "added note")

        assert result == {
            "data": {"updated": True},
            "outcome": "UPDATE_SUCCESS",
        }
        assert seen["agents"] == ["QRY-TICKET-01"]
        assert fake.calls == [
            ("ticket_update", {"ticket_ref": "INC2", "comment": "added note"}),
        ]

    @pytest.mark.asyncio
    async def test_error_returns_update_failed(self, monkeypatch):
        fake = _FakeClient(
            update_raise=ticket_tools.MatBotServicesError("timeout")
        )
        _patch_matbot_client(monkeypatch, fake)

        result = await update_ticket("INC3", "x")

        assert result["outcome"] == "UPDATE_FAILED"
        assert "timeout" in result["error"]


class TestResolveTicket:
    @pytest.mark.asyncio
    async def test_resolves_with_description(self, monkeypatch):
        fake = _FakeClient(resolve_response={"closed": True})
        seen = _patch_matbot_client(monkeypatch, fake)

        result = await resolve_ticket("INC4", "completed by automation")

        assert result == {
            "data": {"closed": True},
            "outcome": "RESOLVE_SUCCESS",
        }
        assert seen["agents"] == ["QRY-TICKET-02"]
        assert fake.calls == [
            ("ticket_resolve",
             {"ticket_ref": "INC4", "description": "completed by automation"}),
        ]

    @pytest.mark.asyncio
    async def test_omitted_description_becomes_none(self, monkeypatch):
        fake = _FakeClient()
        _patch_matbot_client(monkeypatch, fake)

        await resolve_ticket("INC5")

        # The wrapper passes ``description or None`` so the client
        # sees an empty positional become None — preserves the
        # original contract for the optional resolution-notes field.
        assert fake.calls == [
            ("ticket_resolve", {"ticket_ref": "INC5", "description": None}),
        ]

    @pytest.mark.asyncio
    async def test_error_returns_resolve_failed(self, monkeypatch):
        fake = _FakeClient(
            resolve_raise=ticket_tools.MatBotServicesError("auth failed")
        )
        _patch_matbot_client(monkeypatch, fake)

        result = await resolve_ticket("INC6", "x")

        assert result["outcome"] == "RESOLVE_FAILED"
        assert "auth failed" in result["error"]


# ─────────────────────────────────────────────────────────────────────
# ticket_tools.py — action wrappers (post-approval)
# ─────────────────────────────────────────────────────────────────────


class TestAddWorkNotes:
    @pytest.mark.asyncio
    async def test_uses_closure_content_when_supplied(self, monkeypatch):
        fake = _FakeClient(update_response={"ok": True})
        _patch_matbot_client(monkeypatch, fake)

        result = await add_work_notes(
            external_ref="INC10",
            closure_content="approved automated note",
        )

        assert result["outcome"] == "UPDATE_SUCCESS"
        assert fake.calls == [
            ("ticket_update",
             {"ticket_ref": "INC10", "comment": "approved automated note"}),
        ]

    @pytest.mark.asyncio
    async def test_falls_back_to_default_comment_when_blank(self, monkeypatch):
        fake = _FakeClient()
        _patch_matbot_client(monkeypatch, fake)

        await add_work_notes(external_ref="INC11", closure_content="")

        assert fake.calls[0][1]["comment"] == (
            "Automated tote validation completed."
        )

    @pytest.mark.asyncio
    async def test_extra_kwargs_are_absorbed(self, monkeypatch):
        fake = _FakeClient()
        _patch_matbot_client(monkeypatch, fake)

        # Action config sometimes injects extra static params; the
        # wrapper must accept them silently.
        await add_work_notes(
            external_ref="INC12",
            closure_content="note",
            extra_action_param="ignored",
            another="also ignored",
        )

        assert len(fake.calls) == 1

    @pytest.mark.asyncio
    async def test_error_returns_update_failed(self, monkeypatch):
        fake = _FakeClient(
            update_raise=ticket_tools.MatBotServicesError("denied")
        )
        _patch_matbot_client(monkeypatch, fake)

        result = await add_work_notes(external_ref="INC13", closure_content="x")

        assert result["outcome"] == "UPDATE_FAILED"
        assert "denied" in result["error"]


class TestSetTicketPending:
    @pytest.mark.asyncio
    async def test_posts_canonical_status_change_note(self, monkeypatch):
        fake = _FakeClient()
        _patch_matbot_client(monkeypatch, fake)

        result = await set_ticket_pending(external_ref="INC20")

        assert result["outcome"] == "SET_PENDING_SUCCESS"
        assert fake.calls[0][0] == "ticket_update"
        # The status-change note must mention "Pending" so the
        # upstream automation rule fires the actual transition.
        assert "Pending" in fake.calls[0][1]["comment"]
        assert "automated by GIF Tote Validation agent" in fake.calls[0][1]["comment"]

    @pytest.mark.asyncio
    async def test_error_returns_set_pending_failed(self, monkeypatch):
        fake = _FakeClient(
            update_raise=ticket_tools.MatBotServicesError("unreachable")
        )
        _patch_matbot_client(monkeypatch, fake)

        result = await set_ticket_pending(external_ref="INC21")

        assert result["outcome"] == "SET_PENDING_FAILED"
        assert "unreachable" in result["error"]


# ─────────────────────────────────────────────────────────────────────
# email_sender.py — merchant outreach render + send
# ─────────────────────────────────────────────────────────────────────


class _CapturedTemplate:
    """Records the kwargs the production code passes to ``render``."""
    def __init__(self) -> None:
        self.render_calls: list[dict[str, Any]] = []

    def render(self, **kwargs: Any) -> str:
        self.render_calls.append(kwargs)
        return "<html>rendered</html>"


def _patch_jinja_env(monkeypatch) -> _CapturedTemplate:
    captured = _CapturedTemplate()

    class _FakeEnv:
        def get_template(self, name: str):
            assert name == "merchant_outreach.html.j2"
            return captured

    monkeypatch.setattr(email_sender_mod, "_env", _FakeEnv())
    return captured


def _patch_send_email(monkeypatch) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    async def _fake_send(**kwargs):
        calls.append(kwargs)
        return {"success": True, "to": kwargs["to_address"]}

    monkeypatch.setattr(email_sender_mod, "send_email", _fake_send)
    return calls


class TestSendMerchantOutreach:
    @pytest.mark.asyncio
    async def test_canonical_kwargs_drive_render_and_send(self, monkeypatch):
        captured = _patch_jinja_env(monkeypatch)
        sent = _patch_send_email(monkeypatch)

        result = await send_merchant_outreach(
            external_ref="INC100",
            merchant_email="m@walmart.com",
            gtin="01234567890123",
            dimensions="10x10x10 IN",
            store_report="store 1 reported issue",
            additional_context="follow-up needed",
            is_gold="true",
        )

        assert result == {"success": True, "to": "m@walmart.com"}

        # Subject and template kwargs use the canonical names.
        assert sent[0]["to_address"] == "m@walmart.com"
        assert "INC100" in sent[0]["subject"]
        assert "01234567890123" in sent[0]["subject"]
        assert sent[0]["body_html"] == "<html>rendered</html>"

        ctx = captured.render_calls[0]
        assert ctx["incident_number"] == "INC100"
        assert ctx["gtin"] == "01234567890123"
        assert ctx["item_dims"] == "10x10x10 IN"
        assert ctx["store_report"] == "store 1 reported issue"
        assert ctx["additional_context"] == "follow-up needed"
        assert ctx["is_gold"] is True

    @pytest.mark.asyncio
    async def test_legacy_aliases_resolve_to_canonical(self, monkeypatch):
        captured = _patch_jinja_env(monkeypatch)
        sent = _patch_send_email(monkeypatch)

        await send_merchant_outreach(
            to_address="legacy@walmart.com",
            incident_number="INC200",
            item_dims="9x9x9 IN",
            gtin="99999999999999",
        )

        assert sent[0]["to_address"] == "legacy@walmart.com"
        assert "INC200" in sent[0]["subject"]
        ctx = captured.render_calls[0]
        assert ctx["incident_number"] == "INC200"
        assert ctx["item_dims"] == "9x9x9 IN"

    @pytest.mark.asyncio
    async def test_canonical_kwargs_win_over_legacy(self, monkeypatch):
        captured = _patch_jinja_env(monkeypatch)
        sent = _patch_send_email(monkeypatch)

        await send_merchant_outreach(
            merchant_email="canon@walmart.com",
            to_address="legacy@walmart.com",
            external_ref="INC300",
            incident_number="INC-OLD",
            dimensions="NEW",
            item_dims="OLD",
            gtin="12345678901234",
        )

        assert sent[0]["to_address"] == "canon@walmart.com"
        assert "INC300" in sent[0]["subject"]
        ctx = captured.render_calls[0]
        assert ctx["incident_number"] == "INC300"
        assert ctx["item_dims"] == "NEW"

    @pytest.mark.asyncio
    async def test_skips_when_no_recipient(self, monkeypatch):
        _patch_jinja_env(monkeypatch)
        sent = _patch_send_email(monkeypatch)

        result = await send_merchant_outreach(
            external_ref="INC400",
            gtin="12345678901234",
            dimensions="10x10x10",
        )

        assert result["outcome"] == "SKIPPED"
        assert "no merchant email" in result["error"]
        assert sent == []

    @pytest.mark.asyncio
    async def test_skips_when_no_gtin(self, monkeypatch):
        _patch_jinja_env(monkeypatch)
        sent = _patch_send_email(monkeypatch)

        result = await send_merchant_outreach(
            external_ref="INC500",
            merchant_email="m@walmart.com",
            dimensions="10x10x10",
        )

        assert result["outcome"] == "SKIPPED"
        assert "no GTIN" in result["error"]
        assert sent == []

    @pytest.mark.asyncio
    async def test_is_gold_flag_normalisation(self, monkeypatch):
        captured = _patch_jinja_env(monkeypatch)
        _patch_send_email(monkeypatch)

        for raw, expected in (
            ("true", True),
            ("True", True),
            ("yes", True),
            ("1", True),
            ("false", False),
            ("no", False),
            ("0", False),
            ("", False),
        ):
            captured.render_calls.clear()
            await send_merchant_outreach(
                merchant_email="m@walmart.com",
                gtin="11111111111111",
                dimensions="1x1x1",
                is_gold=raw,
            )
            assert captured.render_calls[0]["is_gold"] is expected, raw

    @pytest.mark.asyncio
    async def test_cc_address_threaded_through(self, monkeypatch):
        _patch_jinja_env(monkeypatch)
        sent = _patch_send_email(monkeypatch)

        await send_merchant_outreach(
            merchant_email="m@walmart.com",
            gtin="12345678901234",
            dimensions="1x1x1",
            cc_address="cc1@walmart.com,cc2@walmart.com",
        )

        assert sent[0]["cc_address"] == "cc1@walmart.com,cc2@walmart.com"


# ─────────────────────────────────────────────────────────────────────
# isam_mock.py — thin wrapper around shared iSAM mock
# ─────────────────────────────────────────────────────────────────────


class TestIsamMock:
    def test_returns_pinned_merchant_email(self):
        result = mock_isam_lookup(gtin="12345678901234")

        # The pack pins the mock email — keeps the toy/demo flow
        # deterministic until the real iSAM API is wired.
        assert result["merchant_email"] == MOCK_MERCHANT_EMAIL
        assert MOCK_MERCHANT_EMAIL == "rajeshkumar.mohankumar@walmart.com"
        assert result["gtin"] == "12345678901234"
        assert result["action"] == "lookup_merchant_email"
        assert result["mock"] is True
        assert result["source"] == "isam_mock"

    def test_action_override_is_passed_through(self):
        result = mock_isam_lookup(
            gtin="99",
            action="update_dimensions",
            dimensions="10x10x10",
        )

        assert result["action"] == "update_dimensions"
        # Dimensions kwarg is accepted (reserved for real iSAM) but
        # does not affect the mock response shape.
        assert result["merchant_email"] == MOCK_MERCHANT_EMAIL

    def test_gtin_whitespace_is_stripped(self):
        result = mock_isam_lookup(gtin="   00012345678901   ")
        assert result["gtin"] == "00012345678901"

    def test_module_exports(self):
        # __all__ must publish exactly the two symbols the pack uses.
        assert set(isam_mock.__all__) == {"mock_isam_lookup", "MOCK_MERCHANT_EMAIL"}
