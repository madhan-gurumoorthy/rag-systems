"""
OL Triage Agent workflow — fast-path bypass + ReAct graph.

Fast-path:
  Plain "Check offer X store Y" queries skip the LLM tool-calling loop.
  We extract offer_id + store_id with regex, run the deterministic
  OLTriageEngine, and return the rendered report with 0 LLM calls (~4 s).

Slow-path:
  When regex cannot extract the IDs, a simple router→tools LangGraph
  loop asks the LLM to extract them and call `run_ol_triage_tool`, then
  the rendered_report field is extracted from the tool result.

Graph state is persisted via the shared LangGraph Postgres checkpointer
when available; falls back to in-process MemorySaver otherwise.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Optional, Tuple

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

from agent_factory.common.logging import get_logger
from agent_factory.observability import clear_request_context, set_request_context
from packs.offer_intelligence.services.report_renderer import render_full_report, render_rule_block
from packs.offer_intelligence.services.rule_registry import get_registry
from packs.offer_intelligence.triage_engine import get_engine

logger = get_logger("ol_triage.workflow")


# ── Fast-path query parser ────────────────────────────────────────────────────

# 32-char hex/alphanumeric offer ID (typical real format)
_OFFER_ID_RE = re.compile(r"\b([A-F0-9]{32})\b", re.IGNORECASE)
# Numeric store ID following "store" / "store_id" / "store id" / "@"
_STORE_RE = re.compile(
    r"(?:store(?:[ _-]?id)?[\s:=]+|@\s*|store\s+)(\d{1,6})\b",
    re.IGNORECASE,
)
# Bare numeric fallback after the offer id
_BARE_NUM_RE = re.compile(r"\b(\d{1,6})\b")


def _try_parse_offer_store(query: str) -> Optional[Tuple[str, str]]:
    """Extract (offer_id, store_id) from simple triage queries.

    Returns None if the query isn't a clear "check offer X store Y" pattern.
    Triggers the fast-path only when both an offer ID and a store number
    are unambiguously present.
    """
    offer_match = _OFFER_ID_RE.search(query)
    if not offer_match:
        return None
    offer_id = offer_match.group(1).upper()

    store_match = _STORE_RE.search(query)
    if store_match:
        return offer_id, store_match.group(1)

    # Fallback: take the first bare number AFTER the offer id (avoids picking
    # numbers that are part of the offer ID itself).
    tail = query[offer_match.end():]
    bare = _BARE_NUM_RE.search(tail)
    if bare:
        return offer_id, bare.group(1)

    return None


# ── Fast-path execution ───────────────────────────────────────────────────────

async def _fast_path_triage(query: str, offer_id: str, store_id: str) -> str:
    """Run the deterministic engine and render the report with 0 LLM calls."""
    logger.info(f"ol_triage.fast_path offer={offer_id} store={store_id}")
    engine = get_engine()
    result = await engine.triage_offer(offer_id, store_id)

    if result.listing_status == "LISTED":
        return (
            f"OL Triage Report\n"
            f"===================================\n"
            f"Offer ID   : {result.offer_id}\n"
            f"Store ID   : {result.store_id}\n"
            f"Mart ID    : {result.mart_id}\n"
            f"Listing Status : \u2705 LISTED\n"
            f"===================================\n"
            f"This offer is correctly listed at store {result.store_id}."
        )

    if result.listing_status == "UNKNOWN" and result.errors:
        error_detail = result.errors[0] if result.errors else "OL API returned no data"
        return (
            f"OL Triage Report\n"
            f"===================================\n"
            f"Offer ID   : {result.offer_id}\n"
            f"Store ID   : {result.store_id}\n"
            f"Mart ID    : {result.mart_id}\n"
            f"Listing Status : \u2753 NOT FOUND\n"
            f"===================================\n"
            f"No listing record found for this offer at store {result.store_id}.\n"
            f"The offer may not exist at this store or mart.\n"
            f"\nDetail: {error_detail}"
        )

    registry = get_registry()
    verdict_icons = {
        "VALID": "\u2705 VALID DELIST",
        "INVALID": "\u274c INVALID DELIST",
        "PARTIAL": "\u26a0\ufe0f PARTIAL DELIST",
        "CANNOT_EVALUATE": "\U0001f6ab CANNOT EVALUATE",
    }

    rule_blocks: list[str] = []
    summary_lines: list[str] = []

    for rv in result.rule_verdicts:
        rule_def = registry.get_rule(rv.rule_id)
        if rule_def is None:
            block = f"Rule {rv.rule_id} \u2014 definition not available in current IMP snapshot"
            verdict = "NOT_FOUND"
        else:
            eval_result = {
                "per_condition_results": rv.per_condition_results,
                "verdict": rv.verdict,
                "expression_result": rv.expression_result,
                "evaluated_count": rv.evaluated_count,
                "skipped_count": rv.skipped_count,
                "total_conditions": rv.total_conditions,
                "cannot_evaluate_fields": rv.cannot_evaluate_fields,
            }
            block = render_rule_block(rule_def, eval_result)
            verdict = rv.verdict

        rule_blocks.append(block)
        icon = verdict_icons.get(verdict, f"? {verdict}")
        rname = rv.rule_name if rv.rule_name else rv.rule_id
        summary_lines.append(f"- Rule {rv.rule_id:<4} ({rname}) : {icon}")

    return render_full_report(
        offer_id=result.offer_id,
        store_id=result.store_id,
        mart_id=result.mart_id,
        listing_status=result.listing_status,
        rule_blocks=rule_blocks,
        summary_lines=summary_lines,
    )


# ── System prompt ─────────────────────────────────────────────────────────────

_OL_SYSTEM_PROMPT = """\
You are the OL Triage Agent — an expert at diagnosing why Walmart offers are \
delisted at specific stores.

When a user asks why an offer is delisted or asks you to check an offer at a store:
1. Extract the offer_id (32-character alphanumeric hex ID) and store_id (numeric) \
from their message.
2. Call the `run_ol_triage_tool` with those parameters.
3. The tool returns JSON. Extract the `rendered_report` field and return it verbatim \
as your entire response. Do NOT summarise, reformat, or shorten it.

For questions that don't involve a specific offer or store (e.g., "how does rule 192 \
work?", "what does VALID DELIST mean?"), answer directly using your domain knowledge \
about OL policy rules and verdict types:
  - VALID DELIST: the engine's delist reason is confirmed by live data
  - INVALID DELIST: live data contradicts the delist reason (potential data issue)
  - PARTIAL: some conditions could not be evaluated due to unsupported fields
  - CANNOT EVALUATE: all conditions require unsupported fields

If the user has not provided an offer_id or store_id, ask for them before calling \
the tool. Do NOT fabricate offer IDs or store IDs.\
"""


# ── LangChain tool ────────────────────────────────────────────────────────────

def _make_triage_tool():
    from langchain_core.tools import tool

    from packs.offer_intelligence.ol_tools import run_ol_triage

    @tool
    async def run_ol_triage_tool(
        offer_id: str,
        store_id: str,
        mart_id: str = "0",
    ) -> str:
        """Run deterministic OL triage for a single offer at a store.

        Returns a JSON payload containing listing_status, overall_verdict,
        matched_rule_ids, reason_codes, outcome, and a pre-rendered plain-text
        report in the 'rendered_report' field.

        Args:
            offer_id: The 32-character offer ID (hex alphanumeric).
            store_id: The numeric store ID (e.g. '295', '6295').
            mart_id:  Mart ID — defaults to '0' (DOTCOM).
        """
        return await run_ol_triage(offer_id, store_id, mart_id)

    return run_ol_triage_tool


_OL_TOOLS: list | None = None


def _get_tools() -> list:
    global _OL_TOOLS
    if _OL_TOOLS is None:
        _OL_TOOLS = [_make_triage_tool()]
    return _OL_TOOLS


# ── Graph state ───────────────────────────────────────────────────────────────

class OLWorkflowState(MessagesState):
    """Minimal state for the OL triage ReAct loop.

    Extends MessagesState (which carries the messages list with the
    add_messages reducer) with a session_id for thread keying.
    """
    session_id: str = ""


# ── Graph nodes ───────────────────────────────────────────────────────────────

async def _router_node(state: OLWorkflowState) -> dict:
    """LLM router — decides next action (tool call or final answer).

    Builds a fresh model client each call; the Walmart gateway issues
    short-TTL SOA signatures so clients must not be cached across requests.
    """
    from agent_factory.runtime.model_client import build_langchain_model_client

    messages = list(state["messages"])
    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=_OL_SYSTEM_PROMPT)] + messages

    llm = build_langchain_model_client(temperature=0.0).bind_tools(_get_tools())
    response = await llm.ainvoke(messages)
    return {"messages": [response]}


def _should_continue(state: OLWorkflowState) -> str:
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return END


# ── Graph build ────────────────────────────────────────────────────────────────

_graph = None


def _build_graph():
    tools = _get_tools()
    from agent_factory.graph.checkpointer import langgraph_checkpointer
    checkpointer = langgraph_checkpointer.saver or MemorySaver()

    graph = StateGraph(OLWorkflowState)
    graph.add_node("router", _router_node)
    graph.add_node("tools", ToolNode(tools))
    graph.set_entry_point("router")
    graph.add_conditional_edges(
        "router",
        _should_continue,
        {"tools": "tools", END: END},
    )
    graph.add_edge("tools", "router")

    compiled = graph.compile(checkpointer=checkpointer)
    logger.info("ol_triage.workflow_graph_built tools=1")
    return compiled


def get_graph():
    global _graph
    if _graph is None:
        _graph = _build_graph()
    return _graph


# ── Public entry points ────────────────────────────────────────────────────────

async def run_ol_agent(query: str, session_id: str | None = None) -> str:
    """Run the OL Triage Agent and return the final report as a string.

    Fast-path: queries containing a 32-char offer ID + store number skip
    the LLM loop entirely — 0 LLM calls.

    Slow-path: all other queries go through the LangGraph router→tools loop.

    Args:
        query:      The user's question (e.g. "Why is offer X delisted at store 295?").
        session_id: Optional session ID for in-process conversation continuity.
    """
    if not session_id:
        session_id = str(uuid.uuid4())

    # Seed observability contextvars so every outbound HTTP call inside
    # triage emits an ``api_call`` event row with the correct
    # session/agent/tenant attribution.
    prior_ctx = set_request_context(
        session_id=session_id,
        agent_id="offer_intelligence",
        tenant_id="offer_intelligence",
    )
    try:
        parsed = _try_parse_offer_store(query)
        if parsed:
            offer_id, store_id = parsed
            try:
                return await _fast_path_triage(query, offer_id, store_id)
            except Exception as exc:
                import traceback
                logger.error(
                    f"ol_triage.fast_path_failed offer={offer_id} store={store_id} "
                    f"error={exc}\n{traceback.format_exc()}"
                )
                # Fall through to slow graph on any engine/render error.

        graph = get_graph()
        config = {"configurable": {"thread_id": session_id}}
        input_state: dict[str, Any] = {
            "messages": [HumanMessage(content=query)],
            "session_id": session_id,
        }

        result = await graph.ainvoke(input_state, config=config)
        messages = result["messages"]

        # Prefer the rendered_report embedded in the run_ol_triage_tool result —
        # it's the authoritative plain-text report from the deterministic engine.
        for msg in reversed(messages):
            if (
                getattr(msg, "type", "") == "tool"
                and getattr(msg, "name", "") == "run_ol_triage_tool"
            ):
                try:
                    data = json.loads(msg.content)
                    if data.get("rendered_report"):
                        return data["rendered_report"]
                except Exception:
                    return str(msg.content)

        # Fallback: last non-empty message content (LLM conversational answer).
        for msg in reversed(messages):
            if getattr(msg, "content", ""):
                return str(msg.content)

        return messages[-1].content if messages else ""
    finally:
        clear_request_context(prior_ctx)


async def stream_ol_agent(
    query: str,
    session_id: str | None = None,
) -> AsyncGenerator[dict, None]:
    """Stream OL Triage Agent execution events.

    Yields dicts with keys:
      type    — start | tool_start | tool_result | chunk | done | error
      content — human-readable text for that event
      tool    — tool name (present on tool_start and tool_result events)

    Args:
        query:      The user's question.
        session_id: Optional session ID for in-process conversation continuity.
    """
    if not session_id:
        session_id = str(uuid.uuid4())

    # Seed observability contextvars so every outbound HTTP call inside
    # triage emits an ``api_call`` event row with the correct
    # session/agent/tenant attribution.
    prior_ctx = set_request_context(
        session_id=session_id,
        agent_id="offer_intelligence",
        tenant_id="offer_intelligence",
    )

    try:
        yield {"type": "start", "content": "OL Triage Agent starting..."}

        # Fast-path: deterministic engine, 0 LLM round-trips.
        parsed = _try_parse_offer_store(query)
        if parsed:
            offer_id, store_id = parsed
            try:
                report = await _fast_path_triage(query, offer_id, store_id)
                yield {"type": "chunk", "content": report}
                yield {"type": "done", "content": "Analysis complete"}
                return
            except Exception as exc:
                import traceback
                logger.error(
                    f"ol_triage.stream_fast_path_failed offer={offer_id} store={store_id} "
                    f"error={exc}\n{traceback.format_exc()}"
                )
                # Fall through to slow graph.

        graph = get_graph()
        config = {"configurable": {"thread_id": session_id}}
        input_state: dict[str, Any] = {
            "messages": [HumanMessage(content=query)],
            "session_id": session_id,
        }

        report_emitted = False
        async for event in graph.astream(input_state, config=config, stream_mode="updates"):
            for _node_name, node_output in event.items():
                for msg in node_output.get("messages", []):
                    msg_type = getattr(msg, "type", "")

                    if msg_type == "ai":
                        tool_calls = getattr(msg, "tool_calls", [])
                        if tool_calls:
                            for tc in tool_calls:
                                yield {
                                    "type": "tool_start",
                                    "content": f"Calling {tc['name']}...",
                                    "tool": tc["name"],
                                }
                        elif msg.content and not report_emitted:
                            yield {"type": "chunk", "content": msg.content}

                    elif msg_type == "tool":
                        tool_name = getattr(msg, "name", "")
                        tool_content = str(msg.content)

                        if tool_name == "run_ol_triage_tool":
                            # Extract rendered_report and emit as the final chunk.
                            try:
                                data = json.loads(tool_content)
                                report_text = data.get("rendered_report") or tool_content
                            except Exception:
                                report_text = tool_content
                            yield {"type": "chunk", "content": report_text}
                            report_emitted = True
                        else:
                            yield {
                                "type": "tool_result",
                                "content": tool_content[:200],
                                "tool": tool_name,
                            }

        yield {"type": "done", "content": "Analysis complete"}

    except Exception as exc:
        logger.error(f"ol_triage.stream_error error={exc}")
        yield {"type": "error", "content": str(exc)}
    finally:
        clear_request_context(prior_ctx)
