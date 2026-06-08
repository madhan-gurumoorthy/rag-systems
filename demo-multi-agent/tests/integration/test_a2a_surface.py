"""Contract tests for the A2A HTTP surface.

Boots the full FastAPI app via :class:`fastapi.testclient.TestClient`
so the lifespan registers the A2A routes, then exercises the discovery
card, the synchronous ``message/send`` flow, and the streaming
``message/stream`` flow.

The LangChain backend (`run_chat`, `run_chat_stream`) is monkey-patched
to deterministic stubs so these tests pin the protocol wire format —
JSON-RPC envelopes, Task / artifact / status-update shapes, SSE frame
ordering — without needing a live LLM, BigQuery, or Postgres.
"""
from __future__ import annotations

import json
import os
import uuid
from typing import Any, AsyncIterator

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DYNACONF_AGENT_NAME", "test-agent")
os.environ.setdefault("ENV_FOR_DYNACONF", "testing")

import app as app_module  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    """Single TestClient for the module — lifespan runs once."""
    with TestClient(app_module.app) as c:
        yield c


def _rpc_envelope(method: str, text: str, *, agent_id: str | None = None) -> dict[str, Any]:
    """Build a JSON-RPC 2.0 request body for ``message/send`` or ``message/stream``."""
    message: dict[str, Any] = {
        "kind": "message",
        "messageId": f"msg-{uuid.uuid4().hex[:12]}",
        "role": "user",
        "contextId": f"ctx-{uuid.uuid4().hex[:12]}",
        "parts": [{"kind": "text", "text": text}],
    }
    if agent_id:
        message["metadata"] = {"agent_id": agent_id}
    return {
        "jsonrpc": "2.0",
        "id": f"req-{uuid.uuid4().hex[:8]}",
        "method": method,
        "params": {"message": message},
    }


# ---------------------------------------------------------------------------
# 1. Agent card discovery
# ---------------------------------------------------------------------------


def test_agent_card_discovery(client: TestClient):
    """``GET /.well-known/agent-card.json`` returns a valid A2A AgentCard."""
    resp = client.get("/.well-known/agent-card.json")
    assert resp.status_code == 200, resp.text

    card = resp.json()
    assert card["name"], "AgentCard.name must be non-empty"
    assert card["url"].endswith("/a2a"), f"AgentCard.url must point at the RPC endpoint, got {card['url']!r}"
    assert card["protocolVersion"].startswith("0.3"), card["protocolVersion"]
    assert card["capabilities"]["streaming"] is True, "streaming must be advertised"

    skills = card.get("skills") or []
    assert skills, "AgentCard must advertise at least one skill"
    for skill in skills:
        assert skill["id"], f"skill missing id: {skill}"
        assert skill["name"], f"skill {skill['id']} missing name"
        assert isinstance(skill.get("tags"), list), f"skill {skill['id']} tags must be a list"
        assert isinstance(skill.get("inputModes"), list)
        assert isinstance(skill.get("outputModes"), list)


# ---------------------------------------------------------------------------
# 2. Sync message/send
# ---------------------------------------------------------------------------


def test_a2a_message_send_sync(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    """``POST /a2a`` with ``message/send`` returns a Task whose artifact carries the agent reply."""
    captured: dict[str, Any] = {}

    async def fake_run_chat(query, *, session_id, pack_id, chat_history, **_):
        captured["query"] = query
        captured["session_id"] = session_id
        captured["pack_id"] = pack_id
        return ("integration test reply", {})

    monkeypatch.setattr("agent_factory.langchain_chat.run_chat", fake_run_chat)

    body = _rpc_envelope("message/send", "ping")
    resp = client.post("/a2a", json=body)
    assert resp.status_code == 200, resp.text

    envelope = resp.json()
    assert envelope["jsonrpc"] == "2.0"
    assert envelope["id"] == body["id"]
    assert "error" not in envelope, envelope.get("error")

    result = envelope["result"]
    assert result["kind"] == "task"
    assert result["status"]["state"] in {"completed", "complete"}

    artifacts = result.get("artifacts") or []
    assert artifacts, f"expected at least one artifact, got {result}"
    parts = artifacts[0].get("parts") or []
    assert parts, f"artifact has no parts: {artifacts[0]}"
    text = next((p["text"] for p in parts if p.get("kind") == "text"), "")
    assert "integration test reply" in text

    # Backend received the prompt the client sent.
    assert captured["query"] == "ping"


# ---------------------------------------------------------------------------
# 3. Streaming message/stream
# ---------------------------------------------------------------------------


def _parse_sse_frames(raw: str) -> list[dict[str, Any]]:
    """Parse an SSE response body into a list of decoded JSON frames.

    Accepts both ``\\n`` and ``\\r\\n`` line endings.  A frame is a run of
    ``data:`` lines terminated by a blank line; multi-line ``data:`` payloads
    are joined per the SSE spec before JSON decoding.
    """
    normalised = raw.replace("\r\n", "\n").replace("\r", "\n")
    frames: list[dict[str, Any]] = []
    for block in normalised.split("\n\n"):
        data_lines = []
        for line in block.splitlines():
            if line.startswith("data:"):
                data_lines.append(line[len("data:"):].lstrip())
            elif line.startswith("data: "):
                data_lines.append(line[len("data: "):])
        if not data_lines:
            continue
        payload = "\n".join(data_lines)
        try:
            frames.append(json.loads(payload))
        except json.JSONDecodeError:
            continue
    return frames


def test_a2a_message_stream_sse(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    """``POST /a2a`` with ``message/stream`` emits an SSE sequence ending in a final status-update."""

    async def fake_run_chat_stream(query, *, session_id, pack_id, chat_history, **_) -> AsyncIterator:
        yield "hello "
        yield "world"
        yield ("done", {})

    async def fake_run_chat(query, *, session_id, pack_id, chat_history, **_):
        # In-process TestClient may route message/stream through the sync
        # branch of the executor's queue heuristic; this stub keeps the
        # test focused on the SSE wire contract rather than which branch
        # the SDK picks under the in-memory queue manager.
        return ("hello world", {})

    monkeypatch.setattr("agent_factory.langchain_chat.run_chat_stream", fake_run_chat_stream)
    monkeypatch.setattr("agent_factory.langchain_chat.run_chat", fake_run_chat)

    body = _rpc_envelope("message/stream", "stream please")
    with client.stream(
        "POST",
        "/a2a",
        json=body,
        headers={"Accept": "text/event-stream"},
    ) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream"), resp.headers
        raw = resp.read().decode("utf-8")

    frames = _parse_sse_frames(raw)
    assert frames, f"no SSE frames decoded from response: {raw[:300]!r}"

    # Every frame is a JSON-RPC envelope with the request id echoed back.
    for frame in frames:
        assert frame.get("jsonrpc") == "2.0"
        assert frame.get("id") == body["id"]

    results = [f["result"] for f in frames if "result" in f]
    kinds = [r.get("kind") for r in results]
    assert "task" in kinds, f"expected a 'task' frame in {kinds}"

    # At least one status-update with final=True must close the stream.
    final_updates = [r for r in results if r.get("kind") == "status-update" and r.get("final")]
    assert final_updates, f"expected a final status-update; got kinds={kinds}"

    # The streamed chunks make it into the response somewhere — either as
    # working-state messages or as the final artifact text.
    serialised = json.dumps(results)
    assert "hello" in serialised or "world" in serialised
