"""Tests for `agent_factory.langchain_builder`.

These tests pin:

  • stub provider: `provider="stub"` returns a fake chat model so
    offline / test packs keep working without hitting the Walmart
    gateway
  • `build_pipeline_executor` returns None when the pipeline doesn't
    exist or has no agents — endpoints rely on this to surface
    "pack misconfigured" errors instead of crashing on AttributeError
  • `build_pipeline_executor` and `build_single_executor` both call
    `langchain.agents.create_agent` with the rendered system prompt;
    chat history (when supplied) is prepended by the adapter at
    invocation time
  • agent_name is stamped onto the returned executor so callers can
    label the final AIMessage with the agent's pack-yaml name

The model client itself isn't built — these tests patch
`build_langchain_model_client` and the LangChain agent constructors so
the suite stays hermetic and immune to version drift.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


# ─────────────────────────────────────────────────────────────────────
# Fake pack — minimal AgentPack-like object exposing only what the
# builder actually reads.  Keeps tests free of pack_loader / YAML I/O.
# ─────────────────────────────────────────────────────────────────────


def _agent_spec(name="RetrievalAgent", role="retrieval",
                prompt_file="retrieval.j2", tools=None):
    return SimpleNamespace(
        name=name,
        role=role,
        prompt_file=prompt_file,
        tools=tools or [],
    )


def _pipeline(agents, ptype="round_robin", max_turns=10):
    return SimpleNamespace(agents=agents, type=ptype, max_turns=max_turns)


def _make_pack(*, provider="stub", pipelines=None, prompts=None,
               temperature=0.1, max_tokens=4096, pack_id="test_pack"):
    """Construct a duck-typed AgentPack good enough for the builder."""
    return SimpleNamespace(
        pack_id=pack_id,
        config=SimpleNamespace(
            pipelines=pipelines or {},
            model=SimpleNamespace(
                provider=provider,
                temperature=temperature,
                max_tokens=max_tokens,
            ),
        ),
        prompts=prompts or {"retrieval": "You are RetrievalAgent."},
        tools_manifest=MagicMock(),
    )


# ─────────────────────────────────────────────────────────────────────
# Stub provider — offline packs return a FakeMessagesListChatModel
# ─────────────────────────────────────────────────────────────────────


class TestStubProvider:
    """Pack-level `provider: stub` must produce a deterministic fake
    chat model so test packs can run without the Walmart gateway."""

    def test_stub_provider_returns_fake_chat_model(self):
        from agent_factory.langchain_builder import LangChainAgentBuilder

        pack = _make_pack(provider="stub")
        builder = LangChainAgentBuilder(pack)
        model = builder._build_model_client()

        # FakeMessagesListChatModel exposes `responses` configured at init
        assert hasattr(model, "responses")
        # The stub injects a single AIMessage with the literal 'stub'
        # placeholder content — see _build_stub_model.
        assert any(
            getattr(r, "content", "") == "stub response"
            for r in model.responses
        )

    def test_azure_provider_calls_real_factory(self):
        """Non-stub providers MUST call the langchain Azure factory.
        We patch the factory so the test stays offline."""
        from agent_factory import langchain_builder as lb

        pack = _make_pack(provider="azure_openai",
                          temperature=0.42, max_tokens=2048)
        fake_client = object()
        with patch.object(
            sys.modules.setdefault(
                "agent_factory.core.langchain_model_client",
                MagicMock(),
            ),
            "build_langchain_model_client",
            return_value=fake_client,
        ) as factory:
            model = lb.LangChainAgentBuilder(pack)._build_model_client()

        factory.assert_called_once_with(max_tokens=2048, temperature=0.42)
        assert model is fake_client


# ─────────────────────────────────────────────────────────────────────
# Pipeline resolution — None for missing / empty pipelines
# ─────────────────────────────────────────────────────────────────────


class TestPipelineResolution:
    def test_build_pipeline_executor_missing_pipeline_returns_none(self):
        from agent_factory.langchain_builder import LangChainAgentBuilder

        pack = _make_pack(pipelines={})  # no 'retrieval'
        executor = LangChainAgentBuilder(pack).build_pipeline_executor("retrieval")
        assert executor is None

    def test_build_pipeline_executor_empty_pipeline_returns_none(self):
        """A pipeline with no agents is a config error; the builder
        surfaces it as None rather than crashing."""
        from agent_factory.langchain_builder import LangChainAgentBuilder

        pack = _make_pack(pipelines={"retrieval": _pipeline([])})
        executor = LangChainAgentBuilder(pack).build_pipeline_executor("retrieval")
        assert executor is None

    def test_build_single_executor_unknown_role_returns_none(self):
        from agent_factory.langchain_builder import LangChainAgentBuilder

        pack = _make_pack(
            pipelines={"incident": _pipeline([_agent_spec(role="triage")])},
        )
        executor = LangChainAgentBuilder(pack).build_single_executor(
            "incident", "diagnostic",
        )
        assert executor is None


# ─────────────────────────────────────────────────────────────────────
# Executor assembly — round_robin gets chat_history, selector doesn't
# ─────────────────────────────────────────────────────────────────────


@pytest.fixture
def _patched_langchain():
    """Patch out LangChain so `_assemble_executor` can be exercised
    without actually building a real agent graph.

    Yields the fake agents module whose ``create_agent`` is a MagicMock —
    tests inspect its ``call_args`` to verify what the builder passed.
    """
    fake_agents_module = MagicMock()
    # create_agent returns a mock graph that _LegacyExecutorAdapter wraps.
    fake_agents_module.create_agent.return_value = MagicMock()

    fake_tools_module = MagicMock()
    fake_tools_module.StructuredTool.from_function.return_value = object()

    with patch.dict(sys.modules, {
        "langchain.agents": fake_agents_module,
        "langchain_core.tools": fake_tools_module,
    }):
        yield fake_agents_module


def _patch_prompt_helpers():
    """Stub out build_pack_context + render_prompt so the test doesn't
    need a full SOP-IR pack."""
    return (
        patch("agent_factory.langchain_builder.build_pack_context",
              return_value={}),
        patch("agent_factory.langchain_builder.render_prompt",
              side_effect=lambda raw, ctx: raw),
        patch("agent_factory.langchain_builder._wrap_tools_for_langchain",
              return_value=[]),
    )


class TestExecutorAssembly:
    def test_round_robin_pipeline_calls_create_agent_with_system_prompt(
        self, _patched_langchain,
    ):
        """Round-robin pipeline passes the rendered system prompt to
        ``create_agent``.  Chat history is handled by the adapter at
        invocation time, not at prompt-template construction time."""
        from agent_factory.langchain_builder import LangChainAgentBuilder

        agents_module = _patched_langchain
        pack = _make_pack(
            pipelines={
                "retrieval": _pipeline([_agent_spec()], ptype="round_robin"),
            },
        )
        pctx, prdr, ptools = _patch_prompt_helpers()
        with pctx, prdr, ptools, \
             patch("agent_factory.langchain_builder.LangChainAgentBuilder._build_model_client",
                   return_value=object()):
            executor = LangChainAgentBuilder(pack).build_pipeline_executor("retrieval")

        # create_agent must have been called with a system_prompt kwarg
        agents_module.create_agent.assert_called_once()
        call_kwargs = agents_module.create_agent.call_args.kwargs
        assert "system_prompt" in call_kwargs
        assert executor is not None

    def test_selector_pipeline_also_builds_via_create_agent(
        self, _patched_langchain,
    ):
        """Incident-style (selector) pipelines build via the same
        ``create_agent`` path; they differ only in that the caller
        (evidence node) never passes ``chat_history`` in the input."""
        from agent_factory.langchain_builder import LangChainAgentBuilder

        agents_module = _patched_langchain
        pack = _make_pack(
            pipelines={
                "incident": _pipeline(
                    [_agent_spec(name="DiagAgent", role="diagnostic",
                                 prompt_file="diagnostic.j2")],
                    ptype="selector",
                ),
            },
            prompts={"diagnostic": "You are DiagAgent."},
        )
        pctx, prdr, ptools = _patch_prompt_helpers()
        with pctx, prdr, ptools, \
             patch("agent_factory.langchain_builder.LangChainAgentBuilder._build_model_client",
                   return_value=object()):
            executor = LangChainAgentBuilder(pack).build_pipeline_executor("incident")

        agents_module.create_agent.assert_called_once()
        assert executor is not None
        assert executor.agent_name == "DiagAgent"

    def test_executor_carries_agent_name_label(self, _patched_langchain):
        from agent_factory.langchain_builder import LangChainAgentBuilder

        pack = _make_pack(
            pipelines={
                "retrieval": _pipeline(
                    [_agent_spec(name="MyCustomAgent")],
                ),
            },
        )
        pctx, prdr, ptools = _patch_prompt_helpers()
        with pctx, prdr, ptools, \
             patch("agent_factory.langchain_builder.LangChainAgentBuilder._build_model_client",
                   return_value=object()):
            executor = LangChainAgentBuilder(pack).build_pipeline_executor("retrieval")
        assert executor.agent_name == "MyCustomAgent"

# ─────────────────────────────────────────────────────────────────────
# Prompt resolution — errors when missing, otherwise renders
# ─────────────────────────────────────────────────────────────────────


class TestPromptResolution:
    def test_missing_prompt_file_raises_value_error(self):
        from agent_factory.langchain_builder import _resolve_prompt

        pack = _make_pack()
        spec = _agent_spec(prompt_file="")
        with pytest.raises(ValueError, match="prompt_file is empty"):
            _resolve_prompt(pack, spec)

    def test_prompt_not_in_pack_raises_value_error(self):
        from agent_factory.langchain_builder import _resolve_prompt

        pack = _make_pack(prompts={})  # empty prompt map
        spec = _agent_spec(prompt_file="not_there.j2")
        with pytest.raises(ValueError, match="not in pack"):
            _resolve_prompt(pack, spec)
