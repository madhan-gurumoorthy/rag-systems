"""Run evidence — per-run, business-level audit trail.

Extracts a structured record of what happened during a pipeline run
from the dict result returned by ``_LegacyExecutorAdapter.ainvoke``.
The evidence is injected into the ``team_state`` dict under the
reserved ``_evidence`` key so that callers who don't need it can
ignore it without any API change.

What gets captured
------------------
* **agent_message** — the agent's final text output with a content preview.
* **tool_call** — every tool invocation (name + arguments + call_id).
* **tool_result** — the result returned for each tool call.
* **decision** — structured decision payload when the final agent text
  parses as a JSON object containing ``runbook_card``.

Input contract
--------------
``extract_evidence`` consumes the adapter's dict result directly:

* ``intermediate_steps`` — the list of ``(AgentAction, observation)``
  tuples reconstructed by the adapter from tool-call / tool-result
  message pairs.  Each ``AgentAction`` exposes ``.tool`` (str),
  ``.tool_input`` (dict or str), and an optional ``.message_log``
  carrying the OpenAI ``tool_call_id``.
* ``final_output`` — the agent's final text (``result['output']``).
  Becomes an ``agent_message`` entry — or a ``decision`` entry when
  it parses as JSON with a ``runbook_card``.

Design constraints
------------------
* **Non-invasive** — extracted post-run; no framework internals or
  monkey-patching required.
* **Single-framework native** — consumes LangChain's
  ``(AgentAction, observation)`` tuples directly.
* **Safe content handling** — long strings are truncated; credentials
  never appear in messages (they are resolved inside
  :mod:`agent_factory.tools.executor` and are not visible to the LLM
  layer).
* **Additive output shape** — ``_evidence`` is an additive key on the
  returned ``team_state`` dict; downstream callers (CLI replay tools,
  diagnostics dashboards, golden-trace utilities) read a stable
  entry-dict shape.

Usage
-----
Consumed by :mod:`agent_factory.langchain_chat` (chat path) and the
LangGraph evidence node (incident path)::

    from agent_factory.evidence_extractor import extract_evidence

    evidence = extract_evidence(
        intermediate_steps=result.get("intermediate_steps", []),
        pack_id=pack.pack_id,
        final_output=result.get("output", ""),
        agent_source="DiagnosticAgent",
    )
    if evidence:
        team_state["_evidence"] = evidence
"""
from __future__ import annotations

import json
from typing import Any, Sequence

from agent_factory.common.logging import get_logger

logger = get_logger("evidence")

# Maximum characters stored per content/result preview field.
# Keeps team_state serialisation size bounded for long incidents.
# Must be large enough for closure-template field extraction in
# runtime.py to parse the full JSON payload (nested objects, lists,
# product names, UOM codes etc. easily exceed 500 chars).
_MAX_PREVIEW_CHARS: int = 2000

# Generic outcome codes that indicate a tool result is an error / not a success.
# Matched case-insensitively against the ``outcome`` field of tool results.
#
# Pack-domain outcomes (e.g. ``gtin_not_found``, ``email_failed``) are not
# enumerated here — they are still classified as errors via the explicit
# ``error`` key check and HTTP-status check below.  Packs that need a
# narrower or wider error vocabulary should surface it through the tool
# result's ``error`` / HTTP status, not by hard-coding their domain values
# into the framework.
#
# NOTE: "data_not_found" is intentionally EXCLUDED — it means "no data
# available" (e.g. an optional secondary data source returned no rows),
# which is an expected condition rather than a pipeline failure.  Treating
# it as an error caused pipeline health to report "partial" even when the
# downstream validation completed successfully.
_ERROR_OUTCOMES: frozenset[str] = frozenset({
    "not_found", "auth_error", "bad_request", "rate_limited",
    "upstream_error", "upstream_unavailable", "method_not_allowed",
    "api_error", "parse_failure", "update_failed",
})

# HTTP status codes that signal failure.
_ERROR_HTTP_CODES: frozenset[str] = frozenset({
    "400", "401", "403", "404", "405", "429", "500", "502", "503", "504",
})


def _derive_tool_status(result_text: str) -> tuple[str, str | None]:
    """Derive a normalised status and outcome from a tool result string.

    Returns:
        (status, outcome) — status is one of "success", "error", "not_found";
        outcome is the raw outcome string (e.g. "AUTH_ERROR") or None.
    """
    if not result_text:
        return "success", None

    try:
        data = json.loads(result_text)
    except (json.JSONDecodeError, TypeError):
        return "success", None

    if not isinstance(data, dict):
        return "success", None

    outcome = str(data.get("outcome", "")).strip()
    error = str(data.get("error", "")).strip()

    # Check explicit outcome code
    if outcome and outcome.lower() in _ERROR_OUTCOMES:
        return "error", outcome

    # Check for HTTP error codes in the error field
    if error:
        for code in _ERROR_HTTP_CODES:
            if code in error:
                return "error", outcome or error

    # Check for explicit error key without outcome
    if data.get("error") and not outcome:
        return "error", str(data["error"])[:80]

    return "success", outcome or None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_evidence(
    intermediate_steps: Sequence[Any] | None,
    *,
    pack_id: str,
    final_output: str = "",
    agent_source: str = "agent",
) -> list[dict[str, Any]]:
    """Extract a business-level audit trail from a LangChain executor run.

    Walks the ``intermediate_steps`` list — each entry is a
    ``(AgentAction, observation)`` tuple — and appends ``tool_call`` +
    ``tool_result`` entries for every executed tool, preserving order.
    The agent's final text is appended as an ``agent_message`` entry,
    upgraded to ``decision`` if the content parses as a JSON object
    containing ``runbook_card``.

    Args:
        intermediate_steps: list of ``(AgentAction, observation)`` tuples
            as exposed by ``_LegacyExecutorAdapter.ainvoke``'s
            ``intermediate_steps`` field.  Each ``AgentAction`` is
            duck-typed by attribute inspection (``.tool`` / ``.tool_input``
            / optional ``.message_log``) so the function is robust to
            minor langchain-openai version drift across releases.
        pack_id: ID of the executing pack, recorded on every entry for
            traceability when multiple packs share a state store.
        final_output: the agent's final text (``result['output']``).
            Becomes an ``agent_message`` entry — or a ``decision`` entry
            when the content parses as JSON with a ``runbook_card``.
            Pass an empty string to skip the trailing entry.
        agent_source: name to record on the resulting entries.  Defaults
            to ``"agent"``; callers typically pass the executor's
            ``agent_name`` (e.g. ``"DiagnosticAgent"``).

    Returns:
        Ordered list of evidence entry dicts.  Returns ``[]`` when both
        ``intermediate_steps`` is empty/None and ``final_output`` is empty.
    """
    entries: list[dict[str, Any]] = []

    for idx, step in enumerate(intermediate_steps or []):
        try:
            action, observation = step
        except (TypeError, ValueError):
            logger.warning("Malformed intermediate_steps entry skipped: %r", step)
            continue

        tool_name = getattr(action, "tool", "") or "unknown"
        raw_input = getattr(action, "tool_input", {})
        # LangChain may hand `tool_input` as a dict (typical) or a JSON
        # string (single-input tools that decode their args themselves).
        if isinstance(raw_input, dict):
            args: dict[str, Any] = raw_input
        elif isinstance(raw_input, str):
            args = _safe_parse_json(raw_input)
        elif raw_input is None:
            args = {}
        else:
            args = {"_value": raw_input}

        # Resolve a stable call_id — prefer the OpenAI tool_call_id from
        # action.message_log when langchain-openai exposes it, otherwise
        # fall back to a positional `call_N` so the call_id ↔ result
        # pairing stays consistent in downstream consumers.
        call_id = _extract_call_id(action, tool_name) or f"call_{idx}"

        entries.append({
            "type": "tool_call",
            "agent": agent_source,
            "pack_id": pack_id,
            "tool": tool_name,
            "call_id": call_id,
            "args": args,
        })

        result_text = str(observation) if observation is not None else ""
        status, outcome = _derive_tool_status(result_text)
        entries.append({
            "type": "tool_result",
            "pack_id": pack_id,
            "call_id": call_id,
            "tool": tool_name,
            "result_preview": _truncate(result_text),
            "status": status,
            "outcome": outcome,
        })

    # Final agent text — classified as agent_message or decision.
    if final_output:
        entries.append(_make_text_entry(agent_source, str(final_output), pack_id))

    return entries


def summarise_pipeline_health(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    """Derive pipeline health from evidence entries.

    Returns a dict with:
        - tool_calls: total number of tool invocations
        - tool_successes: number of tool results with status="success"
        - tool_failures: number of tool results with status="error"/"not_found"
        - failed_tools: list of (tool_name, outcome) for each failed tool
        - has_failures: bool
        - pipeline_status: "success" | "partial" | "failed"
    """
    tool_calls = 0
    tool_successes = 0
    tool_failures = 0
    failed_tools: list[dict[str, str]] = []

    for entry in evidence:
        if entry.get("type") == "tool_call":
            tool_calls += 1
        elif entry.get("type") == "tool_result":
            status = entry.get("status", "success")
            if status in ("error", "not_found"):
                tool_failures += 1
                failed_tools.append({
                    "tool": entry.get("tool", "unknown"),
                    "outcome": entry.get("outcome", "unknown"),
                })
            else:
                tool_successes += 1

    has_failures = tool_failures > 0
    if tool_calls == 0:
        pipeline_status = "no_tools"
    elif tool_failures == 0:
        pipeline_status = "success"
    elif tool_successes > 0:
        pipeline_status = "partial"
    else:
        pipeline_status = "failed"

    return {
        "tool_calls": tool_calls,
        "tool_successes": tool_successes,
        "tool_failures": tool_failures,
        "failed_tools": failed_tools,
        "has_failures": has_failures,
        "pipeline_status": pipeline_status,
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _extract_call_id(action: Any, tool_name: str) -> str:
    """Return the OpenAI tool_call_id from ``action.message_log`` if present.

    langchain-openai surfaces the underlying ``tool_calls`` on the
    ``AIMessage`` envelopes stored in ``AgentAction.message_log`` —
    each tool_call dict carries ``id`` (e.g. ``"call_AbCdEf123"``) and
    ``name``.  We prefer this id when the name matches the action's
    tool so that downstream consumers can correlate the evidence back
    to the raw OpenAI trace.

    Returns an empty string when no matching id is found — the caller
    substitutes a positional ``call_N`` fallback.
    """
    for msg in getattr(action, "message_log", None) or []:
        # 1.x AIMessage exposes .tool_calls directly as a list of dicts.
        tool_calls = getattr(msg, "tool_calls", None) or []
        for tc in tool_calls:
            tc_id = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
            tc_name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
            if tc_id and tc_name == tool_name:
                return str(tc_id)
        # 0.3.x fallback path — tool_calls live in additional_kwargs.
        add_kw = getattr(msg, "additional_kwargs", None)
        if isinstance(add_kw, dict):
            for tc in add_kw.get("tool_calls") or []:
                tc_id = (
                    tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
                )
                fn_block = (
                    tc.get("function") if isinstance(tc, dict)
                    else getattr(tc, "function", None)
                )
                tc_name = None
                if isinstance(fn_block, dict):
                    tc_name = fn_block.get("name")
                elif fn_block is not None:
                    tc_name = getattr(fn_block, "name", None)
                if tc_id and tc_name == tool_name:
                    return str(tc_id)
    return ""


def _make_text_entry(
    source: str, content: str, pack_id: str,
) -> dict[str, Any]:
    """Build a text or decision entry from an agent's string message."""
    entry: dict[str, Any] = {
        "type": "agent_message",
        "agent": source,
        "pack_id": pack_id,
        "content_preview": _truncate(content),
    }

    decision = _try_parse_decision(content)
    if decision:
        entry["type"] = "decision"
        entry["decision"] = decision

    return entry


def _try_parse_decision(content: str) -> dict[str, Any] | None:
    """Attempt to parse a structured decision payload from message content.

    The DecisionAgent emits a JSON block containing ``runbook_card``.
    Returns a sanitised decision dict on success, ``None`` otherwise.
    """
    if "runbook_card" not in content:
        return None

    try:
        data = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return None

    if not isinstance(data, dict) or "runbook_card" not in data:
        return None

    return {
        "runbook_card": data.get("runbook_card"),
        "card_name": data.get("card_name"),
        "confidence": data.get("confidence"),
        "reasoning": _truncate(str(data.get("reasoning", ""))),
        "requires_approval": bool(data.get("requires_approval", False)),
        "decision_source": data.get("decision_source"),
    }


def _truncate(text: str, limit: int = _MAX_PREVIEW_CHARS) -> str:
    """Truncate a string to `limit` chars, appending a byte-count suffix."""
    if len(text) <= limit:
        return text
    overflow = len(text) - limit
    return f"{text[:limit]}… [+{overflow} chars]"


def _safe_parse_json(raw: str) -> dict[str, Any]:
    """Parse a JSON string, returning ``{}`` on any failure."""
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {"_value": parsed}
    except (json.JSONDecodeError, TypeError):
        return {"_raw": _truncate(raw, 200)}
