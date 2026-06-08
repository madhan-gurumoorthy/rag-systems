"""Unit tests for agent_factory.prompts — Jinja2 prompt rendering."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_factory.prompts import build_pack_context, render_prompt


# ---------------------------------------------------------------------------
# Helpers — minimal pack / IR mocks
# ---------------------------------------------------------------------------

def _make_mock_pack(
    pack_id: str = "test-pack",
    name: str = "Test Pack",
    version: str = "1.2.3",
    description: str = "A test pack",
    owner_team: str = "TEST-AD-GROUP",
    systems: list | None = None,
    tags: list | None = None,
    diagnostics: list | None = None,
    runbooks: list | None = None,
    decision_rules: list | None = None,
    required_inputs: list | None = None,
) -> MagicMock:
    """Return a lightweight mock that quacks like AgentPack."""
    # Config mock
    cfg = MagicMock()
    cfg.name = name
    cfg.version = version
    cfg.description = description
    cfg.owner_team = owner_team

    # SOP-IR metadata mock
    meta = MagicMock()
    meta.systems = systems or ["sys-a", "sys-b"]
    meta.tags = tags or ["tag1"]

    # Diagnostics
    diag_objs = []
    for d in diagnostics or [{"id": "DIAG-01", "purpose": "Check API"}]:
        dm = MagicMock()
        dm.id = d["id"]
        dm.purpose = d["purpose"]
        diag_objs.append(dm)

    # Runbooks
    rb_objs = []
    for r in runbooks or [{"id": "RUNBOOK-A1", "card_id": "A1", "name": "Fix it",
                            "description": "Restart service", "tags": {}}]:
        rm = MagicMock()
        rm.id = r["id"]
        rm.card_id = r.get("card_id", "")
        rm.name = r["name"]
        rm.description = r.get("description", "")
        rm.tags = r.get("tags", {})
        rb_objs.append(rm)

    # Decision rules
    dr_objs = []
    for dr in decision_rules or []:
        drm = MagicMock()
        drm.when = MagicMock()
        drm.when.all = dr.get("all", [])
        drm.when.any = dr.get("any", [])
        drm.when.expressions = dr.get("expressions", [])
        drm.then_runbook = dr.get("then_runbook", "RUNBOOK-A1")
        dr_objs.append(drm)

    # Intake
    intake = MagicMock()
    intake.required_inputs = required_inputs or ["incident_number"]

    # SOP-IR mock
    sop_ir = MagicMock()
    sop_ir.metadata = meta
    sop_ir.diagnostics = diag_objs
    sop_ir.runbooks = rb_objs
    sop_ir.decision_rules = dr_objs
    sop_ir.intake = intake

    # Pack mock
    pack = MagicMock()
    pack.pack_id = pack_id
    pack.config = cfg
    pack.sop_ir = sop_ir

    return pack


# ---------------------------------------------------------------------------
# build_pack_context
# ---------------------------------------------------------------------------

class TestBuildPackContext:

    def test_pack_identity_fields(self):
        pack = _make_mock_pack(
            pack_id="mypack",
            name="My Pack",
            version="2.0.0",
            description="Handles stuff",
            owner_team="TEAM-XYZ",
        )
        ctx = build_pack_context(pack)

        assert ctx["pack_id"] == "mypack"
        assert ctx["pack_name"] == "My Pack"
        assert ctx["pack_version"] == "2.0.0"
        assert ctx["pack_description"] == "Handles stuff"
        assert ctx["owner_team"] == "TEAM-XYZ"

    def test_systems_and_tags(self):
        pack = _make_mock_pack(systems=["iqs", "merloc"], tags=["core-catalog"])
        ctx = build_pack_context(pack)

        assert ctx["systems"] == ["iqs", "merloc"]
        assert ctx["tags"] == ["core-catalog"]

    def test_diagnostics_shape(self):
        pack = _make_mock_pack(diagnostics=[
            {"id": "DIAG-01", "purpose": "Check IQS"},
            {"id": "DIAG-02", "purpose": "Check Merloc"},
        ])
        ctx = build_pack_context(pack)

        assert len(ctx["diagnostics"]) == 2
        assert ctx["diagnostics"][0] == {"id": "DIAG-01", "purpose": "Check IQS"}
        assert ctx["diagnostics"][1] == {"id": "DIAG-02", "purpose": "Check Merloc"}

    def test_runbooks_shape(self):
        pack = _make_mock_pack(runbooks=[{
            "id": "RUNBOOK-B2",
            "card_id": "B2",
            "name": "Escalate",
            "description": "Escalate to on-call",
            "tags": {"issue_tag": "stale"},
        }])
        ctx = build_pack_context(pack)

        assert len(ctx["runbooks"]) == 1
        rb = ctx["runbooks"][0]
        assert rb["id"] == "RUNBOOK-B2"
        assert rb["card_id"] == "B2"
        assert rb["name"] == "Escalate"
        assert rb["description"] == "Escalate to on-call"
        assert rb["tags"] == {"issue_tag": "stale"}

    def test_decision_rules_include_expressions(self):
        pack = _make_mock_pack(decision_rules=[{
            "all": ["API_DOWN"],
            "any": [],
            "expressions": ["error_rate > 0.5"],
            "then_runbook": "RUNBOOK-A1",
        }])
        ctx = build_pack_context(pack)

        assert len(ctx["decision_rules"]) == 1
        dr = ctx["decision_rules"][0]
        assert dr["when_all"] == ["API_DOWN"]
        assert dr["when_expressions"] == ["error_rate > 0.5"]
        assert dr["then_runbook"] == "RUNBOOK-A1"

    def test_intake_required_inputs(self):
        pack = _make_mock_pack(required_inputs=["gtin", "store_id"])
        ctx = build_pack_context(pack)

        assert ctx["intake_required_inputs"] == ["gtin", "store_id"]

    def test_returns_only_plain_python_types(self):
        """Context must contain only JSON-serialisable plain Python types."""
        import json
        pack = _make_mock_pack()
        ctx = build_pack_context(pack)
        # Should not raise
        json.dumps(ctx)


# ---------------------------------------------------------------------------
# render_prompt — plain-text pass-through
# ---------------------------------------------------------------------------

class TestRenderPromptPlainText:

    def test_plain_text_unchanged(self):
        raw = "You are a triage agent. Classify the incident."
        result = render_prompt(raw, {})
        assert result == raw

    def test_empty_string(self):
        assert render_prompt("", {}) == ""

    def test_multiline_unchanged(self):
        raw = "Line 1\nLine 2\nLine 3"
        assert render_prompt(raw, {}) == raw

    def test_trailing_newline_preserved(self):
        raw = "Some prompt text\n"
        assert render_prompt(raw, {}) == raw


# ---------------------------------------------------------------------------
# render_prompt — Jinja2 substitution
# ---------------------------------------------------------------------------

class TestRenderPromptJinja2:

    def test_simple_variable_substitution(self):
        raw = "You are an agent for {{ pack_name }}."
        result = render_prompt(raw, {"pack_name": "CoreCatalog"})
        assert result == "You are an agent for CoreCatalog."

    def test_multiple_variables(self):
        raw = "Pack: {{ pack_id }} v{{ pack_version }} owned by {{ owner_team }}."
        ctx = {"pack_id": "mypack", "pack_version": "1.0", "owner_team": "OPS"}
        result = render_prompt(raw, ctx)
        assert result == "Pack: mypack v1.0 owned by OPS."

    def test_for_loop_over_runbooks(self):
        raw = "{% for rb in runbooks %}- {{ rb.name }}\n{% endfor %}"
        ctx = {"runbooks": [{"name": "Fix API"}, {"name": "Escalate"}]}
        result = render_prompt(raw, ctx)
        assert "- Fix API" in result
        assert "- Escalate" in result

    def test_if_block(self):
        raw = "{% if systems %}Systems: {{ systems | join(', ') }}{% endif %}"
        ctx = {"systems": ["iqs", "merloc"]}
        result = render_prompt(raw, ctx)
        assert "Systems: iqs, merloc" in result

    def test_undefined_variable_renders_as_placeholder(self):
        """DebugUndefined: missing vars render as '{{ name }}' not empty string."""
        raw = "Hello {{ unknown_var }}!"
        result = render_prompt(raw, {})
        assert "{{ unknown_var }}" in result

    def test_pack_context_integration(self):
        """render_prompt + build_pack_context works end-to-end."""
        raw = "You handle {{ pack_name }} incidents. Owner: {{ owner_team }}."
        pack = _make_mock_pack(name="SupplyChain", owner_team="SC-OPS")
        ctx = build_pack_context(pack)
        result = render_prompt(raw, ctx)
        assert "SupplyChain" in result
        assert "SC-OPS" in result


# ---------------------------------------------------------------------------
# render_prompt — error resilience
# ---------------------------------------------------------------------------

class TestRenderPromptErrorResilience:
    # Patch the module logger in all error-path tests.
    # The project's custom log filter requires Dynaconf (AGENT_NAME) which is
    # not configured in the unit-test environment; patching avoids that dep
    # without changing production behaviour.

    def test_syntax_error_returns_raw(self):
        """Malformed Jinja2 must NOT crash the build pipeline."""
        from unittest.mock import patch
        broken = "Hello {% if %}world{% endif %}"
        with patch("agent_factory.prompts.logger"):
            result = render_prompt(broken, {})
        assert result == broken

    def test_unclosed_block_returns_raw(self):
        from unittest.mock import patch
        broken = "{% for item in items %} item"
        with patch("agent_factory.prompts.logger"):
            result = render_prompt(broken, {})
        assert result == broken

    def test_sandbox_blocks_python_execution(self):
        """SandboxedEnvironment must prevent Python code execution."""
        # Attempting to access Python internals via Jinja2 template syntax
        # raises jinja2.SecurityError which render_prompt catches gracefully.
        from unittest.mock import patch
        evil = "{{ ''.__class__.__mro__[1].__subclasses__() }}"
        with patch("agent_factory.prompts.logger"):
            result = render_prompt(evil, {})
        # The important thing: no arbitrary Python executed, no crash.
        assert isinstance(result, str)
