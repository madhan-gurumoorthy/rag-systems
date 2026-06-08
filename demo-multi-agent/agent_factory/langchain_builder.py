"""LangChain agent builder — pack → agent-graph factory.

Builds a fresh ``langchain.agents.create_agent`` graph from a loaded
SOP Pack.  The agent is resolved from
``pack.config.pipelines.<pipeline_name>``; for single-agent pipelines
the graph drives the iterative tool-call → tool-result loop.

Multi-agent pipelines
---------------------
Pipelines whose ``type`` is ``selector`` (the incident pipeline) are
NOT served by this builder — they run as a LangGraph topology with one
node per agent.  ``_resolve_agent`` expects exactly one agent to match
the lookup key.

Caller contract
---------------
Downstream consumers (evidence node, chat endpoints, evidence_extractor)
invoke the executor with a dict payload and read a dict back:

    result = await executor.ainvoke({"input": ..., "chat_history": ...})
    output = result["output"]
    steps  = result["intermediate_steps"]

``_LegacyExecutorAdapter`` translates between this dict shape and the
LangGraph ``{"messages": [...]}`` interface so the dict contract is
the only thing callers ever see.
"""
from __future__ import annotations

from typing import Any

from agent_factory.common.logging import get_logger
from agent_factory.pack_loader import AgentPack
from agent_factory.pack_models import PipelineAgentSpec
from agent_factory.prompts import build_pack_context, render_prompt
from agent_factory.tools.executor import ToolExecutor

logger = get_logger("langchain_builder")


# ─────────────────────────────────────────────────────────────────────
# Helpers — pack-local, framework-agnostic
# ─────────────────────────────────────────────────────────────────────


def _resolve_prompt(pack: AgentPack, agent_spec: PipelineAgentSpec) -> str:
    """Resolve and render an agent's system prompt from the pack."""
    if not agent_spec.prompt_file:
        raise ValueError(
            f"Prompt not found for agent '{agent_spec.name}' "
            f"(prompt_file is empty) in pack '{pack.pack_id}'."
        )

    key = agent_spec.prompt_file
    for ext in (".j2", ".txt", ".md", ".prompt"):
        key = key.replace(ext, "")

    if key in pack.prompts:
        raw = pack.prompts[key]
        context = build_pack_context(pack)
        return render_prompt(raw, context)

    raise ValueError(
        f"Prompt '{agent_spec.prompt_file}' not in pack '{pack.pack_id}'. "
        f"Available: {list(pack.prompts.keys())}"
    )


def _wrap_tools_for_langchain(
    tool_executor: ToolExecutor,
    tool_ids: list[str],
) -> list[Any]:
    """Wrap ToolExecutor callables as LangChain `StructuredTool` instances.

    `ToolExecutor` already produces callables with `__signature__`,
    `__annotations__`, `__name__` and `__doc__` populated for tool
    introspection.  LangChain's `StructuredTool.from_function` walks
    the same metadata to build a Pydantic args schema, so the
    callables drop in unchanged — no per-tool adapter required.
    """
    # Lazy import — tests mock `langchain_core.tools` out at sys.modules
    # so the module-level imports stay light.
    from langchain_core.tools import StructuredTool

    callables = tool_executor.get_tools_for_agent(tool_ids)
    wrapped: list[Any] = []
    for func in callables:
        try:
            tool = StructuredTool.from_function(
                coroutine=func,
                name=getattr(func, "__name__", "tool"),
                description=getattr(func, "__doc__", None) or "Tool",
            )
            wrapped.append(tool)
        except Exception as e:  # pragma: no cover — surfaced in logs
            logger.warning(
                "Failed to wrap tool '%s' for LangChain: %s",
                getattr(func, "__name__", "?"), e,
            )
    return wrapped


def _build_stub_model() -> Any:
    """Return a deterministic stub chat model for offline / test packs.

    Used when ``pack.config.model.provider == "stub"``.  The stub returns
    a single fixed ``AIMessage`` with no tool calls so the executor exits
    the tool loop immediately.
    """
    from langchain_core.language_models.fake_chat_models import (
        FakeMessagesListChatModel,
    )
    from langchain_core.messages import AIMessage

    return FakeMessagesListChatModel(responses=[AIMessage(content="stub response")])


# ─────────────────────────────────────────────────────────────────────
# Executor adapter — create_agent graph → dict-shaped interface
# ─────────────────────────────────────────────────────────────────────


class _LegacyExecutorAdapter:
    """Wraps a ``create_agent`` graph with a dict-shaped ainvoke contract.

    Callers invoke ``ainvoke({"input": ..., "chat_history": ...})`` and
    read ``result["output"]`` + ``result["intermediate_steps"]``.
    Internally, the adapter translates to/from the LangGraph
    ``{"messages": [...]}`` interface and reconstructs
    ``(AgentAction, observation)`` tuples from tool-call / tool-result
    message pairs.
    """

    def __init__(self, graph: Any, *, agent_name: str = "agent") -> None:
        self._graph = graph
        self.agent_name = agent_name

    # ── helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _to_messages(
        inputs: dict[str, Any],
    ) -> dict[str, list[Any]]:
        """Convert ``{"input": str, "chat_history": list}`` to ``{"messages": list}``."""
        messages: list[Any] = []
        for hist_msg in inputs.get("chat_history") or []:
            messages.append(hist_msg)
        messages.append(("human", inputs.get("input", "")))
        return {"messages": messages}

    @staticmethod
    def _extract_steps_and_output(
        result_messages: list[Any],
    ) -> tuple[list[Any], str]:
        """Walk the message list and extract intermediate_steps + final output.

        Tool-call messages (``AIMessage`` with ``tool_calls``) are paired
        with subsequent ``ToolMessage`` entries to reconstruct the
        ``(AgentAction, observation)`` tuples that ``evidence_extractor``
        expects.
        """
        from langchain_core.agents import AgentAction
        from langchain_core.messages import AIMessage, ToolMessage

        steps: list[tuple[Any, str]] = []
        output = ""

        # Index ToolMessages by tool_call_id for O(1) lookup.
        tool_results: dict[str, str] = {}
        for msg in result_messages:
            if isinstance(msg, ToolMessage):
                tid = getattr(msg, "tool_call_id", None)
                if tid:
                    tool_results[tid] = msg.content or ""

        for msg in result_messages:
            if not isinstance(msg, AIMessage):
                continue
            tool_calls = getattr(msg, "tool_calls", None) or []
            if tool_calls:
                for tc in tool_calls:
                    action = AgentAction(
                        tool=tc.get("name", tc.get("tool", "unknown")),
                        tool_input=tc.get("args", {}),
                        log=f"Invoking {tc.get('name', '?')}",
                    )
                    observation = tool_results.get(tc.get("id", ""), "")
                    steps.append((action, observation))
            elif msg.content:
                # Last AIMessage without tool_calls is the final answer.
                output = msg.content

        return steps, output

    # ── public interface ─────────────────────────────────────────────

    async def ainvoke(
        self,
        inputs: dict[str, Any],
        config: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        graph_input = self._to_messages(inputs)
        result = await self._graph.ainvoke(graph_input, config=config, **kwargs)
        steps, output = self._extract_steps_and_output(
            result.get("messages", []),
        )
        return {
            "output": output,
            "intermediate_steps": steps,
        }

    async def astream_events(
        self,
        inputs: dict[str, Any],
        config: dict[str, Any] | None = None,
        **kwargs: Any,
    ):
        """Delegate streaming to the underlying graph.

        The terminal event name is ``"LangGraph"`` — the streaming chat
        endpoint matches on that.
        """
        graph_input = self._to_messages(inputs)
        async for event in self._graph.astream_events(
            graph_input, config=config, **kwargs,
        ):
            yield event


# ─────────────────────────────────────────────────────────────────────
# Builder
# ─────────────────────────────────────────────────────────────────────


class LangChainAgentBuilder:
    """Build agent graph instances from a loaded SOP Pack.

    Stateless per call — each build method returns a fresh
    ``_LegacyExecutorAdapter``-wrapped graph suitable for a single
    request.  Fresh model client per call preserves SOA-signature
    freshness (signatures rotate frequently on Walmart's LLM gateway).
    """

    def __init__(self, pack: AgentPack) -> None:
        self._pack = pack
        self._tool_executor = ToolExecutor(pack.tools_manifest)

    @property
    def pack(self) -> AgentPack:
        return self._pack

    @property
    def tool_executor(self) -> ToolExecutor:
        return self._tool_executor

    # ── Agent resolution ─────────────────────────────────────────────

    def _find_agent_spec(
        self,
        pipeline_name: str,
        role_keyword: str,
    ) -> PipelineAgentSpec | None:
        """Locate an agent spec inside a named pipeline by role keyword."""
        pipeline = self._pack.config.pipelines.get(pipeline_name)
        if not pipeline:
            return None
        keyword_lower = role_keyword.lower()
        for agent_spec in pipeline.agents:
            if (
                keyword_lower in agent_spec.name.lower()
                or keyword_lower in agent_spec.role.lower()
            ):
                return agent_spec
        return None

    def _first_agent_spec(
        self,
        pipeline_name: str,
    ) -> PipelineAgentSpec | None:
        """Return the first agent in a pipeline — used for single-agent pipelines."""
        pipeline = self._pack.config.pipelines.get(pipeline_name)
        if not pipeline or not pipeline.agents:
            return None
        return pipeline.agents[0]

    # ── Model client ─────────────────────────────────────────────────

    def _build_model_client(self) -> Any:
        """Build a fresh LangChain chat model from pack config.

        Provider switches:
          • ``stub`` — `FakeMessagesListChatModel` (offline / test packs)
          • ``azure_openai`` (default) — `AzureChatOpenAI` with SOA-signed headers
          • ``openai`` — currently NOT supported; treated as azure_openai
            because no production pack uses raw OpenAI today.  Add a real
            branch the first time a pack ships with ``provider: openai``.

        Pack-level ``temperature`` and ``max_tokens`` overrides flow
        through to the model.  Returning ``None`` is never valid — every
        path raises or builds a client.
        """
        mc = self._pack.config.model

        if mc.provider == "stub":
            return _build_stub_model()

        # Default: azure_openai — fresh SOA-signed client per request
        from agent_factory.core.langchain_model_client import (
            build_langchain_model_client,
        )

        return build_langchain_model_client(
            max_tokens=mc.max_tokens or 4096,
            temperature=mc.temperature if mc.temperature is not None else 0.1,
        )

    # ── Executor builders ────────────────────────────────────────────

    def _assemble_executor(
        self,
        agent_spec: PipelineAgentSpec,
    ) -> _LegacyExecutorAdapter:
        """Assemble an agent graph from a resolved agent spec.

        Uses ``langchain.agents.create_agent`` to build a LangGraph
        ``CompiledStateGraph``, then wraps it in
        ``_LegacyExecutorAdapter`` so callers retain the
        ``ainvoke({"input":..}) → {"output":..,"intermediate_steps":..}``
        dict contract.  Chat history (when supplied by the caller) is
        prepended to the agent's message list inside the adapter.

        When the LangGraph checkpointer is available its saver is injected
        at compile time so the graph can persist state across calls
        (keyed by ``thread_id`` in the caller's config); otherwise the
        graph runs stateless.
        """
        from langchain.agents import create_agent
        from agent_factory.graph.checkpointer import langgraph_checkpointer

        system_prompt = _resolve_prompt(self._pack, agent_spec)
        tools = _wrap_tools_for_langchain(self._tool_executor, agent_spec.tools)
        model = self._build_model_client()

        graph = create_agent(
            model,
            tools=tools,
            system_prompt=system_prompt,
            checkpointer=langgraph_checkpointer.saver,
        )

        logger.debug(
            "Built agent graph for '%s' with %d tools",
            agent_spec.name, len(tools),
        )
        return _LegacyExecutorAdapter(graph, agent_name=agent_spec.name)

    def build_single_executor(
        self,
        pipeline_name: str,
        role_keyword: str,
    ) -> _LegacyExecutorAdapter | None:
        """Build an agent resolved by role keyword.

        Used by the LangGraph evidence node to pull the diagnostic
        agent out of the incident pipeline regardless of position.
        Returns ``None`` if no matching agent is found.
        """
        agent_spec = self._find_agent_spec(pipeline_name, role_keyword)
        if agent_spec is None:
            return None
        return self._assemble_executor(agent_spec)

    def build_pipeline_executor(
        self,
        pipeline_name: str,
    ) -> _LegacyExecutorAdapter | None:
        """Build an agent for the first agent in a pipeline.

        Used by the chat endpoints to drive the retrieval pipeline (one
        ``RetrievalAgent`` with tool access).

        Returns ``None`` if the pipeline doesn't exist or has no agents.
        Pipelines with multiple agents are still served — only the first
        agent is exposed; the remaining agents in a selector pipeline
        belong to the LangGraph topology, not this builder.
        """
        pipeline = self._pack.config.pipelines.get(pipeline_name)
        if pipeline is None:
            return None
        agent_spec = self._first_agent_spec(pipeline_name)
        if agent_spec is None:
            return None
        return self._assemble_executor(agent_spec)


__all__ = ["LangChainAgentBuilder"]
