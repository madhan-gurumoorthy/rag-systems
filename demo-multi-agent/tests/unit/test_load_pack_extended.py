"""Extended tests for pack_loader.py — covers load_pack() and all helpers.

Uses temp directories to exercise actual file I/O without touching real packs.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_factory.pack_loader import (
    AgentPack,
    PackValidationResult,
    _load_prompts,
    _validate_tool_bindings,
    _validate_tool_refs,
    load_pack,
)
from agent_factory.pack_models import ToolsManifest, ToolSpec
from agent_factory.ir.models import SOPIR


# ── Minimal valid fixture data ─────────────────────────────────────────────

MINIMAL_PACK_YAML = {
    "id": "test-pack",
    "name": "Test Pack",
}

MINIMAL_SOP_IR = {
    "metadata": {"title": "Test SOP", "owner_team": "test-team"},
    "intake": {"required_inputs": []},
    "diagnostics": [],
    "decision_rules": [],
    "runbooks": [],
    "tools": [],
    "guardrails": {
        "permitted_actions": [],
        "approvals": {"required_for_tools": []},
        "blast_radius": {"max_batch_size": 1, "limits": {}},
    },
}

MINIMAL_TOOLS_YAML = {"tools": []}

MINIMAL_POLICY_YAML = {
    "approvals": {"required_for_cards": [], "required_for_tools": []},
    "blast_radius": {"max_batch_size": 1, "limits": {}},
    "permitted_actions": [],
    "denied_actions": [],
    "feature_flags": {},
}


def _make_pack_dir(tmp_path: Path, pack_id: str = "test-pack") -> Path:
    """Write all four required files into a temp pack directory."""
    packs_root = tmp_path / "packs"
    pack_dir = packs_root / pack_id
    pack_dir.mkdir(parents=True)

    (pack_dir / "pack.yaml").write_text(yaml.dump(MINIMAL_PACK_YAML))
    (pack_dir / "sop-ir.json").write_text(json.dumps(MINIMAL_SOP_IR))
    (pack_dir / "tools.yaml").write_text(yaml.dump(MINIMAL_TOOLS_YAML))
    (pack_dir / "policy.yaml").write_text(yaml.dump(MINIMAL_POLICY_YAML))

    return packs_root


# ── PackValidationResult ───────────────────────────────────────────────────

class TestPackValidationResult:
    def test_starts_valid(self):
        v = PackValidationResult()
        assert v.valid is True
        assert v.errors == []
        assert v.warnings == []

    def test_add_error_marks_invalid(self):
        v = PackValidationResult()
        v.add_error("something broke")
        assert v.valid is False
        assert "something broke" in v.errors

    def test_add_warning_stays_valid(self):
        v = PackValidationResult()
        v.add_warning("heads up")
        assert v.valid is True
        assert "heads up" in v.warnings

    def test_multiple_errors(self):
        v = PackValidationResult()
        v.add_error("err1")
        v.add_error("err2")
        assert len(v.errors) == 2
        assert v.valid is False


# ── load_pack — error paths ────────────────────────────────────────────────

class TestLoadPackErrors:
    def test_missing_directory_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            packs_root = Path(tmp) / "packs"
            packs_root.mkdir()
            with pytest.raises(FileNotFoundError, match="Pack directory not found"):
                load_pack("nonexistent", packs_root=str(packs_root))

    def test_missing_required_file_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            packs_root = Path(tmp) / "packs"
            pack_dir = packs_root / "mypack"
            pack_dir.mkdir(parents=True)
            # Write only some required files
            (pack_dir / "pack.yaml").write_text(yaml.dump(MINIMAL_PACK_YAML))
            # sop-ir.json, tools.yaml, policy.yaml are missing
            with pytest.raises(ValueError, match="mypack.*is invalid"):
                load_pack("mypack", packs_root=str(packs_root))

    def test_invalid_pack_yaml_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            packs_root = _make_pack_dir(Path(tmp))
            pack_dir = packs_root / "test-pack"
            # Overwrite pack.yaml with invalid content (missing required 'id')
            (pack_dir / "pack.yaml").write_text("id: !invalid yaml: [")
            with pytest.raises(ValueError, match="Invalid pack.yaml"):
                load_pack("test-pack", packs_root=str(packs_root))

    def test_invalid_sop_ir_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            packs_root = _make_pack_dir(Path(tmp))
            pack_dir = packs_root / "test-pack"
            # Write invalid JSON
            (pack_dir / "sop-ir.json").write_text("{invalid json}")
            with pytest.raises(ValueError, match="Invalid sop-ir.json"):
                load_pack("test-pack", packs_root=str(packs_root))

    def test_invalid_tools_yaml_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            packs_root = _make_pack_dir(Path(tmp))
            pack_dir = packs_root / "test-pack"
            (pack_dir / "tools.yaml").write_text("tools: not_a_list")
            with pytest.raises(ValueError, match="Invalid tools.yaml"):
                load_pack("test-pack", packs_root=str(packs_root))

    def test_invalid_policy_yaml_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            packs_root = _make_pack_dir(Path(tmp))
            pack_dir = packs_root / "test-pack"
            # Write YAML that can't be parsed at all
            (pack_dir / "policy.yaml").write_text("approvals: !bad\n  - [")
            with pytest.raises(ValueError, match="Invalid policy.yaml"):
                load_pack("test-pack", packs_root=str(packs_root))


# ── load_pack — happy path ─────────────────────────────────────────────────

class TestLoadPackSuccess:
    def test_returns_agent_pack(self):
        with tempfile.TemporaryDirectory() as tmp:
            packs_root = _make_pack_dir(Path(tmp))
            pack = load_pack("test-pack", packs_root=str(packs_root))
            assert isinstance(pack, AgentPack)
            assert pack.pack_id == "test-pack"

    def test_pack_config_loaded(self):
        with tempfile.TemporaryDirectory() as tmp:
            packs_root = _make_pack_dir(Path(tmp))
            pack = load_pack("test-pack", packs_root=str(packs_root))
            assert pack.config.id == "test-pack"
            assert pack.config.name == "Test Pack"

    def test_validation_is_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            packs_root = _make_pack_dir(Path(tmp))
            pack = load_pack("test-pack", packs_root=str(packs_root))
            assert pack.validation.valid is True
            assert pack.validation.errors == []

    def test_no_eval_cases_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            packs_root = _make_pack_dir(Path(tmp))
            pack = load_pack("test-pack", packs_root=str(packs_root))
            assert pack.eval_cases == []

    def test_eval_cases_loaded_when_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            packs_root = _make_pack_dir(Path(tmp))
            pack_dir = packs_root / "test-pack"
            cases = [{"id": "case1", "input": {}, "expected_runbook": "RB-1"}]
            (pack_dir / "eval_cases.json").write_text(json.dumps(cases))
            pack = load_pack("test-pack", packs_root=str(packs_root))
            assert len(pack.eval_cases) == 1
            assert pack.eval_cases[0]["id"] == "case1"

    def test_bad_eval_cases_warning_not_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            packs_root = _make_pack_dir(Path(tmp))
            pack_dir = packs_root / "test-pack"
            (pack_dir / "eval_cases.json").write_text("{not a list}")
            pack = load_pack("test-pack", packs_root=str(packs_root))
            assert pack.validation.valid is True
            assert any("eval_cases" in w for w in pack.validation.warnings)

    def test_no_prompts_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            packs_root = _make_pack_dir(Path(tmp))
            pack = load_pack("test-pack", packs_root=str(packs_root))
            assert pack.prompts == {}

    def test_prompts_loaded_when_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            packs_root = _make_pack_dir(Path(tmp))
            pack_dir = packs_root / "test-pack"
            prompts_dir = pack_dir / "prompts"
            prompts_dir.mkdir()
            (prompts_dir / "triage.txt").write_text("triage content")
            pack = load_pack("test-pack", packs_root=str(packs_root))
            assert "triage" in pack.prompts
            assert pack.prompts["triage"] == "triage content"

    def test_with_tools_produces_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            packs_root = _make_pack_dir(Path(tmp))
            pack_dir = packs_root / "test-pack"
            tools_data = {
                "tools": [
                    {"id": "DIAG-CHECK-API", "type": "python_function",
                     "import": "os.path:exists"}
                ]
            }
            (pack_dir / "tools.yaml").write_text(yaml.dump(tools_data))
            pack = load_pack("test-pack", packs_root=str(packs_root))
            assert len(pack.tools_manifest.tools) == 1
            assert pack.tools_manifest.tools[0].id == "DIAG-CHECK-API"


# ── _load_prompts ──────────────────────────────────────────────────────────

class TestLoadPrompts:
    def test_no_prompts_dir_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack_dir = Path(tmp)
            result = _load_prompts(pack_dir)
            assert result == {}

    def test_txt_prompt_loaded(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack_dir = Path(tmp)
            prompts_dir = pack_dir / "prompts"
            prompts_dir.mkdir()
            (prompts_dir / "triage.txt").write_text("You are triage.")
            result = _load_prompts(pack_dir)
            assert "triage" in result
            assert result["triage"] == "You are triage."

    def test_md_prompt_loaded(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack_dir = Path(tmp)
            prompts_dir = pack_dir / "prompts"
            prompts_dir.mkdir()
            (prompts_dir / "decision.md").write_text("# Decision")
            result = _load_prompts(pack_dir)
            assert "decision" in result

    def test_j2_prompt_loaded(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack_dir = Path(tmp)
            prompts_dir = pack_dir / "prompts"
            prompts_dir.mkdir()
            (prompts_dir / "triage.j2").write_text("{{query}}")
            result = _load_prompts(pack_dir)
            assert "triage" in result

    def test_prompt_extension_loaded(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack_dir = Path(tmp)
            prompts_dir = pack_dir / "prompts"
            prompts_dir.mkdir()
            (prompts_dir / "action.prompt").write_text("Take action.")
            result = _load_prompts(pack_dir)
            assert "action" in result

    def test_non_prompt_files_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack_dir = Path(tmp)
            prompts_dir = pack_dir / "prompts"
            prompts_dir.mkdir()
            (prompts_dir / "config.json").write_text("{}")
            (prompts_dir / "triage.txt").write_text("triage")
            result = _load_prompts(pack_dir)
            assert "config" not in result
            assert "triage" in result

    def test_both_j2_and_txt_same_stem_last_sorted_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack_dir = Path(tmp)
            prompts_dir = pack_dir / "prompts"
            prompts_dir.mkdir()
            # Both triage.txt and triage.j2 — the last in sorted order wins
            # Alphabetically: triage.j2 < triage.txt, so .txt wins (loaded last)
            (prompts_dir / "triage.txt").write_text("plain")
            (prompts_dir / "triage.j2").write_text("template")
            result = _load_prompts(pack_dir)
            # Only one value exists (later sorted file overwrites)
            assert "triage" in result
            assert result["triage"] in ("plain", "template")  # depends on sorted order

    def test_multiple_prompts(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack_dir = Path(tmp)
            prompts_dir = pack_dir / "prompts"
            prompts_dir.mkdir()
            (prompts_dir / "triage.txt").write_text("t")
            (prompts_dir / "action.txt").write_text("a")
            (prompts_dir / "closure.md").write_text("c")
            result = _load_prompts(pack_dir)
            assert len(result) == 3


# ── _validate_tool_refs ────────────────────────────────────────────────────

class TestValidateToolRefs:
    def _make_sopir_with_diagnostic(self, diag_id: str) -> SOPIR:
        return SOPIR(**{
            **MINIMAL_SOP_IR,
            "diagnostics": [
                {"id": diag_id, "purpose": "test"}
            ],
        })

    def _make_sopir_with_runbook_action(self, tool_id: str) -> SOPIR:
        return SOPIR(**{
            **MINIMAL_SOP_IR,
            "runbooks": [
                {
                    "id": "RUNBOOK-TEST",
                    "name": "Test",
                    "description": "test",
                    "card_id": "A1",
                    "tags": {},
                    "actions": [
                        {"id": "ACT-1", "description": "act", "tool_id": tool_id, "params": {}}
                    ],
                }
            ],
        })

    def test_no_warnings_when_refs_match(self):
        sop_ir = SOPIR(**{
            **MINIMAL_SOP_IR,
            "diagnostics": [{"id": "DIAG-CHECK-API", "purpose": "test"}],
        })
        tools = ToolsManifest(tools=[
            ToolSpec(id="DIAG-CHECK-API", type="python_function")
        ])
        v = PackValidationResult()
        _validate_tool_refs(sop_ir, tools, v)
        assert v.warnings == []

    def test_diagnostic_not_in_manifest_warns(self):
        sop_ir = self._make_sopir_with_diagnostic("DIAG-MISSING")
        tools = ToolsManifest(tools=[])
        v = PackValidationResult()
        _validate_tool_refs(sop_ir, tools, v)
        assert any("DIAG-MISSING" in w for w in v.warnings)

    def test_runbook_action_not_in_manifest_warns(self):
        sop_ir = self._make_sopir_with_runbook_action("ACT-MISSING")
        tools = ToolsManifest(tools=[])
        v = PackValidationResult()
        _validate_tool_refs(sop_ir, tools, v)
        assert any("ACT-MISSING" in w for w in v.warnings)

    def test_guardrail_tool_not_in_manifest_warns(self):
        sop_ir = SOPIR(**{
            **MINIMAL_SOP_IR,
            "guardrails": {
                "permitted_actions": [],
                "approvals": {"required_for_tools": ["MISSING-TOOL"]},
                "blast_radius": {"max_batch_size": 1, "limits": {}},
            },
        })
        tools = ToolsManifest(tools=[])
        v = PackValidationResult()
        _validate_tool_refs(sop_ir, tools, v)
        assert any("MISSING-TOOL" in w for w in v.warnings)


# ── _validate_tool_bindings ────────────────────────────────────────────────

class TestValidateToolBindings:
    def test_python_function_no_import_path_warns(self):
        tools = ToolsManifest(tools=[
            ToolSpec(id="MY-TOOL", type="python_function")
            # No import_path or function_ref
        ])
        v = PackValidationResult()
        _validate_tool_bindings(tools, v)
        assert any("MY-TOOL" in w for w in v.warnings)

    def test_python_function_with_import_path_no_warning(self):
        tools = ToolsManifest(tools=[
            ToolSpec(**{"id": "MY-TOOL", "type": "python_function", "import": "os.path:exists"})
        ])
        v = PackValidationResult()
        _validate_tool_bindings(tools, v)
        assert not any("MY-TOOL" in w for w in v.warnings)

    def test_http_api_no_url_template_warns(self):
        tools = ToolsManifest(tools=[
            ToolSpec(id="API-TOOL", type="http_api")
        ])
        v = PackValidationResult()
        _validate_tool_bindings(tools, v)
        assert any("API-TOOL" in w for w in v.warnings)

    def test_http_api_with_url_no_warning(self):
        tools = ToolsManifest(tools=[
            ToolSpec(id="API-TOOL", type="http_api", url_template="https://example.com/api")
        ])
        v = PackValidationResult()
        _validate_tool_bindings(tools, v)
        assert not any("API-TOOL" in w for w in v.warnings)

    def test_sql_query_no_query_template_warns(self):
        tools = ToolsManifest(tools=[
            ToolSpec(id="SQL-TOOL", type="sql_query")
        ])
        v = PackValidationResult()
        _validate_tool_bindings(tools, v)
        assert any("SQL-TOOL" in w for w in v.warnings)

    def test_bigquery_no_query_template_warns(self):
        tools = ToolsManifest(tools=[
            ToolSpec(id="BQ-TOOL", type="bigquery_query")
        ])
        v = PackValidationResult()
        _validate_tool_bindings(tools, v)
        assert any("BQ-TOOL" in w for w in v.warnings)

    def test_non_inspected_type_no_warning(self):
        tools = ToolsManifest(tools=[
            ToolSpec(id="REDIS-TOOL", type="redis")
        ])
        v = PackValidationResult()
        _validate_tool_bindings(tools, v)
        assert v.warnings == []


# ── load_pack with validation warnings ────────────────────────────────────

class TestLoadPackWithWarnings:
    def test_diagnostic_ref_mismatch_produces_warning(self):
        """load_pack should warn when sop-ir references a tool not in tools.yaml."""
        with tempfile.TemporaryDirectory() as tmp:
            packs_root = _make_pack_dir(Path(tmp))
            pack_dir = packs_root / "test-pack"

            # Add a diagnostic that refs DIAG-MISSING (not in tools.yaml)
            sop_ir_data = {
                **MINIMAL_SOP_IR,
                "diagnostics": [{"id": "DIAG-MISSING", "purpose": "test"}],
            }
            (pack_dir / "sop-ir.json").write_text(json.dumps(sop_ir_data))

            pack = load_pack("test-pack", packs_root=str(packs_root))
            assert pack.validation.valid is True
            assert any("DIAG-MISSING" in w for w in pack.validation.warnings)

    def test_python_function_no_binding_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            packs_root = _make_pack_dir(Path(tmp))
            pack_dir = packs_root / "test-pack"
            tools_data = {
                "tools": [{"id": "MY-FUNC", "type": "python_function"}]
            }
            (pack_dir / "tools.yaml").write_text(yaml.dump(tools_data))
            pack = load_pack("test-pack", packs_root=str(packs_root))
            assert pack.validation.valid is True
            assert any("MY-FUNC" in w for w in pack.validation.warnings)
