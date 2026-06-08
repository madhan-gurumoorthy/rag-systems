"""Tests for `agent_factory.langchain_chat`.

These tests pin the production-relevant contracts of the chat surface:

  • `run_chat` returns ``(content, team_state)`` with `_token_usage`
    populated; `_evidence` only appears when there's evidence to report
  • `run_chat` retries on retryable errors (rate limit / timeout) and
    surfaces the result of the eventually-successful attempt
  • `run_chat` returns a user-facing fallback string on connection
    errors (no exception escapes)
  • `_is_retryable_error` correctly classifies the error names the
    Walmart gateway throws
  • Token usage callback aggregates `AIMessage.usage_metadata` off the
    `LLMResult.generations` chain, including the case where the
    response handed to the callback is `None`
  • The intermediate-steps adapter skips malformed tuple entries
    instead of crashing — important because LangChain's
    `intermediate_steps` is loosely typed
  • `get_pipeline_agent_names` returns an empty list (not None and
    no exception) for unknown packs / pipelines — the streaming
    endpoint depends on that

The LangChain agent graph itself is not built — `LangChainAgentBuilder`
is patched out so the suite stays hermetic.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


# ─────────────────────────────────────────────────────────────────────
# Helpers — fake executor / fake pack
# ─────────────────────────────────────────────────────────────────────


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_pack(pack_id="test_pack"):
    pack = MagicMock()
    pack.pack_id = pack_id
    pack.config.pipelines = {
        "retrieval": SimpleNamespace(
            agents=[SimpleNamespace(name="RetrievalAgent")],
            type="round_robin",
            max_turns=10,
        ),
    }
    pack.tools_manifest = MagicMock()
    pack.tools_manifest.tools = []
    return pack


def _fake_executor(*, output="ok", intermediate_steps=None,
                   agent_name="RetrievalAgent", on_invoke=None,
                   raise_exc=None):
    """Return a fake LangChain AgentExecutor."""
    async def _ainvoke(payload, config=None):
        if on_invoke is not None:
            on_invoke(payload, config)
        if raise_exc is not None:
            raise raise_exc
        return {"output": output, "intermediate_steps": intermediate_steps or []}

    exec_ = MagicMock()
    exec_.ainvoke = AsyncMock(side_effect=_ainvoke)
    exec_.agent_name = agent_name
    return exec_


# ─────────────────────────────────────────────────────────────────────
# Error classifier
# ─────────────────────────────────────────────────────────────────────


class TestIsRetryableError:
    def test_rate_limit_is_retryable(self):
        from agent_factory.langchain_chat import _is_retryable_error

        # Use a fresh subclass so the name matches the classifier check.
        class RateLimitError(Exception):
            pass
        assert _is_retryable_error(RateLimitError("429")) is True

    def test_api_timeout_is_retryable(self):
        from agent_factory.langchain_chat import _is_retryable_error

        class APITimeoutError(Exception):
            pass
        assert _is_retryable_error(APITimeoutError("timeout")) is True

    def test_runtime_error_with_429_in_message_is_retryable(self):
        from agent_factory.langchain_chat import _is_retryable_error

        exc = RuntimeError("Upstream returned 429: rate limit exceeded")
        assert _is_retryable_error(exc) is True

    def test_runtime_error_with_unrelated_message_is_not_retryable(self):
        from agent_factory.langchain_chat import _is_retryable_error

        assert _is_retryable_error(RuntimeError("Something else broke")) is False

    def test_value_error_is_not_retryable(self):
        from agent_factory.langchain_chat import _is_retryable_error

        assert _is_retryable_error(ValueError("bad input")) is False


# ─────────────────────────────────────────────────────────────────────
# get_pipeline_agent_names — defensive defaults
# ─────────────────────────────────────────────────────────────────────


class TestGetPipelineAgentNames:
    def test_unknown_pack_returns_empty_list(self):
        from agent_factory import langchain_chat

        with patch.object(langchain_chat, "_resolve_pack", return_value=None):
            assert langchain_chat.get_pipeline_agent_names("retrieval") == []

    def test_unknown_pipeline_returns_empty_list(self):
        from agent_factory import langchain_chat

        pack = MagicMock()
        pack.config.pipelines = {}
        with patch.object(langchain_chat, "_resolve_pack", return_value=pack):
            assert langchain_chat.get_pipeline_agent_names("nope") == []

    def test_known_pipeline_returns_agent_names_in_order(self):
        from agent_factory import langchain_chat

        pack = _make_pack()
        with patch.object(langchain_chat, "_resolve_pack", return_value=pack):
            names = langchain_chat.get_pipeline_agent_names("retrieval")
        assert names == ["RetrievalAgent"]


# ─────────────────────────────────────────────────────────────────────
# Token-usage callback
# ─────────────────────────────────────────────────────────────────────


class TestTokenUsageCallback:
    def test_usage_metadata_aggregated_across_calls(self):
        """Repeated calls accumulate input/output tokens off
        ``AIMessage.usage_metadata`` on the LLMResult's generations chain."""
        from agent_factory.langchain_chat import _build_token_usage_callback

        cb = _build_token_usage_callback()
        msg = SimpleNamespace(usage_metadata={"input_tokens": 12, "output_tokens": 8})
        gen = SimpleNamespace(message=msg)
        resp = SimpleNamespace(llm_output=None, generations=[[gen]])
        cb.on_llm_end(resp)
        cb.on_llm_end(resp)
        usage = cb.usage_dict()
        assert usage == {
            "prompt_tokens": 24,
            "completion_tokens": 16,
            "total_tokens": 40,
        }

    def test_usage_metadata_shape_aggregated(self):
        from agent_factory.langchain_chat import _build_token_usage_callback

        cb = _build_token_usage_callback()
        msg = SimpleNamespace(usage_metadata={"input_tokens": 5, "output_tokens": 2})
        gen = SimpleNamespace(message=msg)
        resp = SimpleNamespace(llm_output=None, generations=[[gen]])
        cb.on_llm_end(resp)
        usage = cb.usage_dict()
        assert usage == {
            "prompt_tokens": 5,
            "completion_tokens": 2,
            "total_tokens": 7,
        }

    def test_response_none_handled_gracefully(self):
        """The callback receives `response=None` if the LLM call short-
        circuits (e.g. cache hit, mid-stream cancel).  Must not raise."""
        from agent_factory.langchain_chat import _build_token_usage_callback

        cb = _build_token_usage_callback()
        cb.on_llm_end(None)
        assert cb.usage_dict() == {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

    def test_response_with_no_usage_anywhere(self):
        """No llm_output and no generations → still produces zeros."""
        from agent_factory.langchain_chat import _build_token_usage_callback

        cb = _build_token_usage_callback()
        cb.on_llm_end(SimpleNamespace(llm_output=None, generations=[]))
        assert cb.usage_dict()["total_tokens"] == 0

    def test_langchain_callback_manager_fires_on_chat_model_start(self):
        """Verify LangChain's real CallbackManager routes through
        ``on_chat_model_start`` (not the ``on_llm_start`` fallback) so
        latency tracking is active.  The default ``BaseCallbackHandler``
        raises ``NotImplementedError`` from ``on_chat_model_start`` and
        the manager falls back to ``on_llm_start`` — our override must
        suppress that raise so the timestamp is recorded and
        ``latency_ms`` is non-None."""
        from langchain_core.callbacks.manager import CallbackManager
        from langchain_core.messages import HumanMessage
        import uuid as _uuid
        from agent_factory.langchain_chat import _build_token_usage_callback

        cb = _build_token_usage_callback()
        mgr = CallbackManager(handlers=[cb])
        run_id = _uuid.uuid4()

        run_mgrs = mgr.on_chat_model_start(
            serialized={},
            messages=[[HumanMessage(content="test")]],
            run_id=run_id,
        )

        # _call_starts populated → on_chat_model_start fired (not on_llm_start)
        assert cb._call_starts, "on_chat_model_start did not register a start time"

        msg = SimpleNamespace(
            usage_metadata={"input_tokens": 10, "output_tokens": 5},
            tool_calls=[{"id": "tc1"}],
        )
        gen = SimpleNamespace(message=msg)
        result = SimpleNamespace(generations=[[gen]])
        run_mgrs[0].on_llm_end(result)

        assert len(cb.calls) == 1
        assert cb.calls[0]["latency_ms"] is not None, (
            "latency_ms is None — on_chat_model_start did not fire before on_llm_end"
        )
        assert cb.calls[0]["tokens_in"] == 10
        assert cb.calls[0]["tool_calls_made"] == 1

    def test_per_call_entry_appended_after_llm_end(self):
        """Each on_llm_end appends one entry to cb.calls with the correct
        shape: call_num, tokens_in, tokens_out, tool_calls_made."""
        from agent_factory.langchain_chat import _build_token_usage_callback
        import uuid as _uuid

        cb = _build_token_usage_callback()
        rid = str(_uuid.uuid4())
        msg = SimpleNamespace(
            usage_metadata={"input_tokens": 10, "output_tokens": 3},
            tool_calls=[{"id": "tc1"}, {"id": "tc2"}],
        )
        gen = SimpleNamespace(message=msg)
        resp = SimpleNamespace(llm_output=None, generations=[[gen]])

        cb.on_chat_model_start(None, [], run_id=rid)
        cb.on_llm_end(resp, run_id=rid)

        assert len(cb.calls) == 1
        entry = cb.calls[0]
        assert entry["call_num"] == 1
        assert entry["tokens_in"] == 10
        assert entry["tokens_out"] == 3
        assert entry["tool_calls_made"] == 2
        assert entry["latency_ms"] is not None and entry["latency_ms"] >= 0

    def test_multiple_calls_assigned_sequential_call_nums(self):
        """call_num is assigned in on_chat_model_start order, not arrival
        order of on_llm_end — concurrent LLM calls keep separate counters."""
        from agent_factory.langchain_chat import _build_token_usage_callback
        import uuid as _uuid

        cb = _build_token_usage_callback()
        rid1 = str(_uuid.uuid4())
        rid2 = str(_uuid.uuid4())

        cb.on_chat_model_start(None, [], run_id=rid1)
        cb.on_chat_model_start(None, [], run_id=rid2)

        msg = SimpleNamespace(usage_metadata={"input_tokens": 1, "output_tokens": 1},
                              tool_calls=[])
        gen = SimpleNamespace(message=msg)
        resp = SimpleNamespace(llm_output=None, generations=[[gen]])

        cb.on_llm_end(resp, run_id=rid1)
        cb.on_llm_end(resp, run_id=rid2)

        nums = [e["call_num"] for e in cb.calls]
        assert nums == [1, 2]

    def test_llm_end_without_prior_start_still_appends_entry(self):
        """on_llm_end without a matching on_chat_model_start (e.g. cache
        hit skipped start) must not crash — latency becomes None."""
        from agent_factory.langchain_chat import _build_token_usage_callback

        cb = _build_token_usage_callback()
        msg = SimpleNamespace(usage_metadata={"input_tokens": 5, "output_tokens": 2},
                              tool_calls=[])
        gen = SimpleNamespace(message=msg)
        resp = SimpleNamespace(llm_output=None, generations=[[gen]])

        cb.on_llm_end(resp)   # no run_id, no prior on_chat_model_start

        assert len(cb.calls) == 1
        assert cb.calls[0]["latency_ms"] is None
        assert cb.calls[0]["tokens_in"] == 5

    def test_run_chat_populates_llm_calls_in_team_state(self):
        """run_chat exposes ``_llm_calls`` in team_state so the dispatcher
        can write domain_data.calls to the event store."""
        from agent_factory import langchain_chat
        import uuid as _uuid

        pack = _make_pack()
        rid = str(_uuid.uuid4())

        def _fire_callback(payload, config):
            for cb in (config or {}).get("callbacks", []):
                cb.on_chat_model_start(None, [], run_id=rid)
                msg = SimpleNamespace(
                    usage_metadata={"input_tokens": 7, "output_tokens": 3},
                    tool_calls=[{"id": "x"}],
                )
                cb.on_llm_end(
                    SimpleNamespace(llm_output=None,
                                    generations=[[SimpleNamespace(message=msg)]]),
                    run_id=rid,
                )

        exec_ = _fake_executor(output="answer", on_invoke=_fire_callback)

        with patch.object(langchain_chat, "_resolve_pack", return_value=pack), \
             patch.object(langchain_chat, "LangChainAgentBuilder") as Builder:
            Builder.return_value.build_pipeline_executor.return_value = exec_
            _, team_state = _run(langchain_chat.run_chat("hi"))

        assert "_llm_calls" in team_state
        calls = team_state["_llm_calls"]
        assert len(calls) == 1
        assert calls[0]["call_num"] == 1
        assert calls[0]["tokens_in"] == 7
        assert calls[0]["tokens_out"] == 3
        assert calls[0]["tool_calls_made"] == 1


# ─────────────────────────────────────────────────────────────────────
# intermediate_steps → evidence — native LangChain consumption
# ─────────────────────────────────────────────────────────────────────


class TestIntermediateStepsViaRunChat:
    """``run_chat`` passes the executor's ``intermediate_steps`` straight
    into ``extract_evidence``.  These tests pin the round-trip through
    the public surface."""

    def test_well_formed_step_produces_call_and_result_evidence(self):
        from agent_factory import langchain_chat

        pack = _make_pack()
        action = SimpleNamespace(
            tool="lookup_item",
            tool_input={"gtin": "00012345"},
            message_log=[],
        )
        exec_ = _fake_executor(
            output="done",
            intermediate_steps=[(action, '{"outcome":"success"}')],
        )

        with patch.object(langchain_chat, "_resolve_pack", return_value=pack), \
             patch.object(langchain_chat, "LangChainAgentBuilder") as Builder:
            Builder.return_value.build_pipeline_executor.return_value = exec_
            _, team_state = _run(langchain_chat.run_chat("hi"))

        types = [e["type"] for e in team_state["_evidence"]]
        # 1 tool_call + 1 tool_result + 1 agent_message
        assert types == ["tool_call", "tool_result", "agent_message"]
        tool_call = team_state["_evidence"][0]
        assert tool_call["tool"] == "lookup_item"
        assert tool_call["args"] == {"gtin": "00012345"}

    def test_malformed_tuple_step_is_skipped(self):
        """LangChain's intermediate_steps is loosely typed — a hostile
        tool wrapper could put a non-tuple in.  ``extract_evidence``
        must skip instead of crashing."""
        from agent_factory import langchain_chat

        pack = _make_pack()
        action = SimpleNamespace(tool="ok", tool_input={}, message_log=[])
        exec_ = _fake_executor(
            output="done",
            intermediate_steps=[
                (action, "{}"),
                12345,            # Not a tuple — must be skipped
                ("only_one",),    # Wrong-length tuple — must be skipped
            ],
        )

        with patch.object(langchain_chat, "_resolve_pack", return_value=pack), \
             patch.object(langchain_chat, "LangChainAgentBuilder") as Builder:
            Builder.return_value.build_pipeline_executor.return_value = exec_
            _, team_state = _run(langchain_chat.run_chat("hi"))

        # Only the well-formed step produces a tool_call/tool_result pair
        types = [e["type"] for e in team_state["_evidence"]]
        assert types == ["tool_call", "tool_result", "agent_message"]

    def test_call_id_resolved_from_message_log(self):
        from agent_factory import langchain_chat

        pack = _make_pack()
        action = SimpleNamespace(
            tool="ping",
            tool_input={"x": 1},
            message_log=[
                SimpleNamespace(tool_calls=[{"id": "call_abc", "name": "ping"}]),
            ],
        )
        exec_ = _fake_executor(
            output="ok", intermediate_steps=[(action, "ok")],
        )

        with patch.object(langchain_chat, "_resolve_pack", return_value=pack), \
             patch.object(langchain_chat, "LangChainAgentBuilder") as Builder:
            Builder.return_value.build_pipeline_executor.return_value = exec_
            _, team_state = _run(langchain_chat.run_chat("hi"))

        tool_call = team_state["_evidence"][0]
        assert tool_call["call_id"] == "call_abc"

    def test_str_tool_input_parsed_to_dict(self):
        """LangChain sometimes hands tool_input as a JSON string already —
        the extractor parses it so downstream consumers always see a dict."""
        from agent_factory import langchain_chat

        pack = _make_pack()
        action = SimpleNamespace(
            tool="foo",
            tool_input='{"already":"json"}',
            message_log=[],
        )
        exec_ = _fake_executor(
            output="ok", intermediate_steps=[(action, "ok")],
        )

        with patch.object(langchain_chat, "_resolve_pack", return_value=pack), \
             patch.object(langchain_chat, "LangChainAgentBuilder") as Builder:
            Builder.return_value.build_pipeline_executor.return_value = exec_
            _, team_state = _run(langchain_chat.run_chat("hi"))

        tool_call = team_state["_evidence"][0]
        assert tool_call["args"] == {"already": "json"}


# ─────────────────────────────────────────────────────────────────────
# run_chat — happy path + retry + connection-error fallback
# ─────────────────────────────────────────────────────────────────────


class TestRunChatHappyPath:
    def test_returns_content_and_token_usage(self):
        from agent_factory import langchain_chat

        pack = _make_pack()
        exec_ = _fake_executor(output="Final answer")

        def _fake_invoke(payload, config):
            # Fire the callback to populate token usage via the v1
            # AIMessage.usage_metadata shape.
            msg = SimpleNamespace(usage_metadata={
                "input_tokens": 11, "output_tokens": 4,
            })
            gen = SimpleNamespace(message=msg)
            for cb in (config or {}).get("callbacks", []):
                cb.on_llm_end(SimpleNamespace(
                    llm_output=None,
                    generations=[[gen]],
                ))

        exec_ = _fake_executor(output="Final answer", on_invoke=_fake_invoke)

        with patch.object(langchain_chat, "_resolve_pack", return_value=pack), \
             patch.object(langchain_chat, "LangChainAgentBuilder") as Builder:
            Builder.return_value.build_pipeline_executor.return_value = exec_
            content, team_state = _run(langchain_chat.run_chat("hi"))

        assert content == "Final answer"
        assert team_state["_token_usage"]["prompt_tokens"] == 11
        assert team_state["_token_usage"]["completion_tokens"] == 4
        # The final assistant text becomes a single agent_message entry
        assert team_state["_evidence"][0]["type"] == "agent_message"
        assert team_state["_evidence"][0]["agent"] == "RetrievalAgent"

    def test_empty_output_becomes_fallback_string(self):
        from agent_factory import langchain_chat

        pack = _make_pack()
        exec_ = _fake_executor(output="   ")

        with patch.object(langchain_chat, "_resolve_pack", return_value=pack), \
             patch.object(langchain_chat, "LangChainAgentBuilder") as Builder:
            Builder.return_value.build_pipeline_executor.return_value = exec_
            content, _ = _run(langchain_chat.run_chat("hi"))

        assert content == "No response generated"


class TestRunChatErrorPaths:
    def test_unknown_pack_raises_runtime_error(self):
        from agent_factory import langchain_chat

        with patch.object(langchain_chat, "_resolve_pack", return_value=None):
            with pytest.raises(RuntimeError, match="not loaded"):
                _run(langchain_chat.run_chat("hi", pack_id="nope"))

    def test_pipeline_missing_raises_runtime_error(self):
        from agent_factory import langchain_chat

        pack = _make_pack()
        with patch.object(langchain_chat, "_resolve_pack", return_value=pack), \
             patch.object(langchain_chat, "LangChainAgentBuilder") as Builder:
            Builder.return_value.build_pipeline_executor.return_value = None
            with pytest.raises(RuntimeError, match="retrieval"):
                _run(langchain_chat.run_chat("hi"))

    def test_connection_error_produces_user_facing_fallback(self):
        """The chat endpoints must never propagate connection errors
        — operators see them in logs, end users see a friendly message."""
        from agent_factory import langchain_chat

        class APIConnectionError(Exception):
            pass

        pack = _make_pack()
        exec_ = _fake_executor(raise_exc=APIConnectionError("VPN down"))

        with patch.object(langchain_chat, "_resolve_pack", return_value=pack), \
             patch.object(langchain_chat, "LangChainAgentBuilder") as Builder:
            Builder.return_value.build_pipeline_executor.return_value = exec_
            content, team_state = _run(langchain_chat.run_chat("hi"))

        assert "unable to process" in content.lower()
        assert team_state == {}

    def test_retryable_error_eventually_succeeds(self):
        """First two attempts hit a rate limit; the third succeeds."""
        from agent_factory import langchain_chat

        class RateLimitError(Exception):
            pass

        pack = _make_pack()
        call_count = {"n": 0}

        async def _flaky(payload, config=None):
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise RateLimitError("429")
            return {"output": "finally", "intermediate_steps": []}

        exec_ = MagicMock()
        exec_.ainvoke = AsyncMock(side_effect=_flaky)
        exec_.agent_name = "RetrievalAgent"

        with patch.object(langchain_chat, "_resolve_pack", return_value=pack), \
             patch.object(langchain_chat, "LangChainAgentBuilder") as Builder, \
             patch.object(langchain_chat.asyncio, "sleep", new=AsyncMock()):
            Builder.return_value.build_pipeline_executor.return_value = exec_
            content, _ = _run(langchain_chat.run_chat("hi"))

        assert content == "finally"
        assert call_count["n"] == 3

    def test_non_retryable_error_propagates(self):
        from agent_factory import langchain_chat

        pack = _make_pack()
        exec_ = _fake_executor(raise_exc=ValueError("bad payload"))

        with patch.object(langchain_chat, "_resolve_pack", return_value=pack), \
             patch.object(langchain_chat, "LangChainAgentBuilder") as Builder:
            Builder.return_value.build_pipeline_executor.return_value = exec_
            with pytest.raises(ValueError, match="bad payload"):
                _run(langchain_chat.run_chat("hi"))


# ─────────────────────────────────────────────────────────────────────
# run_chat_stream — yields chunks + ("done", team_state) sentinel
# ─────────────────────────────────────────────────────────────────────


class TestRunChatStream:
    def test_streams_chunks_then_done_sentinel(self):
        from agent_factory import langchain_chat

        pack = _make_pack()

        async def _fake_astream_events(payload, config=None, version="v2"):
            # Two chunks then a final on_chain_end with output
            yield {
                "event": "on_chat_model_stream",
                "data": {"chunk": SimpleNamespace(content="Hel")},
            }
            yield {
                "event": "on_chat_model_stream",
                "data": {"chunk": SimpleNamespace(content="lo!")},
            }
            yield {
                "event": "on_chain_end",
                "name": "AgentExecutor",
                "data": {"output": {"output": "Hello!",
                                     "intermediate_steps": []}},
            }

        exec_ = MagicMock()
        exec_.astream_events = _fake_astream_events
        exec_.agent_name = "RetrievalAgent"

        async def _collect():
            chunks = []
            sentinel = None
            with patch.object(langchain_chat, "_resolve_pack", return_value=pack), \
                 patch.object(langchain_chat, "LangChainAgentBuilder") as Builder:
                Builder.return_value.build_pipeline_executor.return_value = exec_
                async for msg in langchain_chat.run_chat_stream("hi"):
                    if isinstance(msg, tuple) and msg[0] == "done":
                        sentinel = msg
                    else:
                        chunks.append(msg)
            return chunks, sentinel

        chunks, sentinel = _run(_collect())
        assert chunks == ["Hel", "lo!"]
        assert sentinel is not None
        assert sentinel[0] == "done"
        assert "_token_usage" in sentinel[1]

    def test_connection_error_yields_fallback_then_done(self):
        from agent_factory import langchain_chat

        class APIConnectionError(Exception):
            pass

        pack = _make_pack()

        async def _failing_stream(payload, config=None, version="v2"):
            raise APIConnectionError("VPN down")
            yield  # pragma: no cover — make it an async generator

        exec_ = MagicMock()
        exec_.astream_events = _failing_stream
        exec_.agent_name = "RetrievalAgent"

        async def _collect():
            msgs = []
            with patch.object(langchain_chat, "_resolve_pack", return_value=pack), \
                 patch.object(langchain_chat, "LangChainAgentBuilder") as Builder:
                Builder.return_value.build_pipeline_executor.return_value = exec_
                async for msg in langchain_chat.run_chat_stream("hi"):
                    msgs.append(msg)
            return msgs

        msgs = _run(_collect())
        # First msg: user-facing string; last msg: done sentinel
        assert isinstance(msgs[0], str)
        assert "unable to process" in msgs[0].lower()
        assert msgs[-1] == ("done", {})


# ─────────────────────────────────────────────────────────────────────
# chat_history rehydration — multi-turn memory
# ─────────────────────────────────────────────────────────────────────


class TestBuildChatHistoryMessages:
    """`_build_chat_history_messages` converts persisted session rows into
    LangChain `HumanMessage`/`AIMessage` objects that feed the executor's
    `MessagesPlaceholder('chat_history')`.

    The contract is intentionally permissive (missing fields / unknown
    msg_types are dropped, not errored) because the caller is the
    persistence layer — chat must not 500 on a bad row."""

    def test_none_returns_empty_list(self):
        from agent_factory.langchain_chat import _build_chat_history_messages
        assert _build_chat_history_messages(None) == []

    def test_empty_sequence_returns_empty_list(self):
        from agent_factory.langchain_chat import _build_chat_history_messages
        assert _build_chat_history_messages([]) == []

    def test_single_user_row_maps_to_human_message(self):
        from langchain_core.messages import HumanMessage
        from agent_factory.langchain_chat import _build_chat_history_messages
        rows = [{"msg_type": "user", "content": "hello"}]
        msgs = _build_chat_history_messages(rows)
        assert len(msgs) == 1
        assert isinstance(msgs[0], HumanMessage)
        assert msgs[0].content == "hello"

    def test_single_assistant_row_maps_to_ai_message(self):
        from langchain_core.messages import AIMessage
        from agent_factory.langchain_chat import _build_chat_history_messages
        rows = [{"msg_type": "assistant", "content": "world"}]
        msgs = _build_chat_history_messages(rows)
        assert len(msgs) == 1
        assert isinstance(msgs[0], AIMessage)
        assert msgs[0].content == "world"

    def test_alternating_turns_preserve_order(self):
        from langchain_core.messages import AIMessage, HumanMessage
        from agent_factory.langchain_chat import _build_chat_history_messages
        rows = [
            {"msg_type": "user", "content": "q1"},
            {"msg_type": "assistant", "content": "a1"},
            {"msg_type": "user", "content": "q2"},
            {"msg_type": "assistant", "content": "a2"},
        ]
        msgs = _build_chat_history_messages(rows)
        assert [type(m) for m in msgs] == [
            HumanMessage, AIMessage, HumanMessage, AIMessage,
        ]
        assert [m.content for m in msgs] == ["q1", "a1", "q2", "a2"]

    def test_empty_content_rows_dropped(self):
        """Whitespace-only or empty content rows are skipped — they'd
        otherwise pollute the prompt with nothing useful."""
        from agent_factory.langchain_chat import _build_chat_history_messages
        rows = [
            {"msg_type": "user", "content": ""},
            {"msg_type": "user", "content": "   "},
            {"msg_type": "user", "content": None},
            {"msg_type": "user", "content": "real"},
        ]
        msgs = _build_chat_history_messages(rows)
        assert len(msgs) == 1
        assert msgs[0].content == "real"

    def test_unknown_msg_type_dropped(self):
        """system/tool/etc rows are persisted-but-not-replayed — only
        user/assistant land in chat_history."""
        from agent_factory.langchain_chat import _build_chat_history_messages
        rows = [
            {"msg_type": "user", "content": "q"},
            {"msg_type": "system", "content": "sys prompt"},
            {"msg_type": "tool", "content": '{"out":1}'},
            {"msg_type": "assistant", "content": "a"},
        ]
        msgs = _build_chat_history_messages(rows)
        assert [m.content for m in msgs] == ["q", "a"]

    def test_non_dict_rows_silently_skipped(self):
        """Defensive — `None` or stray strings in the row list must not
        crash the prompt builder."""
        from agent_factory.langchain_chat import _build_chat_history_messages
        rows = [
            None,
            "not a dict",
            12345,
            {"msg_type": "user", "content": "q"},
        ]
        msgs = _build_chat_history_messages(rows)
        assert len(msgs) == 1
        assert msgs[0].content == "q"

    def test_non_string_content_skipped(self):
        from agent_factory.langchain_chat import _build_chat_history_messages
        rows = [
            {"msg_type": "user", "content": {"obj": "not a string"}},
            {"msg_type": "user", "content": "ok"},
        ]
        msgs = _build_chat_history_messages(rows)
        assert len(msgs) == 1
        assert msgs[0].content == "ok"

    def test_max_turns_keeps_most_recent_oldest_first(self):
        """The safety net — even if persistence returns 50 rows, the
        in-runtime cap trims to the most-recent N while preserving
        oldest-first ordering (LangChain's chat_history convention)."""
        from agent_factory.langchain_chat import _build_chat_history_messages
        rows = [
            {"msg_type": "user", "content": f"msg-{i}"}
            for i in range(10)
        ]
        msgs = _build_chat_history_messages(rows, max_turns=3)
        # Most-recent 3 → indexes 7, 8, 9 in their original order
        assert [m.content for m in msgs] == ["msg-7", "msg-8", "msg-9"]

    def test_max_turns_below_or_equal_count_no_trim(self):
        from agent_factory.langchain_chat import _build_chat_history_messages
        rows = [
            {"msg_type": "user", "content": "q1"},
            {"msg_type": "assistant", "content": "a1"},
        ]
        msgs = _build_chat_history_messages(rows, max_turns=10)
        assert len(msgs) == 2

    def test_default_cap_is_20(self):
        """The exported `DEFAULT_CHAT_HISTORY_TURNS` is what app.py uses
        as the persistence-layer limit — pin it so the wiring stays
        coherent."""
        from agent_factory.langchain_chat import DEFAULT_CHAT_HISTORY_TURNS
        assert DEFAULT_CHAT_HISTORY_TURNS == 20


class TestRunChatWithHistory:
    """run_chat threads `chat_history` into the executor payload so the
    LangChain `MessagesPlaceholder('chat_history')` is populated."""

    def test_chat_history_passed_to_executor(self):
        from langchain_core.messages import AIMessage, HumanMessage
        from agent_factory import langchain_chat

        pack = _make_pack()
        captured: dict = {}

        def _capture(payload, config):
            captured["payload"] = payload

        exec_ = _fake_executor(output="ok", on_invoke=_capture)

        prior_history = [
            {"msg_type": "user", "content": "earlier question"},
            {"msg_type": "assistant", "content": "earlier answer"},
        ]

        with patch.object(langchain_chat, "_resolve_pack", return_value=pack), \
             patch.object(langchain_chat, "LangChainAgentBuilder") as Builder:
            Builder.return_value.build_pipeline_executor.return_value = exec_
            _run(langchain_chat.run_chat(
                "new question", chat_history=prior_history,
            ))

        assert "chat_history" in captured["payload"]
        history = captured["payload"]["chat_history"]
        assert len(history) == 2
        assert isinstance(history[0], HumanMessage)
        assert history[0].content == "earlier question"
        assert isinstance(history[1], AIMessage)
        assert history[1].content == "earlier answer"
        # The new query is NOT duplicated into history
        assert captured["payload"]["input"] == "new question"

    def test_no_chat_history_yields_empty_list(self):
        """Omitting the kwarg leaves chat_history empty — protects
        existing single-turn callers from accidental context pollution."""
        from agent_factory import langchain_chat

        pack = _make_pack()
        captured: dict = {}

        def _capture(payload, config):
            captured["payload"] = payload

        exec_ = _fake_executor(output="ok", on_invoke=_capture)

        with patch.object(langchain_chat, "_resolve_pack", return_value=pack), \
             patch.object(langchain_chat, "LangChainAgentBuilder") as Builder:
            Builder.return_value.build_pipeline_executor.return_value = exec_
            _run(langchain_chat.run_chat("hi"))

        assert captured["payload"].get("chat_history") == []
