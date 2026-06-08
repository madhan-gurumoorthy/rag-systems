"""LangChain-driven chat runtime — the production chat surface
(``run_chat``, ``run_chat_stream``, ``get_pipeline_agent_names``).

Surface
-------
* :func:`run_chat`         — synchronous one-shot.  Returns
  ``(content, team_state)`` where ``team_state`` carries token usage,
  evidence, and the LangChain result for callers that want it.
* :func:`run_chat_stream`  — async iterator yielding incremental
  content chunks, then a final ``("done", team_state)`` sentinel.
* :func:`get_pipeline_agent_names` — pack-yaml read.

Behavior notes
--------------
* Each call builds a fresh agent graph (fresh SOA signature) via
  :class:`LangChainAgentBuilder`.
* Per-request retry: connection / 429 / timeout errors retry with
  exponential backoff up to ``MAX_RETRIES``.
* Token usage is captured via a ``BaseCallbackHandler`` that reads
  ``AIMessage.usage_metadata`` — the same callback the LangGraph
  evidence node uses, so telemetry accumulates identically across
  chat and incident paths.
"""
from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator, Iterable, Sequence

from agent_factory.common.logging import get_logger
from agent_factory.evidence_extractor import extract_evidence
from agent_factory.langchain_builder import LangChainAgentBuilder
from agent_factory.pack_loader import AgentPack
from agent_factory.registry import pack_registry

logger = get_logger("langchain_chat")


# Retry config — connection / 429 / timeout errors retry with
# exponential backoff up to MAX_RETRIES.
MAX_RETRIES = 3
INITIAL_BACKOFF_SECONDS = 2.0
BACKOFF_MULTIPLIER = 2.0

# Max prior conversation turns prepended to the agent's message list.
DEFAULT_CHAT_HISTORY_TURNS = 20

_CONN_ERROR_NAMES = (
    "APIConnectionError", "APITimeoutError", "ConnectError",
    "RequestError", "ConnectTimeout", "ReadTimeout",
)


def _is_connection_error(exc: BaseException) -> bool:
    """True if `exc` (or any cause in its chain) is a connection/timeout."""
    cur: BaseException | None = exc
    while cur is not None:
        name = type(cur).__name__
        if name in _CONN_ERROR_NAMES:
            return True
        msg = str(cur).lower()
        if any(k in msg for k in (
            "timeout", "timed out", "readtimeout", "connecttimeout",
        )):
            return True
        cur = cur.__cause__
    return False


def _is_retryable_error(exc: BaseException) -> bool:
    """True if the error is worth retrying with backoff."""
    exc_name = type(exc).__name__
    exc_msg = str(exc).lower()
    if exc_name in ("RateLimitError", "APITimeoutError", "APIConnectionError"):
        return True
    if _is_connection_error(exc):
        return True
    if exc_name == "RuntimeError" and any(k in exc_msg for k in (
        "ratelimiterror", "429", "rate limit", "too many requests",
        "timeout", "timed out", "connection error", "503", "service unavailable",
    )):
        return True
    return False


def _build_token_usage_callback() -> Any:
    """Return a ``BaseCallbackHandler`` that aggregates LLM token usage and
    captures per-call telemetry.

    Attributes populated after the agent finishes:
      * ``prompt_tokens`` / ``completion_tokens`` — cumulative totals across
        all LLM calls in the request.
      * ``calls`` — ordered list of per-call dicts::

            {
              "call_num":          1,
              "tokens_in":         1842,
              "tokens_out":        47,
              "tool_calls_made":   1,
              "latency_ms":        3210,
              "response":          "",          # empty when call only invokes tools
              "tool_calls_detail": [            # one entry per tool invoked
                  {"name": "some_tool", "args": {"param_a": "...", "param_b": "..."}}
              ],
            }

    ``latency_ms`` is wall-clock time from ``on_chat_model_start`` to
    ``on_llm_end``.  Calls are keyed by LangChain ``run_id`` so concurrent
    model invocations (e.g. parallel tool fan-out) don't clobber each other.
    ``response`` holds the assistant text content; ``tool_calls_detail``
    holds the structured tool invocations so the dashboard can render both
    what the LLM said and which tools it called on each step.
    """
    import time as _time
    from langchain_core.callbacks import BaseCallbackHandler

    class _UsageCallback(BaseCallbackHandler):  # type: ignore[misc]
        def __init__(self) -> None:
            self.prompt_tokens = 0
            self.completion_tokens = 0
            self.calls: list[dict] = []
            self._call_starts: dict[str, float] = {}
            self._call_nums: dict[str, int] = {}
            self._next_call_num = 0

        def on_chat_model_start(  # type: ignore[override]
            self, serialized, messages, *, run_id=None, **kwargs
        ) -> None:
            self._next_call_num += 1
            rid = str(run_id)
            self._call_starts[rid] = _time.monotonic()
            self._call_nums[rid] = self._next_call_num

        def on_llm_end(self, response, *, run_id=None, **kwargs):  # type: ignore[override]
            if response is None:
                return
            rid = str(run_id)
            start = self._call_starts.pop(rid, None)
            latency_ms = int((_time.monotonic() - start) * 1000) if start is not None else None
            call_num = self._call_nums.pop(rid, len(self.calls) + 1)

            call_tokens_in = 0
            call_tokens_out = 0
            call_tool_calls = 0
            call_response = ""
            call_tool_calls_detail: list[dict] = []

            for gen_list in getattr(response, "generations", []) or []:
                for gen in gen_list:
                    msg = getattr(gen, "message", None)
                    if msg is None:
                        continue

                    # Token counts
                    meta = getattr(msg, "usage_metadata", None)
                    if meta:
                        call_tokens_in  += int(meta.get("input_tokens",  0) or 0)
                        call_tokens_out += int(meta.get("output_tokens", 0) or 0)

                    # Tool calls — count + structured detail for dashboard.
                    # LangChain may return tool_calls as dicts or as objects
                    # with attributes depending on the model provider / version.
                    tool_calls = getattr(msg, "tool_calls", None) or []
                    call_tool_calls += len(tool_calls)
                    for tc in tool_calls:
                        if isinstance(tc, dict):
                            name = tc.get("name") or "unknown"
                            args = tc.get("args") or {}
                        else:
                            name = getattr(tc, "name", None) or "unknown"
                            args = getattr(tc, "args", None) or {}
                        call_tool_calls_detail.append({"name": name, "args": args})

                    # Response text — last non-empty content wins
                    content = getattr(msg, "content", None)
                    if isinstance(content, str) and content:
                        call_response = content
                    elif isinstance(content, list):
                        # Multimodal content blocks — join text parts
                        text = " ".join(
                            c.get("text", "") if isinstance(c, dict) else str(c)
                            for c in content
                        ).strip()
                        if text:
                            call_response = text

            self.prompt_tokens     += call_tokens_in
            self.completion_tokens += call_tokens_out
            self.calls.append({
                "call_num":          call_num,
                "tokens_in":         call_tokens_in,
                "tokens_out":        call_tokens_out,
                "tool_calls_made":   call_tool_calls,
                "latency_ms":        latency_ms,
                "response":          call_response,
                "tool_calls_detail": call_tool_calls_detail,
            })

        def usage_dict(self) -> dict[str, int]:
            return {
                "prompt_tokens":    self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "total_tokens":     self.prompt_tokens + self.completion_tokens,
            }

    return _UsageCallback()


# ─────────────────────────────────────────────────────────────────────
# Public helpers
# ─────────────────────────────────────────────────────────────────────


def _resolve_pack(pack_id: str | None) -> AgentPack | None:
    """Resolve a pack from the registry, allowing `None` to mean default."""
    return pack_registry.get_pack(pack_id)


def _build_chat_history_messages(
    rows: Sequence[dict] | Iterable[dict] | None,
    *,
    max_turns: int = DEFAULT_CHAT_HISTORY_TURNS,
) -> list[Any]:
    """Convert persisted session rows into LangChain message objects.

    Input: oldest-first list of ``{"msg_type": "user"|"assistant", "content": str}``
    dicts from ``postgres_state_manager.get_session_messages``.  Rows with
    empty content or unknown ``msg_type`` are dropped.  If more than
    ``max_turns`` eligible rows arrive the most-recent ``max_turns`` are kept.
    """
    if not rows:
        return []

    from langchain_core.messages import AIMessage, HumanMessage

    eligible: list[Any] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        msg_type = row.get("msg_type")
        content = row.get("content") or ""
        if not isinstance(content, str) or not content.strip():
            continue
        if msg_type == "user":
            eligible.append(HumanMessage(content=content))
        elif msg_type == "assistant":
            eligible.append(AIMessage(content=content))
        # silently drop unknown msg_types (system/tool/etc) — they aren't
        # part of the user-visible conversational thread.

    if max_turns and len(eligible) > max_turns:
        eligible = eligible[-max_turns:]
    return eligible


def get_pipeline_agent_names(
    pipeline_name: str,
    *,
    pack_id: str | None = None,
) -> list[str]:
    """Return ordered agent names for a pipeline from pack.yaml.

    Used by the streaming endpoint to identify which messages belong
    to the active pipeline.
    """
    pack = _resolve_pack(pack_id)
    if pack is None:
        return []
    pipeline = pack.config.pipelines.get(pipeline_name)
    if not pipeline:
        return []
    return [a.name for a in pipeline.agents]


# ─────────────────────────────────────────────────────────────────────
# Chat — synchronous
# ─────────────────────────────────────────────────────────────────────


async def run_chat(
    query: str,
    session_id: str | None = None,
    *,
    pack_id: str | None = None,
    chat_history: Sequence[dict] | None = None,
) -> tuple[str, dict]:
    """Execute a one-shot retrieval/chat query through LangChain.

    Returns ``(content, team_state)``:
      • Retries on connection / 429 / timeout errors up to MAX_RETRIES.
      • Populates ``team_state['_token_usage']`` and ``['_evidence']``.

    Pass ``chat_history`` (from ``postgres_state_manager.get_session_messages``)
    for multi-turn memory; ``None`` / empty gives single-turn behavior.
    """
    history_messages = _build_chat_history_messages(chat_history)
    logger.info(
        "langchain_chat.run_chat: query='%s' session=%s history_turns=%d",
        query[:120], session_id, len(history_messages),
    )
    pack = _resolve_pack(pack_id)
    if pack is None:
        raise RuntimeError(
            f"Pack '{pack_id or 'default'}' not loaded. "
            f"Ensure pack_registry.discover_and_load_all() was called at startup."
        )

    last_exception: BaseException | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            executor = LangChainAgentBuilder(pack).build_pipeline_executor("retrieval")
            if executor is None:
                raise RuntimeError(
                    f"Pack '{pack.pack_id}' has no 'retrieval' pipeline "
                    f"or it has no agents configured."
                )

            callback = _build_token_usage_callback()
            agent_name = getattr(executor, "agent_name", "RetrievalAgent")

            # When the checkpointer is active the graph already carries
            # accumulated message state keyed by thread_id; passing
            # chat_history on top would double-add every prior turn via
            # the add_messages reducer.
            from agent_factory.graph.checkpointer import langgraph_checkpointer
            _use_cp = bool(session_id) and (langgraph_checkpointer.saver is not None)
            invoke_config: dict = {"callbacks": [callback]}
            if _use_cp:
                invoke_config["configurable"] = {"thread_id": session_id}
            effective_history = [] if _use_cp else history_messages

            result = await executor.ainvoke(
                {"input": query, "chat_history": effective_history},
                config=invoke_config,
            )

            content = (result.get("output") or "").strip() or "No response generated"
            intermediate_steps = result.get("intermediate_steps", []) or []
            evidence = extract_evidence(
                intermediate_steps,
                pack_id=pack.pack_id,
                final_output=content,
                agent_source=agent_name,
            )
            team_state: dict = {
                "_token_usage": callback.usage_dict(),
                "_intermediate_steps": intermediate_steps,
                "_llm_calls": list(callback.calls),
            }
            if evidence:
                team_state["_evidence"] = evidence

            logger.info("langchain_chat.run_chat completed — %d chars", len(content))
            return content, team_state

        except Exception as e:
            last_exception = e
            if _is_connection_error(e):
                logger.error("LLM connection failed: %s", e)
                return (
                    "I'm unable to process your request right now — the LLM service is unreachable. "
                    "Please check your VPN connection and try again."
                ), {}
            if _is_retryable_error(e) and attempt < MAX_RETRIES:
                wait = INITIAL_BACKOFF_SECONDS * (BACKOFF_MULTIPLIER ** (attempt - 1))
                logger.warning(
                    "Retryable error (attempt %d): %s — retrying in %.1fs",
                    attempt, e, wait,
                )
                await asyncio.sleep(wait)
                continue
            raise

    assert last_exception is not None  # for type checker
    raise last_exception


# ─────────────────────────────────────────────────────────────────────
# Chat — streaming
# ─────────────────────────────────────────────────────────────────────


async def run_chat_stream(
    query: str,
    session_id: str | None = None,
    *,
    pack_id: str | None = None,
    chat_history: Sequence[dict] | None = None,
) -> AsyncIterator[Any]:
    """Stream a retrieval/chat query token-by-token.

    Yields:
      • intermediate string chunks as the LLM emits them
        (`on_chat_model_stream` events from LangChain's v2 event API)
      • a final ``("done", team_state)`` tuple carrying token usage
        and evidence

    Caller-side error handling: connection errors produce a single
    fallback string then a ``("done", {})`` sentinel; other errors
    propagate.

    ``chat_history`` has the same contract as :func:`run_chat`.
    """
    history_messages = _build_chat_history_messages(chat_history)
    logger.info(
        "langchain_chat.run_chat_stream: query='%s' session=%s history_turns=%d",
        query[:120], session_id, len(history_messages),
    )
    pack = _resolve_pack(pack_id)
    if pack is None:
        raise RuntimeError(
            f"Pack '{pack_id or 'default'}' not loaded. "
            f"Ensure pack_registry.discover_and_load_all() was called at startup."
        )

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            executor = LangChainAgentBuilder(pack).build_pipeline_executor("retrieval")
            if executor is None:
                raise RuntimeError(
                    f"Pack '{pack.pack_id}' has no 'retrieval' pipeline "
                    f"or it has no agents configured."
                )

            callback = _build_token_usage_callback()
            agent_name = getattr(executor, "agent_name", "RetrievalAgent")
            content_buffer: list[str] = []
            intermediate_steps: list[Any] = []
            final_output = ""

            from agent_factory.graph.checkpointer import langgraph_checkpointer
            _use_cp = bool(session_id) and (langgraph_checkpointer.saver is not None)
            stream_config: dict = {"callbacks": [callback]}
            if _use_cp:
                stream_config["configurable"] = {"thread_id": session_id}
            effective_history = [] if _use_cp else history_messages

            async for event in executor.astream_events(
                {"input": query, "chat_history": effective_history},
                config=stream_config,
                version="v2",
            ):
                ev_type = event.get("event", "")
                if ev_type == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    chunk_content = getattr(chunk, "content", None)
                    if isinstance(chunk_content, str) and chunk_content:
                        content_buffer.append(chunk_content)
                        yield chunk_content
                elif ev_type == "on_chain_end" and event.get("name") == "LangGraph":
                    output = event.get("data", {}).get("output", {}) or {}
                    if isinstance(output, dict):
                        final_output = (output.get("output") or "").strip()
                        intermediate_steps = output.get("intermediate_steps", []) or []

            if not final_output:
                final_output = "".join(content_buffer).strip() or "No response generated"

            evidence = extract_evidence(
                intermediate_steps,
                pack_id=pack.pack_id,
                final_output=final_output,
                agent_source=agent_name,
            )
            team_state: dict = {
                "_token_usage": callback.usage_dict(),
                "_intermediate_steps": intermediate_steps,
                "_llm_calls": list(callback.calls),
            }
            if evidence:
                team_state["_evidence"] = evidence
            yield ("done", team_state)
            return

        except Exception as e:
            if _is_connection_error(e):
                yield "I'm unable to process your request right now — the LLM service is unreachable."
                yield ("done", {})
                return
            if _is_retryable_error(e) and attempt < MAX_RETRIES:
                wait = INITIAL_BACKOFF_SECONDS * (BACKOFF_MULTIPLIER ** (attempt - 1))
                logger.warning(
                    "Retryable error (attempt %d): %s — retrying in %.1fs",
                    attempt, e, wait,
                )
                await asyncio.sleep(wait)
                continue
            raise


__all__ = [
    "MAX_RETRIES",
    "INITIAL_BACKOFF_SECONDS",
    "BACKOFF_MULTIPLIER",
    "DEFAULT_CHAT_HISTORY_TURNS",
    "get_pipeline_agent_names",
    "run_chat",
    "run_chat_stream",
]
