"""Build the A2A AgentCard from the loaded pack registry.

Each pack produces an *umbrella* :class:`a2a.types.AgentSkill` (``id =
pack_id``) and, optionally, one extra skill per tool in
``tools.yaml`` that sets ``expose_as_skill: true`` (``id =
"<pack_id>.<tool_id>"``).  Callers select the target by sending
``metadata.agent_id`` (pack id) or ``metadata.skill_id`` (either
form); the executor falls back to the registry's default pack when
neither is supplied.
"""
from __future__ import annotations

from typing import Any

from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentProvider,
    AgentSkill,
)

from agent_factory.common.logging import get_logger
from agent_factory.infrastructure.settings import get_config
from agent_factory.registry import pack_registry

logger = get_logger("agent_factory_api.a2a.agent_card")


# A2A v0.3 is the only protocol version the pinned SDK speaks.
_PROTOCOL_VERSION = "0.3.0"

# Cap on auto-derived example prompts to keep the card payload small.
_MAX_AUTO_EXAMPLES = 3


def _config_get(config: Any, key: str, default: str = "") -> str:
    """Tolerant config getter — Dynaconf exposes both attribute and dict
    access; this helper returns ``default`` when the key is unset."""
    try:
        val = config.get(key, default)  # type: ignore[attr-defined]
    except Exception:
        val = getattr(config, key, default)
    return str(val) if val is not None else default


def _dedupe(values: list[str]) -> list[str]:
    """Order-preserving dedupe; drops empties and whitespace-only entries."""
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        s = (v or "").strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def _umbrella_examples(cfg: Any, display_name: str) -> list[str]:
    """Pick the best available example prompts for a pack's umbrella skill.

    Priority: ``pack.examples`` → symptom keywords from
    ``triage_extraction.symptom_rules`` → generic placeholders.
    """
    curated = _dedupe(list(getattr(cfg, "examples", []) or []))
    if curated:
        return curated[:_MAX_AUTO_EXAMPLES]

    rules = getattr(getattr(cfg, "triage_extraction", None), "symptom_rules", []) or []
    derived: list[str] = []
    for rule in rules:
        for kw in getattr(rule, "keywords", []) or []:
            derived.append(str(kw))
            if len(derived) >= _MAX_AUTO_EXAMPLES:
                break
        if len(derived) >= _MAX_AUTO_EXAMPLES:
            break
    derived = _dedupe(derived)
    if derived:
        return derived

    return [f"Ask {display_name} a question.", f"What can {display_name} help with?"]


def _umbrella_skill(pack) -> AgentSkill:
    """Render the pack-level umbrella skill (the chat entry point)."""
    cfg = pack.config
    display_name = (cfg.name or pack.pack_id).strip()
    description = (cfg.description or f"Pack '{pack.pack_id}'.").strip()
    extra_tags = list(getattr(cfg, "tags", []) or [])
    tags = _dedupe([pack.pack_id, "chat", *extra_tags])
    return AgentSkill(
        id=pack.pack_id,
        name=display_name,
        description=description,
        tags=tags,
        examples=_umbrella_examples(cfg, display_name),
        input_modes=["text"],
        output_modes=["text"],
    )


def _tool_skills(pack) -> list[AgentSkill]:
    """Render one :class:`AgentSkill` per opted-in tool.

    A tool opts in via ``expose_as_skill: true`` in ``tools.yaml``.
    The display name falls back to ``pack.config.display.tool_names``
    and finally to the raw tool id.
    """
    manifest = getattr(pack, "tools_manifest", None)
    if manifest is None:
        return []
    tool_names = dict(getattr(pack.config.display, "tool_names", {}) or {})
    skills: list[AgentSkill] = []
    for tool in getattr(manifest, "tools", []) or []:
        if not getattr(tool, "expose_as_skill", False):
            continue
        tool_id = (tool.id or "").strip()
        if not tool_id:
            continue
        # ``display.tool_names`` is keyed by the normalized form
        # (lowercase, underscored), matching the convention used in
        # tool wrappers and outcome rules.
        normalized = tool_id.replace("-", "_").lower()
        name = (tool_names.get(normalized) or tool_id).strip()
        description = (tool.description or name).strip()
        tags = _dedupe([
            pack.pack_id,
            tool.type or "tool",
            *list(getattr(tool, "skill_tags", []) or []),
        ])
        examples = _dedupe(list(getattr(tool, "skill_examples", []) or []))
        skills.append(
            AgentSkill(
                id=f"{pack.pack_id}.{tool_id}",
                name=name,
                description=description,
                tags=tags,
                examples=examples,
                input_modes=["text"],
                output_modes=["text"],
            )
        )
    return skills


def build_agent_card() -> AgentCard:
    """Build the AgentCard advertising every loaded pack as a skill.

    Must be called after :meth:`pack_registry.discover_and_load_all` so
    the skill list reflects the live registry.
    """
    config = get_config()

    agent_name = _config_get(config, "A2A_AGENT_NAME") or _config_get(
        config, "AGENT_NAME", "matbot-agent-factory"
    )
    agent_version = _config_get(config, "A2A_AGENT_VERSION", "1.0.0")
    agent_description = _config_get(
        config,
        "A2A_AGENT_DESCRIPTION",
        "Matbot multi-agent runtime — chat over any loaded pack.",
    )
    base_url = _config_get(config, "A2A_BASE_URL", "http://localhost:8000")
    streaming_enabled = bool(config.get("A2A_STREAMING_ENABLED", True))  # type: ignore[attr-defined]

    skills: list[AgentSkill] = []
    for pack_id in pack_registry.list_packs():
        pack = pack_registry.get_pack(pack_id)
        if pack is None:
            continue
        try:
            skills.append(_umbrella_skill(pack))
            skills.extend(_tool_skills(pack))
        except Exception as exc:
            logger.warning("AgentCard: skipping pack '%s' (%s)", pack_id, exc)

    if not skills:
        # Service is up but no pack loaded — advertise a single placeholder
        # so the AgentCard is still A2A-valid.
        skills.append(
            AgentSkill(
                id="default",
                name="Matbot Chat",
                description="Default chat skill (no pack loaded).",
                tags=["chat"],
                examples=["Hello"],
                input_modes=["text"],
                output_modes=["text"],
            )
        )

    capabilities = AgentCapabilities(
        streaming=streaming_enabled,
        push_notifications=False,
    )

    provider = AgentProvider(
        organization="Walmart",
        url="https://walmart.com",
    )

    card = AgentCard(
        name=agent_name,
        description=agent_description,
        version=agent_version,
        url=f"{base_url.rstrip('/')}/a2a",
        protocol_version=_PROTOCOL_VERSION,
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=capabilities,
        skills=skills,
        provider=provider,
    )
    logger.info(
        "AgentCard built: name=%s version=%s skills=%d streaming=%s",
        agent_name, agent_version, len(skills), streaming_enabled,
    )
    return card
