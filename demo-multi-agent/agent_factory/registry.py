"""Pack Registry — holds loaded packs and provides lookup.

The registry is the central place where the runtime resolves which
pack to use for a given request.  At startup the runtime can either:

  * load *one* pack by ID — :meth:`PackRegistry.initialize`, used by
    single-pack deployments;
  * or **discover and load every pack** under the packs root —
    :meth:`PackRegistry.discover_and_load_all`, used by the factory
    monorepo's multi-pack flow.

The default pack ID drives :meth:`get_pack(None)` lookups so
single-pack callers work after multi-pack startup.

Usage::

    from agent_factory.registry import pack_registry
    pack_registry.discover_and_load_all(packs_root="packs")
    pack = pack_registry.get_pack()             # default pack
    pack = pack_registry.get_pack("my_domain")  # explicit
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from agent_factory.common.logging import get_logger
from .pack_loader import AgentPack, load_pack

logger = get_logger("pack_registry")

# Pack IDs must match the documented rule in ``packs/_example/pack.yaml``:
# lowercase alphanumeric + underscores, starting with a letter.  Exposed
# as a public symbol so HTTP-boundary validators (Pydantic field
# validators, route guards) can enforce the same shape on caller-supplied
# pack ids before they flow into the registry.
PACK_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")

# Private alias retained for internal call sites.
_PACK_ID_PATTERN = PACK_ID_PATTERN


def _resolve_default_pack_id() -> str:
    """Read ``DEFAULT_PACK_ID`` from the environment each call.

    Re-read on every call so operators and tests that flip the env var
    after module import still see the updated value at discovery time.

    The value is gated through :data:`PACK_ID_PATTERN` — anything that
    isn't a well-formed pack id (lowercase alphanumeric + underscores,
    starting with a letter) is rejected and replaced with the
    ``"_example"`` placeholder.  That placeholder is filtered out at
    discovery as a private name, so a malformed env value degrades to
    "no default" instead of flowing into ``load_pack`` as raw operator
    input.  Mirrors the validation gate the ``PACK_ID`` env var
    already receives.
    """
    raw = os.environ.get("DEFAULT_PACK_ID", "")
    if raw and PACK_ID_PATTERN.match(raw):
        return raw
    return "_example"


# Kept for backward compatibility — callers that imported the constant
# directly still see the value captured at process start.  Internal
# code should call :func:`_resolve_default_pack_id` instead.
DEFAULT_PACK_ID = _resolve_default_pack_id()


class PackRegistry:
    """In-memory registry of loaded SOP Packs."""

    def __init__(self) -> None:
        # NOTE: this registry is built for startup-time loading on a
        # single FastAPI worker.  ``_initialized`` is NOT lock-guarded
        # — the contract is that discovery runs once, before the event
        # loop starts serving requests.  Hot-reload calls
        # ``discover_and_load_all(..., force=True)`` from the same
        # thread.  Don't bolt threading on without revisiting this.
        self._packs: dict[str, AgentPack] = {}
        self._default_pack_id: str = _resolve_default_pack_id()
        self._initialized: bool = False

    @property
    def initialized(self) -> bool:
        return self._initialized

    @property
    def default_pack_id(self) -> str:
        return self._default_pack_id

    def initialize(self, packs_root: str = "packs") -> None:
        """Load the default pack on startup.

        This is intentionally synchronous because it runs during app
        startup before the event loop serves requests.

        Args:
            packs_root: Path to the packs directory.
        """
        if self._initialized:
            logger.debug("Pack registry already initialized")
            return

        try:
            pack = load_pack(self._default_pack_id, packs_root=packs_root)
            self._packs[pack.pack_id] = pack
            self._initialized = True
            logger.info(
                f"Pack registry initialized with default pack: "
                f"'{self._default_pack_id}'"
            )
        except Exception as e:
            logger.error(
                f"Failed to load default pack '{self._default_pack_id}': {e}"
            )
            # Don't crash the app — degrade gracefully
            self._initialized = True  # Mark as initialized to avoid retry loops

    def discover_pack_ids(self, packs_root: str = "packs") -> list[str]:
        """Return the IDs of every pack directory under ``packs_root``.

        A directory is considered a pack candidate when it contains a
        ``pack.yaml`` file.  Names starting with ``_`` or ``.`` are
        skipped (``_example`` placeholders, ``__pycache__``,
        ``.DS_Store``, etc.).

        When the ``PACK_ID`` environment variable is set, discovery
        narrows to that single pack — each pod can set ``PACK_ID`` to
        serve only its own pack.  If ``PACK_ID`` is set but the
        directory doesn't exist or has no ``pack.yaml``, discovery logs
        an error and returns ``[]`` — callers can decide whether to fail
        boot or degrade.

        This is a *discovery* helper — it does no schema validation.
        Use :meth:`discover_and_load_all` to actually load packs.

        Args:
            packs_root: directory to scan.  Relative paths are resolved
                against the current working directory, matching the
                behaviour of :func:`load_pack`.

        Returns:
            Alphabetically sorted list of pack IDs.  Empty list when
            the directory does not exist (or when ``PACK_ID`` filters
            to nothing).
        """
        root = Path(packs_root)
        if not root.is_absolute():
            root = Path(os.getcwd()) / root

        if not root.is_dir():
            logger.warning(
                "Pack discovery: packs_root '%s' does not exist", root
            )
            return []

        # ``PACK_ID`` selects a single pack for child-process deployments.
        # We still validate it has a real ``pack.yaml`` so a typo'd
        # PACK_ID surfaces as a clear log line instead of an empty boot.
        pack_id_filter = os.environ.get("PACK_ID", "").strip()
        if pack_id_filter:
            if not _PACK_ID_PATTERN.match(pack_id_filter):
                # Reject anything that isn't a well-formed pack id —
                # avoids echoing operator-controlled payloads into log
                # aggregators and keeps Path traversal off the table.
                logger.error(
                    "Pack discovery: PACK_ID env var is not a valid "
                    "pack id (must match %s); ignoring and returning []",
                    _PACK_ID_PATTERN.pattern,
                )
                return []
            entry = root / pack_id_filter
            if entry.is_dir() and (entry / "pack.yaml").exists():
                logger.info(
                    "Pack discovery: PACK_ID=%s set — loading only that pack",
                    pack_id_filter,
                )
                return [pack_id_filter]
            logger.error(
                "Pack discovery: PACK_ID='%s' does not match any pack "
                "under '%s' (no pack.yaml found)",
                pack_id_filter,
                root,
            )
            return []

        candidates: list[str] = []
        for entry in sorted(root.iterdir()):
            if not entry.is_dir():
                continue
            name = entry.name
            # ``_example`` is the conventional placeholder copied by the
            # SOP normaliser scaffolder; underscore-prefixed and
            # dot-prefixed dirs (``__pycache__``, ``.DS_Store``,
            # ``.cache``) are private filesystem artefacts.  Pack IDs
            # are required to start with an alphanumeric — this is
            # documented in ``packs/_example/pack.yaml``.
            if name.startswith(".") or name.startswith("_"):
                logger.debug(
                    "Pack discovery: skipping '%s' (private name)",
                    name,
                )
                continue
            if not (entry / "pack.yaml").exists():
                logger.debug(
                    "Pack discovery: skipping '%s' (no pack.yaml)", name
                )
                continue
            candidates.append(name)
        return candidates

    def discover_and_load_all(
        self,
        packs_root: str = "packs",
        *,
        force: bool = False,
    ) -> list[str]:
        """Discover every pack under ``packs_root`` and load each one.

        The multi-pack entry point.  Each pack is loaded independently;
        a failure on one pack is logged and skipped — it never
        prevents other packs from loading.

        After discovery the default pack ID is resolved:

          * If ``DEFAULT_PACK_ID`` (env var, captured at module
            import time) is among the loaded packs, it wins.
          * Otherwise the first alphabetically loaded pack becomes
            the default — keeps :meth:`get_pack(None)` working.

        The registry is marked ``initialized`` after this call so
        repeated calls are no-ops unless ``force=True``.

        Args:
            packs_root: directory to scan.
            force: when ``True``, re-runs discovery even if the
                registry is already initialised.  Existing entries
                are overwritten; previously-loaded packs that have
                since been deleted are NOT removed (additive only).

        Returns:
            List of pack IDs that loaded successfully.
        """
        if self._initialized and not force:
            logger.debug("Pack registry already initialized (skipping discovery)")
            return list(self._packs.keys())

        # ``force=True`` should produce the same registry state as a
        # fresh boot.  Clearing first evicts packs that have since been
        # deleted from disk — additive-only behaviour leaked stale
        # entries to ``get_pack`` callers.
        if force:
            self._packs.clear()

        candidate_ids = self.discover_pack_ids(packs_root)
        loaded: list[str] = []
        failed: list[tuple[str, str]] = []

        for pack_id in candidate_ids:
            try:
                pack = load_pack(pack_id, packs_root=packs_root)
                self._packs[pack.pack_id] = pack
                loaded.append(pack.pack_id)
            except Exception as e:
                # ``logger.exception`` keeps the traceback for the
                # operator — discovery failures usually need it.
                logger.exception(
                    "Pack discovery: failed to load '%s'", pack_id
                )
                failed.append((pack_id, str(e)))

        # Resolve effective default pack.  Re-read ``DEFAULT_PACK_ID``
        # from the environment on every call so operators (and tests)
        # who flip the env var after this module first imported still
        # win.  Honour the env value when it points at a
        # successfully-loaded pack; otherwise fall back to the first
        # alphabetically-loaded pack so callers that pass ``None`` to
        # :meth:`get_pack` keep working.
        env_default = _resolve_default_pack_id()
        if env_default in self._packs:
            self._default_pack_id = env_default
        elif loaded:
            new_default = loaded[0]
            if env_default != new_default:
                logger.info(
                    "Pack registry: DEFAULT_PACK_ID='%s' not loaded — "
                    "falling back to '%s' as default",
                    env_default,
                    new_default,
                )
            self._default_pack_id = new_default

        self._initialized = True
        logger.info(
            "Pack registry discovery complete: %d loaded, %d failed "
            "(default='%s')",
            len(loaded),
            len(failed),
            self._default_pack_id,
        )
        return loaded

    def register_pack(self, pack: AgentPack) -> None:
        """Register an already-loaded pack."""
        self._packs[pack.pack_id] = pack
        logger.info(f"Pack '{pack.pack_id}' registered")

    def get_pack(self, pack_id: str | None = None) -> AgentPack | None:
        """Get a loaded pack by ID, or the default pack.

        Args:
            pack_id: Pack ID to look up.  If None, returns the default pack.

        Returns:
            The AgentPack, or None if not found.
        """
        target = pack_id or self._default_pack_id
        pack = self._packs.get(target)
        if pack is None:
            logger.warning(f"Pack '{target}' not found in registry")
        return pack

    def validate_pack_id(self, value: object) -> str | None:
        """Sanitise an externally-supplied pack id against the closed allowlist.

        The contract is "value-from-an-untrusted-source → key drawn from
        the loaded registry, or None".  Callers at the HTTP boundary
        should pass the raw input through this gate before handing the
        value to :meth:`get_pack` or any downstream loader.

        Returns ``None`` when ``value`` is missing, of the wrong type,
        not a well-formed pack id, or not present in the loaded set.
        When the value matches, the returned string is the registry key
        itself (not the caller-supplied buffer) so taint analyzers
        observe the value as drawn from the closed enum.
        """
        if not isinstance(value, str):
            return None
        candidate = value.strip()
        if not candidate or not PACK_ID_PATTERN.match(candidate):
            return None
        for loaded_id in self._packs:
            if loaded_id == candidate:
                return loaded_id
        return None

    def list_packs(self) -> list[str]:
        """Return IDs of all loaded packs."""
        return list(self._packs.keys())

    def get_pack_health(self) -> dict:
        """Return health/status for all loaded packs."""
        result = {}
        for pack_id, pack in self._packs.items():
            v = pack.validation
            bound_tools = sum(
                1
                for t in pack.tools_manifest.tools
                if t.type == "python_function" and (t.import_path or t.function_ref)
            )
            total_tools = len(pack.tools_manifest.tools)
            result[pack_id] = {
                "valid": v.valid,
                "warnings": len(v.warnings),
                "errors": len(v.errors),
                "tools_total": total_tools,
                "tools_bound": bound_tools,
                "diagnostics": len(pack.sop_ir.diagnostics),
                "runbooks": len(pack.sop_ir.runbooks),
                "prompts": len(pack.prompts),
                "eval_cases": len(pack.eval_cases),
            }
        return result


# Module-level singleton
pack_registry = PackRegistry()
