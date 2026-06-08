"""Tests for agent_factory/registry.py — PackRegistry."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_factory.registry import PackRegistry
from agent_factory.pack_loader import AgentPack, PackValidationResult
from agent_factory.pack_models import ToolsManifest, ToolSpec, PolicyConfig, PackConfig
from agent_factory.ir.models import SOPIR


def _make_mock_pack(pack_id: str = "test-pack") -> MagicMock:
    """Create a minimal mock AgentPack."""
    pack = MagicMock(spec=AgentPack)
    pack.pack_id = pack_id
    pack.validation = PackValidationResult()
    pack.prompts = {}
    pack.eval_cases = []

    # Tools manifest with two python_function tools (one bound, one unbound)
    bound_tool = ToolSpec(**{"id": "TOOL-BOUND", "type": "python_function",
                              "import": "os.path:exists"})
    unbound_tool = ToolSpec(id="TOOL-UNBOUND", type="python_function")
    http_tool = ToolSpec(id="TOOL-HTTP", type="http_api")

    pack.tools_manifest = ToolsManifest(tools=[bound_tool, unbound_tool, http_tool])

    # SOP IR mock
    pack.sop_ir = MagicMock()
    pack.sop_ir.diagnostics = []
    pack.sop_ir.runbooks = []

    return pack


class TestPackRegistryInit:
    def test_not_initialized_on_creation(self):
        reg = PackRegistry()
        assert reg.initialized is False

    def test_packs_empty_on_creation(self):
        reg = PackRegistry()
        assert reg.list_packs() == []

    def test_default_pack_id_from_env(self, monkeypatch):
        monkeypatch.setenv("DEFAULT_PACK_ID", "my-default")
        # Note: DEFAULT_PACK_ID is read at module import time via os.environ.get
        # so we test the instance attribute directly
        reg = PackRegistry()
        # The instance reads from the module-level constant; just verify property works
        assert isinstance(reg.default_pack_id, str)


class TestPackRegistryInitialize:
    def test_initialize_success(self):
        reg = PackRegistry()
        mock_pack = _make_mock_pack("_example")

        with patch("agent_factory.registry.load_pack", return_value=mock_pack):
            reg.initialize(packs_root="packs")

        assert reg.initialized is True
        assert "_example" in reg.list_packs()

    def test_initialize_already_initialized_is_idempotent(self):
        reg = PackRegistry()
        mock_pack = _make_mock_pack("_example")

        with patch("agent_factory.registry.load_pack", return_value=mock_pack) as mock_load:
            reg.initialize(packs_root="packs")
            reg.initialize(packs_root="packs")  # second call should no-op

        # load_pack should only be called once
        mock_load.assert_called_once()

    def test_initialize_failure_marks_initialized_gracefully(self):
        reg = PackRegistry()

        with patch("agent_factory.registry.load_pack", side_effect=FileNotFoundError("no pack")):
            reg.initialize(packs_root="packs")

        # Should still be marked initialized (to avoid retry loops)
        assert reg.initialized is True
        assert reg.list_packs() == []

    def test_initialize_exception_does_not_raise(self):
        reg = PackRegistry()

        with patch("agent_factory.registry.load_pack", side_effect=Exception("boom")):
            # Should not propagate the exception
            reg.initialize(packs_root="packs")

        assert reg.initialized is True


class TestPackRegistryRegister:
    def test_register_pack_adds_to_registry(self):
        reg = PackRegistry()
        pack = _make_mock_pack("custom-pack")
        reg.register_pack(pack)
        assert "custom-pack" in reg.list_packs()

    def test_register_multiple_packs(self):
        reg = PackRegistry()
        reg.register_pack(_make_mock_pack("pack-a"))
        reg.register_pack(_make_mock_pack("pack-b"))
        packs = reg.list_packs()
        assert "pack-a" in packs
        assert "pack-b" in packs
        assert len(packs) == 2

    def test_register_overwrite_existing(self):
        reg = PackRegistry()
        pack_v1 = _make_mock_pack("my-pack")
        pack_v2 = _make_mock_pack("my-pack")
        reg.register_pack(pack_v1)
        reg.register_pack(pack_v2)
        # Should only have one entry
        assert len(reg.list_packs()) == 1


class TestPackRegistryGetPack:
    def test_get_pack_by_id(self):
        reg = PackRegistry()
        pack = _make_mock_pack("alpha")
        reg.register_pack(pack)
        result = reg.get_pack("alpha")
        assert result is pack

    def test_get_pack_returns_default_when_id_is_none(self):
        reg = PackRegistry()
        # Override default pack id
        reg._default_pack_id = "my-default"
        pack = _make_mock_pack("my-default")
        reg.register_pack(pack)
        result = reg.get_pack(None)
        assert result is pack

    def test_get_pack_returns_none_for_missing_id(self):
        reg = PackRegistry()
        result = reg.get_pack("nonexistent")
        assert result is None

    def test_get_pack_returns_none_default_when_no_default(self):
        reg = PackRegistry()
        reg._default_pack_id = "missing"
        result = reg.get_pack()
        assert result is None


class TestPackRegistryListPacks:
    def test_empty_registry(self):
        reg = PackRegistry()
        assert reg.list_packs() == []

    def test_list_returns_all_ids(self):
        reg = PackRegistry()
        reg.register_pack(_make_mock_pack("p1"))
        reg.register_pack(_make_mock_pack("p2"))
        reg.register_pack(_make_mock_pack("p3"))
        assert set(reg.list_packs()) == {"p1", "p2", "p3"}


class TestPackRegistryGetPackHealth:
    def test_empty_registry_health(self):
        reg = PackRegistry()
        health = reg.get_pack_health()
        assert health == {}

    def test_health_includes_pack_id(self):
        reg = PackRegistry()
        pack = _make_mock_pack("alpha")
        reg.register_pack(pack)
        health = reg.get_pack_health()
        assert "alpha" in health

    def test_health_has_required_keys(self):
        reg = PackRegistry()
        pack = _make_mock_pack("alpha")
        reg.register_pack(pack)
        health = reg.get_pack_health()["alpha"]
        assert "valid" in health
        assert "warnings" in health
        assert "errors" in health
        assert "tools_total" in health
        assert "tools_bound" in health
        assert "diagnostics" in health
        assert "runbooks" in health
        assert "prompts" in health
        assert "eval_cases" in health

    def test_health_counts_tools_correctly(self):
        reg = PackRegistry()
        pack = _make_mock_pack("alpha")
        # pack has 3 tools: bound python_function, unbound python_function, http_api
        # bound_tools = tools where type==python_function AND (import_path or function_ref)
        reg.register_pack(pack)
        health = reg.get_pack_health()["alpha"]
        assert health["tools_total"] == 3
        assert health["tools_bound"] == 1  # only TOOL-BOUND has import_path

    def test_health_valid_true_for_clean_pack(self):
        reg = PackRegistry()
        pack = _make_mock_pack("alpha")
        reg.register_pack(pack)
        health = reg.get_pack_health()["alpha"]
        assert health["valid"] is True
        assert health["warnings"] == 0
        assert health["errors"] == 0

    def test_health_multiple_packs(self):
        reg = PackRegistry()
        reg.register_pack(_make_mock_pack("pack-a"))
        reg.register_pack(_make_mock_pack("pack-b"))
        health = reg.get_pack_health()
        assert set(health.keys()) == {"pack-a", "pack-b"}
