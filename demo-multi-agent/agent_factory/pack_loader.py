"""Pack Loader — validates and loads an SOP Pack from disk."""
from __future__ import annotations

import importlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import yaml

from agent_factory.common.logging import get_logger
from agent_factory.infrastructure.settings import get_config
from .ir.models import SOPIR
from .pack_models import PackConfig, ToolsManifest, PolicyConfig
logger = get_logger("pack_loader")

_REQUIRED_FILES = ["pack.yaml", "sop-ir.json", "tools.yaml", "policy.yaml"]
_OPTIONAL_FILES = ["eval_cases.json", "secrets.toml"]
_PACK_SECRETS_FILE = "secrets.toml"


@dataclass
class PackValidationResult:
    """Outcome of pack validation."""
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.valid = False

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)


@dataclass
class AgentPack:
    """A fully-loaded SOP Pack ready for the runtime."""
    pack_id: str
    pack_dir: Path
    config: PackConfig
    sop_ir: SOPIR
    tools_manifest: ToolsManifest
    policy: PolicyConfig
    eval_cases: list[dict[str, Any]] = field(default_factory=list)
    prompts: dict[str, str] = field(default_factory=dict)
    validation: PackValidationResult = field(default_factory=PackValidationResult)
    graph_builder: Optional[Callable[..., Any]] = None
    state_schema: Optional[type] = None
    state_factory: Optional[Callable[..., Any]] = None


def _resolve_entry_point(
    ref: str,
    *,
    pack_id: str,
    field_name: str,
    validation: PackValidationResult,
) -> Optional[Callable[..., Any]]:
    """Resolve a ``"<module>:<attribute>"`` callable entry-point.

    Returns the callable, or ``None`` when ``ref`` is empty or resolution
    fails (failure is recorded as a validation warning so the pack still loads).
    """
    if not ref:
        return None

    module_path, _, attr = ref.partition(":")
    try:
        module = importlib.import_module(module_path)
    except Exception as exc:
        validation.add_warning(
            f"runtime.{field_name}: cannot import '{module_path}' "
            f"({exc.__class__.__name__}: {exc})"
        )
        return None

    target = getattr(module, attr, None)
    if target is None:
        validation.add_warning(
            f"runtime.{field_name}: module '{module_path}' has no attribute '{attr}'"
        )
        return None

    if not callable(target):
        validation.add_warning(
            f"runtime.{field_name}: '{ref}' is not callable ({type(target).__name__})"
        )
        return None

    logger.debug("[pack:%s] runtime.%s resolved → %s", pack_id, field_name, ref)
    return target


def _resolve_state_schema(
    ref: str,
    *,
    pack_id: str,
    validation: PackValidationResult,
) -> Optional[type]:
    """Resolve a ``"<module>:<class>"`` reference to a TypedDict subclass.

    Returns the class, or ``None`` when ``ref`` is empty or resolution fails.
    """
    if not ref:
        return None

    module_path, _, attr = ref.partition(":")
    try:
        module = importlib.import_module(module_path)
    except Exception as exc:
        validation.add_warning(
            f"runtime.state_schema: cannot import '{module_path}' "
            f"({exc.__class__.__name__}: {exc})"
        )
        return None

    target = getattr(module, attr, None)
    if target is None:
        validation.add_warning(
            f"runtime.state_schema: module '{module_path}' has no attribute '{attr}'"
        )
        return None

    if not isinstance(target, type):
        validation.add_warning(
            f"runtime.state_schema: '{ref}' is not a class ({type(target).__name__})"
        )
        return None

    logger.debug("[pack:%s] runtime.state_schema resolved → %s", pack_id, ref)
    return target


def _read_yaml(path: Path) -> dict:
    """Read and parse a YAML file."""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _read_json(path: Path) -> Any:
    """Read and parse a JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _merge_pack_secrets(pack_id: str, pack_dir: Path) -> None:
    """Merge ``packs/<pack_id>/secrets.toml`` into the active Dynaconf config.

    The framework reads secrets from two flat ``[default.<section>]`` TOML
    files — the common file under ``agent_factory/infrastructure/`` and a
    per-pack file alongside ``pack.yaml``.  When a pack ships its own
    secrets file, it is loaded into the same Dynaconf instance returned
    by :func:`get_config`, so pack code can read ``config.<section>.<key>``
    identically whether the section came from the common file or the
    pack file.

    Best-effort: a missing file is a silent no-op (most packs won't ship
    one); a malformed file logs a warning and is skipped so the rest of
    pack load still completes.
    """
    secrets_path = pack_dir / _PACK_SECRETS_FILE
    if not secrets_path.exists():
        return

    try:
        config = get_config()
        config.load_file(path=str(secrets_path))
        logger.info(
            "[pack:%s] merged pack secrets from %s", pack_id, secrets_path.name,
        )
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning(
            "[pack:%s] failed to merge %s: %s (%s)",
            pack_id,
            secrets_path.name,
            exc.__class__.__name__,
            exc,
        )


def _load_prompts(pack_dir: Path) -> dict[str, str]:
    """Load all prompt files from the prompts/ subdirectory.

    Supported extensions:
      - ``.txt``, ``.md``, ``.prompt`` — plain-text prompts (returned as-is).
      - ``.j2``                        — Jinja2 templates (rendered at build
        time by :mod:`agent_factory.prompts`).

    All files are stored as raw strings under their stem (filename without
    extension).  If both ``triage.txt`` and ``triage.j2`` exist, ``.j2``
    takes precedence (it is loaded last in sorted order and overwrites the
    plain-text entry).
    """
    prompts_dir = pack_dir / "prompts"
    prompts: dict[str, str] = {}
    if not prompts_dir.is_dir():
        return prompts

    for prompt_file in sorted(prompts_dir.iterdir()):
        if prompt_file.suffix in (".txt", ".md", ".prompt", ".j2"):
            key = prompt_file.stem  # e.g., "triage" from "triage.txt"
            prompts[key] = prompt_file.read_text(encoding="utf-8")

    return prompts


def _validate_tool_refs(
    sop_ir: SOPIR,
    tools_manifest: ToolsManifest,
    validation: PackValidationResult,
) -> None:
    """Cross-reference tool IDs between SOP-IR and tools.yaml."""
    manifest_ids = {t.id for t in tools_manifest.tools}

    # Check diagnostics reference valid tools
    for diag in sop_ir.diagnostics:
        if diag.id not in manifest_ids:
            validation.add_warning(
                f"Diagnostic '{diag.id}' not found in tools.yaml — "
                f"it may not be executable at runtime"
            )

    # Check runbook actions reference valid tools
    for rb in sop_ir.runbooks:
        for action in rb.actions:
            if action.tool_id and action.tool_id not in manifest_ids:
                validation.add_warning(
                    f"Runbook '{rb.id}' action '{action.id}' references tool "
                    f"'{action.tool_id}' not found in tools.yaml"
                )

    # Check guardrail tool references
    for tool_id in sop_ir.guardrails.approvals.required_for_tools:
        if tool_id not in manifest_ids:
            validation.add_warning(
                f"Guardrail approval tool '{tool_id}' not in tools.yaml"
            )


def _validate_tool_bindings(
    tools_manifest: ToolsManifest,
    validation: PackValidationResult,
) -> None:
    """Check that python_function tools have importable bindings."""
    for tool in tools_manifest.tools:
        if tool.type == "python_function":
            import_path = tool.import_path or tool.function_ref
            if not import_path:
                validation.add_warning(
                    f"Tool '{tool.id}' (python_function) has no import path — "
                    f"it will not be executable"
                )
        elif tool.type == "http_api":
            if not tool.url_template:
                validation.add_warning(
                    f"Tool '{tool.id}' (http_api) has no url_template"
                )
        elif tool.type == "sql_query":
            if not tool.query_template:
                validation.add_warning(
                    f"Tool '{tool.id}' (sql_query) has no query_template"
                )
        elif tool.type == "bigquery_query":
            if not tool.query_template:
                validation.add_warning(
                    f"Tool '{tool.id}' (bigquery_query) has no query_template"
                )


def load_pack(
    pack_id: str,
    packs_root: str = "packs",
) -> AgentPack:
    """Load and validate an SOP Pack from disk.

    Raises FileNotFoundError if the pack directory is missing,
    ValueError if required files are absent or schema validation fails.
    """
    root = Path(packs_root)
    if not root.is_absolute():
        root = Path(os.getcwd()) / root
    pack_dir = root / pack_id

    if not pack_dir.is_dir():
        raise FileNotFoundError(f"Pack directory not found: {pack_dir}")

    validation = PackValidationResult()

    for fname in _REQUIRED_FILES:
        if not (pack_dir / fname).exists():
            validation.add_error(f"Required file missing: {fname}")

    if not validation.valid:
        logger.error(f"Pack '{pack_id}' missing required files: {validation.errors}")
        raise ValueError(f"Pack '{pack_id}' is invalid: {'; '.join(validation.errors)}")

    try:
        raw_pack = _read_yaml(pack_dir / "pack.yaml")
        pack_config = PackConfig(**raw_pack)
    except Exception as e:
        raise ValueError(f"Invalid pack.yaml for '{pack_id}': {e}") from e

    try:
        raw_ir = _read_json(pack_dir / "sop-ir.json")
        sop_ir = SOPIR(**raw_ir)
    except Exception as e:
        raise ValueError(f"Invalid sop-ir.json for '{pack_id}': {e}") from e

    try:
        raw_tools = _read_yaml(pack_dir / "tools.yaml")
        tools_manifest = ToolsManifest(**raw_tools)
    except Exception as e:
        raise ValueError(f"Invalid tools.yaml for '{pack_id}': {e}") from e

    try:
        raw_policy = _read_yaml(pack_dir / "policy.yaml")
        policy = PolicyConfig(**raw_policy)
    except Exception as e:
        raise ValueError(f"Invalid policy.yaml for '{pack_id}': {e}") from e

    eval_cases: list[dict] = []
    eval_path = pack_dir / "eval_cases.json"
    if eval_path.exists():
        try:
            eval_cases = _read_json(eval_path)
        except Exception as e:
            validation.add_warning(f"Could not parse eval_cases.json: {e}")

    prompts = _load_prompts(pack_dir)
    _merge_pack_secrets(pack_id, pack_dir)
    _validate_tool_refs(sop_ir, tools_manifest, validation)
    _validate_tool_bindings(tools_manifest, validation)

    # ── Resolve runtime entry points ─────────────────────────────────
    graph_builder = _resolve_entry_point(
        pack_config.runtime.graph_builder,
        pack_id=pack_id,
        field_name="graph_builder",
        validation=validation,
    )
    state_schema = _resolve_state_schema(
        pack_config.runtime.state_schema,
        pack_id=pack_id,
        validation=validation,
    )
    state_factory = _resolve_entry_point(
        pack_config.runtime.state_factory,
        pack_id=pack_id,
        field_name="state_factory",
        validation=validation,
    )

    # Log warnings
    for w in validation.warnings:
        logger.warning(f"[pack:{pack_id}] {w}")

    if validation.errors:
        for e in validation.errors:
            logger.error(f"[pack:{pack_id}] {e}")

    pack = AgentPack(
        pack_id=pack_id,
        pack_dir=pack_dir,
        config=pack_config,
        sop_ir=sop_ir,
        tools_manifest=tools_manifest,
        policy=policy,
        eval_cases=eval_cases,
        prompts=prompts,
        validation=validation,
        graph_builder=graph_builder,
        state_schema=state_schema,
        state_factory=state_factory,
    )

    logger.info(
        f"Pack '{pack_id}' loaded: "
        f"{len(tools_manifest.tools)} tools, "
        f"{len(sop_ir.diagnostics)} diagnostics, "
        f"{len(sop_ir.runbooks)} runbooks, "
        f"{len(prompts)} prompts, "
        f"{len(eval_cases)} eval cases, "
        f"{len(validation.warnings)} warnings"
    )

    return pack
