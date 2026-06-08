"""Event-store persistence helpers for the chat path.

Thin façade that lives in the API layer because it is shaped to the
chat protocol (LangChain messages, dispatch/llm/tool event triplet).
All durable state belongs to the canonical stores in :mod:`storage`
— this module never owns a table; it only translates HTTP-side
chat events into ``event_store`` rows and reads them back.

All helpers are best-effort: a failure to persist must never break
the in-flight response.

Public surface
--------------
* ``load_chat_history(session_id)`` — return prior user/assistant turns
  in the format :func:`langchain_chat._build_chat_history_messages`
  expects.
* ``write_dispatch_event(...)`` — record the inbound user message.
* ``write_tool_events(steps, ...)`` — one ``tool`` event per LangChain
  intermediate step.
* ``write_llm_event(...)`` — record the assistant response with token
  usage and per-call telemetry.
* ``ensure_session(...)`` — idempotent session-row create.
"""
from __future__ import annotations

import json
from typing import Any, Sequence

from agent_factory.common.logging import get_logger
from storage.event_store import event_store
from storage.session_store import session_store

logger = get_logger("agent_factory_api.chat_persistence")


def _chat_history_event_limit() -> int:
    """Headroom over DEFAULT_CHAT_HISTORY_TURNS for tool/state events
    interleaved with the dispatch+llm pairs that become chat turns."""
    from agent_factory.langchain_chat import DEFAULT_CHAT_HISTORY_TURNS
    return DEFAULT_CHAT_HISTORY_TURNS * 4


async def load_chat_history(session_id: str) -> list[dict]:
    """Return prior conversation turns for ``session_id`` as msg dicts.

    Reads ``dispatch`` (user) and ``llm`` (assistant) events oldest-first
    and converts them to ``{"msg_type": "user"|"assistant", "content": str}``
    — the shape :func:`langchain_chat._build_chat_history_messages`
    expects.

    Returns an empty list when the event store is unavailable, the
    session is new, or history retrieval fails.
    """
    if not event_store.is_available:
        return []
    try:
        prior_events = await event_store.list_by_session(
            session_id, limit=_chat_history_event_limit(),
        )
        history: list[dict] = []
        for ev in prior_events:
            ev_type: str = ev.event_type if hasattr(ev, "event_type") else (ev.get("event_type") or "")
            if ev_type == "dispatch":
                im = ev.input_messages if hasattr(ev, "input_messages") else ev.get("input_messages")
                text = ""
                if isinstance(im, list) and im:
                    last = im[-1]
                    text = last.get("content", "") if isinstance(last, dict) else str(last)
                if not text:
                    dd = ev.domain_data if hasattr(ev, "domain_data") else (ev.get("domain_data") or {})
                    text = dd.get("query", "")
                if text:
                    history.append({"msg_type": "user", "content": text})
            elif ev_type == "llm":
                om = ev.output_message if hasattr(ev, "output_message") else ev.get("output_message")
                text = ""
                if isinstance(om, dict):
                    text = om.get("content", "")
                if not text:
                    dd = ev.domain_data if hasattr(ev, "domain_data") else (ev.get("domain_data") or {})
                    text = dd.get("response", "")
                if text:
                    history.append({"msg_type": "assistant", "content": text})
        return history
    except Exception as exc:
        logger.warning("chat history load failed for session=%s: %s", session_id, exc)
        return []


async def ensure_session(
    *,
    agent_id: str,
    tenant_id: str,
    session_id: str,
) -> None:
    """Idempotent session-row create.  Swallows failures."""
    if not session_store.is_available:
        return
    try:
        await session_store.create_session(
            agent_id=agent_id,
            tenant_id=tenant_id,
            session_id=session_id,
            idempotency_key=session_id,
        )
    except Exception as exc:
        logger.warning("session_store.create_session failed: %s", exc)


async def write_dispatch_event(
    *,
    session_id: str,
    agent_id: str,
    tenant_id: str,
    user_id: str,
    message_id: str,
    query: str,
    source_channel: str = "a2a",
) -> None:
    """Record the inbound user message as a ``dispatch`` event."""
    if not event_store.is_available:
        return
    try:
        await event_store.append_event(
            session_id=session_id,
            agent_id=agent_id,
            tenant_id=tenant_id,
            event_type="dispatch",
            input_messages=[{"role": "user", "content": query}],
            domain_data={
                "query": query,
                "user_id": user_id,
                "message_id": message_id,
                "source_channel": source_channel,
            },
        )
    except Exception as exc:
        logger.warning("dispatch event write failed: %s", exc)


async def write_tool_events(
    steps: Sequence[Any],
    *,
    session_id: str,
    agent_id: str,
    tenant_id: str,
) -> None:
    """Write one ``tool`` event row per LangChain intermediate step.

    Each step is a ``(AgentAction, observation)`` tuple.  Observations
    that are valid JSON strings are decoded so the dashboard can render
    their fields directly; plain strings are stored as-is.
    """
    if not event_store.is_available or not steps:
        return
    for idx, step in enumerate(steps):
        try:
            action, observation = step if isinstance(step, (tuple, list)) else (step, "")
            tool_name: str = getattr(action, "tool", "") or "unknown"
            raw_input = getattr(action, "tool_input", {})
            if isinstance(raw_input, str):
                try:
                    raw_input = json.loads(raw_input)
                except Exception:
                    raw_input = {"_raw": raw_input}
            elif raw_input is None:
                raw_input = {}

            if isinstance(observation, (dict, list)):
                obs_data: Any = observation
            elif observation is None:
                obs_data = ""
            else:
                obs_str = str(observation)
                try:
                    obs_data = json.loads(obs_str)
                except Exception:
                    obs_data = obs_str

            await event_store.append_event(
                session_id=session_id,
                agent_id=agent_id,
                tenant_id=tenant_id,
                event_type="tool",
                domain_data={
                    "tool_name": tool_name,
                    "input": raw_input,
                    "output": obs_data,
                },
            )
        except Exception as exc:
            logger.warning("tool event write (step %d) failed: %s", idx, exc)


async def write_llm_event(
    *,
    session_id: str,
    agent_id: str,
    tenant_id: str,
    user_id: str,
    content: str,
    token_usage: dict,
    llm_calls: list[dict] | None = None,
) -> None:
    """Record the assistant response as an ``llm`` event."""
    if not event_store.is_available:
        return
    llm_domain: dict = {"response": content, "user_id": user_id}
    if llm_calls:
        llm_domain["calls"] = llm_calls
    total_latency_ms = (
        sum(c.get("latency_ms") or 0 for c in (llm_calls or [])) or None
    )
    try:
        await event_store.append_event(
            session_id=session_id,
            agent_id=agent_id,
            tenant_id=tenant_id,
            event_type="llm",
            output_message={"role": "assistant", "content": content},
            input_tokens=token_usage.get("prompt_tokens", 0),
            output_tokens=token_usage.get("completion_tokens", 0),
            llm_latency_ms=total_latency_ms,
            domain_data=llm_domain,
        )
    except Exception as exc:
        logger.warning("llm event write failed: %s", exc)
