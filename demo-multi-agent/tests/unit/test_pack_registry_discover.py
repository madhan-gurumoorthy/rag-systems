"""Tests for pack-registry discovery and multi-pack loading (Phase B.4).

These cover the new ``discover_pack_ids`` and ``discover_and_load_all``
methods on :class:`agent_factory.registry.PackRegistry`.

Strategy: build temp packs/ directories on disk and let the registry
walk them, rather than mocking the file system.  The pack-loader
itself is patched so we don't need a full SOP-IR fixture for every
candidate — discovery is the unit under test, not loader correctness.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Iterable
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_factory.pack_loader import AgentPack, PackValidationResult
from agent_factory.pack_models import PolicyConfig, ToolsManifest
from agent_factory.registry import PackRegistry


# ── Helpers ────────────────────────────────────────────────────────


def _mk_pack_dir(root: Path, pack_id: str, *, with_yaml: bool = True) -> Path:
    """Create ``root/<pack_id>/`` and optionally drop a stub pack.yaml."""
    pack_dir = root / pack_id
    pack_dir.mkdir(parents=True, exist_ok=True)
    if with_yaml:
        (pack_dir / "pack.yaml").write_text(f"id: {pack_id}\nname: {pack_id}\n")
    return pack_dir


def _mock_pack(pack_id: str) -> MagicMock:
    """Minimal AgentPack stand-in for registry tests."""
    pack = MagicMock(spec=AgentPack)
    pack.pack_id = pack_id
    pack.validation = PackValidationResult()
    pack.prompts = {}
    pack.eval_cases = []
    pack.tools_manifest = ToolsManifest(tools=[])
    pack.sop_ir = MagicMock(diagnostics=[], runbooks=[])
    return pack


# ── discover_pack_ids ──────────────────────────────────────────────


class TestDiscoverPackIds:
    def test_returns_empty_when_root_missing(self, tmp_path: Path):
        """Pointing at a non-existent directory must yield ``[]``."""
        reg = PackRegistry()
        result = reg.discover_pack_ids(str(tmp_path / "does_not_exist"))
        assert result == []

    def test_finds_directories_with_pack_yaml(self, tmp_path: Path):
        """Every directory containing a pack.yaml is a candidate."""
        _mk_pack_dir(tmp_path, "alpha")
        _mk_pack_dir(tmp_path, "beta")
        _mk_pack_dir(tmp_path, "gamma")

        reg = PackRegistry()
        result = reg.discover_pack_ids(str(tmp_path))
        assert result == ["alpha", "beta", "gamma"]

    def test_skips_dirs_without_pack_yaml(self, tmp_path: Path):
        """Directories that don't carry a pack.yaml are silently ignored."""
        _mk_pack_dir(tmp_path, "alpha")
        _mk_pack_dir(tmp_path, "no_yaml", with_yaml=False)

        reg = PackRegistry()
        assert reg.discover_pack_ids(str(tmp_path)) == ["alpha"]

    def test_skips_underscore_prefixed_names(self, tmp_path: Path):
        """Legacy ``_example`` and similar private dirs are excluded."""
        _mk_pack_dir(tmp_path, "alpha")
        _mk_pack_dir(tmp_path, "_example")
        _mk_pack_dir(tmp_path, "__pycache__")

        reg = PackRegistry()
        assert reg.discover_pack_ids(str(tmp_path)) == ["alpha"]

    def test_skips_dot_prefixed_names(self, tmp_path: Path):
        """Hidden directories (e.g. ``.DS_Store`` looks like a file but
        guarding against ``.cache`` dirs is cheap)."""
        _mk_pack_dir(tmp_path, "alpha")
        _mk_pack_dir(tmp_path, ".cache")

        reg = PackRegistry()
        assert reg.discover_pack_ids(str(tmp_path)) == ["alpha"]

    def test_skips_regular_files(self, tmp_path: Path):
        """A stray file at the packs root must not be treated as a pack."""
        _mk_pack_dir(tmp_path, "alpha")
        (tmp_path / "README.md").write_text("hi")

        reg = PackRegistry()
        assert reg.discover_pack_ids(str(tmp_path)) == ["alpha"]

    def test_results_are_sorted(self, tmp_path: Path):
        """Output ordering is deterministic across runs."""
        for name in ("zeta", "alpha", "mu"):
            _mk_pack_dir(tmp_path, name)

        reg = PackRegistry()
        assert reg.discover_pack_ids(str(tmp_path)) == ["alpha", "mu", "zeta"]


# ── PACK_ID env var filter (single-pack child-process deployments) ─


class TestPackIdEnvFilter:
    """Tests for the ``PACK_ID`` env var single-pack filter.

    Phase B.3 deploys one child kitt.yml pod per pack and sets
    ``PACK_ID=<pack_id>`` on each so the pod only loads + serves
    traffic for its own pack.  Discovery honours that filter to keep
    sibling-pack memory footprints out of every pod.
    """

    def test_pack_id_env_filters_to_single_pack(
        self, tmp_path: Path, monkeypatch
    ):
        """When ``PACK_ID`` is set to a real pack, only that pack is
        returned even though siblings are present on disk."""
        _mk_pack_dir(tmp_path, "alpha")
        _mk_pack_dir(tmp_path, "beta")
        _mk_pack_dir(tmp_path, "gamma")

        monkeypatch.setenv("PACK_ID", "beta")
        reg = PackRegistry()
        assert reg.discover_pack_ids(str(tmp_path)) == ["beta"]

    def test_pack_id_env_typo_returns_empty(
        self, tmp_path: Path, monkeypatch
    ):
        """When ``PACK_ID`` points at a non-existent (but
        well-formed) pack id, discovery returns ``[]`` and logs an
        error so a typo'd env var surfaces as a clear log line
        instead of a silent empty boot."""
        _mk_pack_dir(tmp_path, "alpha")

        # ``missing_pack`` passes the pack-id charset guard but has
        # no directory under ``tmp_path`` — exercises the
        # "no pack.yaml found" code path, not the charset reject.
        monkeypatch.setenv("PACK_ID", "missing_pack")
        reg = PackRegistry()

        # The pack_registry logger has ``propagate=False`` (set in
        # agent_factory/common/logging.py), so caplog can't see it.
        # Patch ``logger.error`` directly to verify the diagnostic
        # message renders the offending PACK_ID value.
        with patch("agent_factory.registry.logger.error") as mock_error:
            result = reg.discover_pack_ids(str(tmp_path))

        assert result == []
        assert mock_error.called
        # First positional arg is the format string; check the args
        # we passed contain the typo'd PACK_ID for operator clarity.
        all_args = [
            str(arg)
            for call in mock_error.call_args_list
            for arg in (call.args or ())
        ]
        assert any("missing_pack" in arg for arg in all_args)

    def test_pack_id_env_invalid_charset_rejected(
        self, tmp_path: Path, monkeypatch
    ):
        """A PACK_ID with characters outside the documented charset
        (``^[a-z][a-z0-9_]*$``) is rejected before any filesystem
        access — defence-in-depth against shell-injection payloads
        and Path-traversal attempts.  The error log MUST NOT echo
        the raw operator-supplied value verbatim."""
        _mk_pack_dir(tmp_path, "alpha")

        # Shell-injection-shaped payload — wouldn't reach the disk
        # anyway (is_dir() returns False), but echoing it into a log
        # aggregator is sloppy.  The guard rejects it first.
        monkeypatch.setenv("PACK_ID", "alpha; rm -rf /")
        reg = PackRegistry()

        with patch("agent_factory.registry.logger.error") as mock_error:
            result = reg.discover_pack_ids(str(tmp_path))

        assert result == []
        assert mock_error.called
        # The raw payload must NOT appear in any log argument — the
        # guard logs the pattern, not the offending value.
        all_args = [
            str(arg)
            for call in mock_error.call_args_list
            for arg in (call.args or ())
        ]
        assert not any("rm -rf" in arg for arg in all_args)

    def test_pack_id_env_uppercase_rejected(
        self, tmp_path: Path, monkeypatch
    ):
        """Pack IDs must start with a lowercase letter — uppercase
        PACK_ID is treated as invalid even though the filesystem on
        macOS would happily case-insensitively match."""
        _mk_pack_dir(tmp_path, "alpha")

        monkeypatch.setenv("PACK_ID", "Alpha")
        reg = PackRegistry()
        assert reg.discover_pack_ids(str(tmp_path)) == []

    def test_pack_id_env_dir_without_pack_yaml_returns_empty(
        self, tmp_path: Path, monkeypatch
    ):
        """A ``PACK_ID`` whose dir exists but has no ``pack.yaml`` is
        treated the same as a typo — no half-loaded packs."""
        _mk_pack_dir(tmp_path, "alpha")
        _mk_pack_dir(tmp_path, "broken", with_yaml=False)

        monkeypatch.setenv("PACK_ID", "broken")
        reg = PackRegistry()
        assert reg.discover_pack_ids(str(tmp_path)) == []

    def test_pack_id_env_empty_string_disables_filter(
        self, tmp_path: Path, monkeypatch
    ):
        """An empty ``PACK_ID`` (set but blank) must NOT collapse
        discovery to nothing — normal multi-pack discovery applies."""
        _mk_pack_dir(tmp_path, "alpha")
        _mk_pack_dir(tmp_path, "beta")

        monkeypatch.setenv("PACK_ID", "")
        reg = PackRegistry()
        assert reg.discover_pack_ids(str(tmp_path)) == ["alpha", "beta"]

    def test_pack_id_env_whitespace_only_disables_filter(
        self, tmp_path: Path, monkeypatch
    ):
        """Whitespace-only ``PACK_ID`` is stripped to empty and the
        filter is bypassed (operator-fat-finger guard)."""
        _mk_pack_dir(tmp_path, "alpha")
        _mk_pack_dir(tmp_path, "beta")

        monkeypatch.setenv("PACK_ID", "   ")
        reg = PackRegistry()
        assert reg.discover_pack_ids(str(tmp_path)) == ["alpha", "beta"]

    def test_pack_id_env_unset_is_normal_discovery(
        self, tmp_path: Path, monkeypatch
    ):
        """When ``PACK_ID`` is unset, discovery returns every candidate
        — verifies the filter doesn't leak when the env var is missing."""
        _mk_pack_dir(tmp_path, "alpha")
        _mk_pack_dir(tmp_path, "beta")

        monkeypatch.delenv("PACK_ID", raising=False)
        reg = PackRegistry()
        assert reg.discover_pack_ids(str(tmp_path)) == ["alpha", "beta"]

    def test_pack_id_env_filter_flows_through_discover_and_load_all(
        self, tmp_path: Path, monkeypatch
    ):
        """The filter narrows ``discover_and_load_all`` to the single
        pack — the load loop should only see one candidate even when
        the disk has multiple."""
        _mk_pack_dir(tmp_path, "alpha")
        _mk_pack_dir(tmp_path, "beta")
        _mk_pack_dir(tmp_path, "gamma")

        monkeypatch.setenv("PACK_ID", "gamma")
        reg = PackRegistry()
        with patch(
            "agent_factory.registry.load_pack",
            side_effect=lambda pid, packs_root: _mock_pack(pid),
        ) as mock_load:
            loaded = reg.discover_and_load_all(str(tmp_path))

        assert loaded == ["gamma"]
        assert set(reg.list_packs()) == {"gamma"}
        # The loader was called for ``gamma`` only — siblings on disk
        # never touched.
        assert mock_load.call_count == 1
        mock_load.assert_called_once_with("gamma", packs_root=str(tmp_path))


# ── discover_and_load_all ──────────────────────────────────────────


class TestDiscoverAndLoadAll:
    def test_loads_every_discovered_pack(self, tmp_path: Path):
        """All packs with a pack.yaml must be loaded and registered."""
        _mk_pack_dir(tmp_path, "alpha")
        _mk_pack_dir(tmp_path, "beta")

        reg = PackRegistry()
        with patch(
            "agent_factory.registry.load_pack",
            side_effect=lambda pid, packs_root: _mock_pack(pid),
        ) as mock_load:
            loaded = reg.discover_and_load_all(str(tmp_path))

        assert set(loaded) == {"alpha", "beta"}
        assert set(reg.list_packs()) == {"alpha", "beta"}
        assert reg.initialized is True
        # load_pack called exactly once per candidate.
        assert mock_load.call_count == 2

    def test_continues_on_individual_load_failure(self, tmp_path: Path):
        """A single broken pack does not block siblings from loading."""
        _mk_pack_dir(tmp_path, "alpha")
        _mk_pack_dir(tmp_path, "broken")
        _mk_pack_dir(tmp_path, "gamma")

        def _loader(pid, packs_root):
            if pid == "broken":
                raise ValueError("broken on purpose")
            return _mock_pack(pid)

        reg = PackRegistry()
        with patch("agent_factory.registry.load_pack", side_effect=_loader):
            loaded = reg.discover_and_load_all(str(tmp_path))

        assert set(loaded) == {"alpha", "gamma"}
        assert "broken" not in reg.list_packs()
        assert reg.initialized is True

    def test_default_pack_falls_back_to_first_loaded(self, tmp_path: Path):
        """When ``DEFAULT_PACK_ID`` is not among the loaded packs the
        registry must promote the first loaded pack so
        :meth:`get_pack(None)` keeps returning something useful."""
        _mk_pack_dir(tmp_path, "alpha")
        _mk_pack_dir(tmp_path, "beta")

        reg = PackRegistry()
        # Force a default that won't be discovered.
        reg._default_pack_id = "missing-default"

        with patch(
            "agent_factory.registry.load_pack",
            side_effect=lambda pid, packs_root: _mock_pack(pid),
        ):
            reg.discover_and_load_all(str(tmp_path))

        assert reg.default_pack_id == "alpha"
        assert reg.get_pack() is reg.get_pack("alpha")

    def test_default_pack_kept_when_loaded(self, tmp_path: Path, monkeypatch):
        """If ``DEFAULT_PACK_ID`` points at a loaded pack, the default
        stays at the env-var value (not the alphabetical first)."""
        _mk_pack_dir(tmp_path, "alpha")
        _mk_pack_dir(tmp_path, "beta")

        monkeypatch.setenv("DEFAULT_PACK_ID", "beta")
        reg = PackRegistry()

        with patch(
            "agent_factory.registry.load_pack",
            side_effect=lambda pid, packs_root: _mock_pack(pid),
        ):
            reg.discover_and_load_all(str(tmp_path))

        assert reg.default_pack_id == "beta"
        assert reg.get_pack() is reg.get_pack("beta")

    def test_idempotent_by_default(self, tmp_path: Path):
        """Repeated calls without ``force`` must be no-ops and leave
        the loaded-pack set unchanged."""
        _mk_pack_dir(tmp_path, "alpha")

        reg = PackRegistry()
        with patch(
            "agent_factory.registry.load_pack",
            side_effect=lambda pid, packs_root: _mock_pack(pid),
        ) as mock_load:
            reg.discover_and_load_all(str(tmp_path))
            snapshot = sorted(reg.list_packs())
            reg.discover_and_load_all(str(tmp_path))

        assert mock_load.call_count == 1
        assert sorted(reg.list_packs()) == snapshot

    def test_force_reruns_discovery(self, tmp_path: Path):
        """``force=True`` must re-run discovery even after initialisation."""
        _mk_pack_dir(tmp_path, "alpha")

        reg = PackRegistry()
        with patch(
            "agent_factory.registry.load_pack",
            side_effect=lambda pid, packs_root: _mock_pack(pid),
        ) as mock_load:
            reg.discover_and_load_all(str(tmp_path))
            reg.discover_and_load_all(str(tmp_path), force=True)

        assert mock_load.call_count == 2

    def test_force_evicts_deleted_packs(self, tmp_path: Path):
        """``force=True`` must drop packs that have disappeared from
        disk between the first and second discovery — additive-only
        semantics leak stale entries to ``get_pack`` callers."""
        _mk_pack_dir(tmp_path, "alpha")
        _mk_pack_dir(tmp_path, "beta")

        reg = PackRegistry()
        with patch(
            "agent_factory.registry.load_pack",
            side_effect=lambda pid, packs_root: _mock_pack(pid),
        ):
            reg.discover_and_load_all(str(tmp_path))
            assert set(reg.list_packs()) == {"alpha", "beta"}

            # Simulate ``beta`` being removed from disk.
            import shutil

            shutil.rmtree(tmp_path / "beta")
            reg.discover_and_load_all(str(tmp_path), force=True)

        assert set(reg.list_packs()) == {"alpha"}
        assert reg.get_pack("beta") is None

    def test_env_var_default_resolved_at_call_time(
        self, tmp_path: Path, monkeypatch
    ):
        """``DEFAULT_PACK_ID`` set after module import must still win
        — captured-at-import-time semantics were surprising."""
        _mk_pack_dir(tmp_path, "alpha")
        _mk_pack_dir(tmp_path, "beta")

        monkeypatch.setenv("DEFAULT_PACK_ID", "beta")
        reg = PackRegistry()  # new instance reads the patched env
        with patch(
            "agent_factory.registry.load_pack",
            side_effect=lambda pid, packs_root: _mock_pack(pid),
        ):
            reg.discover_and_load_all(str(tmp_path))

        assert reg.default_pack_id == "beta"

    def test_env_var_default_re_resolved_on_force(
        self, tmp_path: Path, monkeypatch
    ):
        """When the env var flips between two ``discover_and_load_all``
        calls, the second (with ``force``) must pick up the new value."""
        _mk_pack_dir(tmp_path, "alpha")
        _mk_pack_dir(tmp_path, "beta")

        monkeypatch.setenv("DEFAULT_PACK_ID", "alpha")
        reg = PackRegistry()
        with patch(
            "agent_factory.registry.load_pack",
            side_effect=lambda pid, packs_root: _mock_pack(pid),
        ):
            reg.discover_and_load_all(str(tmp_path))
            assert reg.default_pack_id == "alpha"

            monkeypatch.setenv("DEFAULT_PACK_ID", "beta")
            reg.discover_and_load_all(str(tmp_path), force=True)

        assert reg.default_pack_id == "beta"

    def test_no_default_promotion_when_nothing_loaded(self, tmp_path: Path):
        """Discovery against an empty directory must NOT clobber the
        configured default pack id."""
        reg = PackRegistry()
        original_default = reg.default_pack_id

        loaded = reg.discover_and_load_all(str(tmp_path))

        assert loaded == []
        assert reg.default_pack_id == original_default
        assert reg.initialized is True


# ── Integration with real packs/ directory ────────────────────────


class TestRealPacksDirectoryIntegration:
    """Sanity checks that run against the real ``packs/`` tree.

    These don't mock the loader — they prove the discovery + load
    pipeline works end-to-end with the packs that actually ship in
    this repo (currently ``gif_tote_validation`` and
    ``devops_health_check``).
    """

    def test_real_packs_directory_loads_both_packs(self):
        """Running discovery against the real packs/ directory must
        load both shipped packs cleanly."""
        reg = PackRegistry()
        loaded = reg.discover_and_load_all(packs_root="packs")

        # Both shipped packs must load — the test directly proves the
        # substrate is genuinely multi-pack.
        assert "gif_tote_validation" in loaded
        assert "devops_health_check" in loaded
        assert reg.initialized is True

        # Health snapshot must include both.
        health = reg.get_pack_health()
        assert "gif_tote_validation" in health
        assert "devops_health_check" in health
        # Toy pack still loads with zero warnings/errors.
        toy_health = health["devops_health_check"]
        assert toy_health["valid"] is True
        assert toy_health["errors"] == 0
