"""Unit tests for agent_factory.evidence — per-run audit trail extraction.

``extract_evidence`` consumes LangChain ``(AgentAction, observation)``
tuples natively from the executor's ``intermediate_steps`` list.
These tests pin that contract.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_factory.evidence_extractor import (
    extract_evidence,
    summarise_pipeline_health,
    _truncate,
    _try_parse_decision,
    _safe_parse_json,
    _extract_call_id,
    _derive_tool_status,
    _MAX_PREVIEW_CHARS,
)


# ---------------------------------------------------------------------------
# Helpers — LangChain `AgentAction` look-alike
# ---------------------------------------------------------------------------


def _action(tool: str, tool_input, call_id: str | None = None):
    """Build a minimal fake ``AgentAction``.

    Mirrors the langchain-openai 1.x shape: ``.tool`` (name),
    ``.tool_input`` (dict or str), optional ``.message_log`` carrying
    AIMessage-shape envelopes with ``.tool_calls``.
    """
    if call_id:
        message_log = [
            SimpleNamespace(tool_calls=[{"id": call_id, "name": tool}]),
        ]
    else:
        message_log = []
    return SimpleNamespace(tool=tool, tool_input=tool_input, message_log=message_log)


# ---------------------------------------------------------------------------
# extract_evidence — input/output contract
# ---------------------------------------------------------------------------


class TestExtractEvidence:

    def test_none_intermediate_steps_returns_empty(self):
        assert extract_evidence(None, pack_id="test") == []

    def test_empty_intermediate_steps_returns_empty(self):
        assert extract_evidence([], pack_id="test") == []

    def test_final_output_alone_yields_single_agent_message(self):
        evidence = extract_evidence(
            [], pack_id="my-pack", final_output="Triage done",
            agent_source="TriageAgent",
        )
        assert len(evidence) == 1
        entry = evidence[0]
        assert entry["type"] == "agent_message"
        assert entry["agent"] == "TriageAgent"
        assert entry["pack_id"] == "my-pack"
        assert "Triage done" in entry["content_preview"]

    def test_decision_payload_upgrades_to_decision_entry(self):
        decision_json = json.dumps({
            "runbook_card": "A2",
            "card_name": "Refresh Data",
            "confidence": "high",
            "reasoning": "DB is stale",
            "requires_approval": False,
            "decision_source": "yaml_rules",
        })
        evidence = extract_evidence(
            [], pack_id="pack", final_output=decision_json,
            agent_source="DecisionAgent",
        )
        assert len(evidence) == 1
        entry = evidence[0]
        assert entry["type"] == "decision"
        assert entry["decision"]["runbook_card"] == "A2"
        assert entry["decision"]["card_name"] == "Refresh Data"
        assert entry["decision"]["confidence"] == "high"
        assert entry["decision"]["requires_approval"] is False

    def test_single_tool_call_produces_call_and_result(self):
        steps = [
            (
                _action("DIAG-CHECK-API", {"service": "example-api"}),
                '{"status": "healthy"}',
            ),
        ]
        evidence = extract_evidence(
            steps, pack_id="pack", agent_source="DiagnosticAgent",
        )
        # 1 tool_call + 1 tool_result (no final_output so no agent_message)
        assert len(evidence) == 2
        call_entry = evidence[0]
        assert call_entry["type"] == "tool_call"
        assert call_entry["tool"] == "DIAG-CHECK-API"
        assert call_entry["args"] == {"service": "example-api"}
        assert call_entry["agent"] == "DiagnosticAgent"

        result_entry = evidence[1]
        assert result_entry["type"] == "tool_result"
        assert "healthy" in result_entry["result_preview"]
        # call_id pairs the entries
        assert result_entry["call_id"] == call_entry["call_id"]

    def test_call_id_from_message_log_preferred_over_positional(self):
        steps = [
            (_action("ping", {"x": 1}, call_id="call_abc"), "ok"),
        ]
        evidence = extract_evidence(steps, pack_id="pack")
        assert evidence[0]["call_id"] == "call_abc"
        assert evidence[1]["call_id"] == "call_abc"

    def test_positional_call_id_fallback(self):
        steps = [
            (_action("a", {}), "ok"),
            (_action("b", {}), "ok"),
        ]
        evidence = extract_evidence(steps, pack_id="pack")
        call_ids = [e["call_id"] for e in evidence if e["type"] == "tool_call"]
        assert call_ids == ["call_0", "call_1"]

    def test_tool_input_string_parsed_to_dict(self):
        steps = [(_action("foo", '{"already":"json"}'), "ok")]
        evidence = extract_evidence(steps, pack_id="pack")
        assert evidence[0]["args"] == {"already": "json"}

    def test_unparseable_tool_input_string_falls_back(self):
        steps = [(_action("foo", "not json"), "ok")]
        evidence = extract_evidence(steps, pack_id="pack")
        assert "_raw" in evidence[0]["args"]

    def test_non_dict_non_str_tool_input_wrapped(self):
        steps = [(_action("foo", [1, 2, 3]), "ok")]
        evidence = extract_evidence(steps, pack_id="pack")
        assert evidence[0]["args"] == {"_value": [1, 2, 3]}

    def test_none_tool_input_becomes_empty_dict(self):
        steps = [(_action("foo", None), "ok")]
        evidence = extract_evidence(steps, pack_id="pack")
        assert evidence[0]["args"] == {}

    def test_malformed_step_skipped(self):
        good = (_action("ok", {}), "ok")
        steps = [good, 12345, ("only_one",)]
        evidence = extract_evidence(steps, pack_id="pack", final_output="done")
        # 1 call + 1 result + 1 final = 3 entries
        assert len(evidence) == 3

    def test_pack_id_on_every_entry(self):
        steps = [(_action("TOOL", {}), "ok")]
        evidence = extract_evidence(
            steps, pack_id="my-specific-pack", final_output="text",
        )
        for entry in evidence:
            assert entry["pack_id"] == "my-specific-pack"

    def test_pipeline_order_preserved(self):
        steps = [
            (_action("first", {}), "1"),
            (_action("second", {}), "2"),
            (_action("third", {}), "3"),
        ]
        evidence = extract_evidence(steps, pack_id="pack", final_output="done")
        # Three (call, result) pairs in order + final agent_message
        types = [e["type"] for e in evidence]
        assert types == [
            "tool_call", "tool_result",
            "tool_call", "tool_result",
            "tool_call", "tool_result",
            "agent_message",
        ]
        tools = [e["tool"] for e in evidence if e["type"] == "tool_call"]
        assert tools == ["first", "second", "third"]

    def test_failed_tool_result_classified_as_error(self):
        steps = [
            (_action("lookup", {}), '{"outcome":"NOT_FOUND"}'),
        ]
        evidence = extract_evidence(steps, pack_id="pack")
        tool_result = evidence[1]
        assert tool_result["status"] == "error"
        assert tool_result["outcome"] == "NOT_FOUND"

    def test_http_error_in_error_field_classified_as_error(self):
        steps = [
            (_action("call", {}), '{"error":"HTTP 503: service unavailable"}'),
        ]
        evidence = extract_evidence(steps, pack_id="pack")
        assert evidence[1]["status"] == "error"

    def test_unknown_outcome_treated_as_success(self):
        """`data_not_found` is intentionally NOT in the error set —
        optional secondary data sources can legitimately return no rows
        and downstream pipeline health must not flip to 'partial'."""
        steps = [
            (_action("call", {}), '{"outcome":"data_not_found"}'),
        ]
        evidence = extract_evidence(steps, pack_id="pack")
        assert evidence[1]["status"] == "success"


# ---------------------------------------------------------------------------
# summarise_pipeline_health
# ---------------------------------------------------------------------------


class TestSummarisePipelineHealth:

    def test_no_tool_calls_yields_no_tools(self):
        evidence = [
            {"type": "agent_message", "agent": "x", "pack_id": "p"},
        ]
        health = summarise_pipeline_health(evidence)
        assert health["pipeline_status"] == "no_tools"
        assert health["tool_calls"] == 0
        assert health["has_failures"] is False

    def test_all_success_yields_success(self):
        evidence = [
            {"type": "tool_call", "tool": "a", "pack_id": "p"},
            {"type": "tool_result", "tool": "a", "status": "success"},
        ]
        health = summarise_pipeline_health(evidence)
        assert health["pipeline_status"] == "success"
        assert health["tool_failures"] == 0

    def test_mixed_yields_partial(self):
        evidence = [
            {"type": "tool_call", "tool": "a"},
            {"type": "tool_result", "tool": "a", "status": "success"},
            {"type": "tool_call", "tool": "b"},
            {"type": "tool_result", "tool": "b", "status": "error",
             "outcome": "AUTH_ERROR"},
        ]
        health = summarise_pipeline_health(evidence)
        assert health["pipeline_status"] == "partial"
        assert health["tool_failures"] == 1
        assert health["failed_tools"] == [
            {"tool": "b", "outcome": "AUTH_ERROR"},
        ]

    def test_all_failures_yields_failed(self):
        evidence = [
            {"type": "tool_call", "tool": "a"},
            {"type": "tool_result", "tool": "a", "status": "error",
             "outcome": "404"},
        ]
        health = summarise_pipeline_health(evidence)
        assert health["pipeline_status"] == "failed"


# ---------------------------------------------------------------------------
# _extract_call_id — message_log walking
# ---------------------------------------------------------------------------


class TestExtractCallId:

    def test_no_message_log_returns_empty(self):
        action = _action("ping", {})
        assert _extract_call_id(action, "ping") == ""

    def test_matching_name_returns_id(self):
        action = _action("ping", {}, call_id="call_xyz")
        assert _extract_call_id(action, "ping") == "call_xyz"

    def test_mismatched_name_returns_empty(self):
        """Defensive — a stray tool_call envelope for a different tool
        in message_log must not bleed its id into our entry."""
        action = SimpleNamespace(
            tool="ping",
            tool_input={},
            message_log=[
                SimpleNamespace(
                    tool_calls=[{"id": "call_other", "name": "OTHER"}],
                ),
            ],
        )
        assert _extract_call_id(action, "ping") == ""

    def test_additional_kwargs_fallback_path(self):
        """langchain-openai 0.3.x puts tool_calls in additional_kwargs."""
        action = SimpleNamespace(
            tool="ping",
            tool_input={},
            message_log=[
                SimpleNamespace(
                    tool_calls=None,
                    additional_kwargs={
                        "tool_calls": [
                            {"id": "call_zzz", "function": {"name": "ping"}},
                        ],
                    },
                ),
            ],
        )
        assert _extract_call_id(action, "ping") == "call_zzz"


# ---------------------------------------------------------------------------
# _derive_tool_status
# ---------------------------------------------------------------------------


class TestDeriveToolStatus:

    def test_empty_result_is_success(self):
        assert _derive_tool_status("") == ("success", None)

    def test_non_json_is_success(self):
        assert _derive_tool_status("just a string") == ("success", None)

    def test_known_error_outcome(self):
        status, outcome = _derive_tool_status('{"outcome":"AUTH_ERROR"}')
        assert status == "error"
        assert outcome == "AUTH_ERROR"

    def test_data_not_found_is_success(self):
        status, _ = _derive_tool_status('{"outcome":"data_not_found"}')
        assert status == "success"

    def test_http_error_code_in_error_field(self):
        status, _ = _derive_tool_status('{"error":"HTTP 500: internal"}')
        assert status == "error"

    def test_error_key_without_outcome(self):
        status, outcome = _derive_tool_status('{"error":"something broke"}')
        assert status == "error"
        assert "something broke" in outcome


# ---------------------------------------------------------------------------
# _truncate
# ---------------------------------------------------------------------------


class TestTruncate:

    def test_short_string_unchanged(self):
        s = "hello"
        assert _truncate(s) == s

    def test_exactly_limit_unchanged(self):
        s = "x" * _MAX_PREVIEW_CHARS
        assert _truncate(s) == s

    def test_long_string_truncated(self):
        s = "a" * (_MAX_PREVIEW_CHARS + 50)
        result = _truncate(s)
        assert len(result) > _MAX_PREVIEW_CHARS  # includes the suffix
        assert "…" in result
        assert "+50 chars" in result

    def test_custom_limit(self):
        s = "hello world"
        result = _truncate(s, limit=5)
        assert result.startswith("hello")
        assert "…" in result


# ---------------------------------------------------------------------------
# _try_parse_decision
# ---------------------------------------------------------------------------


class TestTryParseDecision:

    def test_no_runbook_card_returns_none(self):
        assert _try_parse_decision("Some plain text") is None

    def test_valid_decision_json(self):
        payload = json.dumps({
            "runbook_card": "B1",
            "card_name": "No Action",
            "confidence": "high",
            "reasoning": "All checks passed",
            "requires_approval": False,
            "decision_source": "yaml_rules",
        })
        result = _try_parse_decision(payload)

        assert result is not None
        assert result["runbook_card"] == "B1"
        assert result["confidence"] == "high"
        assert result["requires_approval"] is False

    def test_invalid_json_with_keyword_returns_none(self):
        """If 'runbook_card' appears in plain text but isn't valid JSON."""
        assert _try_parse_decision("runbook_card A1 selected") is None

    def test_requires_approval_coerced_to_bool(self):
        payload = json.dumps({
            "runbook_card": "A1",
            "requires_approval": 1,
        })
        result = _try_parse_decision(payload)
        assert result["requires_approval"] is True


# ---------------------------------------------------------------------------
# _safe_parse_json
# ---------------------------------------------------------------------------


class TestSafeParseJson:

    def test_valid_dict(self):
        assert _safe_parse_json('{"key": "value"}') == {"key": "value"}

    def test_empty_string(self):
        assert _safe_parse_json("") == {}

    def test_invalid_json(self):
        result = _safe_parse_json("{not json}")
        assert "_raw" in result

    def test_json_array_wrapped(self):
        result = _safe_parse_json('[1, 2, 3]')
        assert result == {"_value": [1, 2, 3]}
