"""Prompt rendering — Jinja2 template support for SOP Pack prompts.

Plain-text prompts (.txt, .md, .prompt) are returned unchanged.
Jinja2 templates (.j2) are rendered with a safe, static pack context
derived from the loaded pack's configuration and SOP-IR data.

Design decisions
----------------
* **Backward compatible** — plain-text files with no Jinja2 syntax pass through
  the renderer unchanged; existing packs require zero migration work.
* **Opt-in** — pack authors add Jinja2 syntax to gain dynamic content;
  there is no requirement to adopt it.
* **SandboxedEnvironment** — Jinja2's sandbox disallows attribute / item access
  to Python internals and prevents arbitrary code execution inside templates.
* **DebugUndefined** — references to unknown variables render as
  ``{{ variable_name }}`` rather than raising ``UndefinedError``.  This means
  prompts that accidentally contain ``{{ }}`` sequences in code examples still
  survive rendering without crashing the build pipeline.
* **Static context only** — the template context is built exclusively from
  pack-level configuration and SOP-IR data.  User-supplied request content is
  **never** passed into a template, eliminating prompt-injection risk at the
  template engine level.

Usage
-----
The builder calls :func:`render_prompt` once per agent per request::

    from agent_factory.prompts import render_prompt, build_pack_context

    raw = pack.prompts["triage"]          # loaded by PackLoader
    ctx = build_pack_context(pack)
    system_message = render_prompt(raw, ctx)

Template variables available to .j2 prompts
--------------------------------------------
``pack_id``, ``pack_name``, ``pack_version``, ``pack_description``,
``owner_team``, ``systems``, ``tags``, ``diagnostics`` (list of
``{id, purpose}``), ``runbooks`` (list of ``{id, card_id, name,
description, tags}``), ``decision_rules`` (list of
``{when_all, when_any, when_expressions, then_runbook}``),
``intake_required_inputs``.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import jinja2
import jinja2.sandbox

from agent_factory.common.logging import get_logger

if TYPE_CHECKING:
    from .pack_loader import AgentPack

logger = get_logger("prompts")

# ---------------------------------------------------------------------------
# Shared sandboxed environment
# ---------------------------------------------------------------------------
# * SandboxedEnvironment blocks access to Python dunder attributes and
#   prevents importing modules — safe for untrusted template authors.
# * DebugUndefined renders unknown variables as "{{ name }}" (not blank),
#   which preserves Mustache-style tool templates that may appear in the
#   same prompt file without being interpreted as Jinja2.
# * keep_trailing_newline preserves the final newline in .j2 files so the
#   rendered string matches what would be read from a .txt file.
# ---------------------------------------------------------------------------
_JINJA_ENV: jinja2.sandbox.SandboxedEnvironment = jinja2.sandbox.SandboxedEnvironment(
    undefined=jinja2.DebugUndefined,
    autoescape=False,         # prompts are plain text, not HTML
    keep_trailing_newline=True,
    trim_blocks=False,        # preserve template whitespace intentionally
    lstrip_blocks=False,
)


def build_pack_context(pack: "AgentPack") -> dict[str, Any]:
    """Build a safe, static template context from a loaded pack.

    Only pack-level metadata from ``pack.yaml`` and ``sop-ir.json`` is
    exposed.  Request-level data (incident text, session IDs, user input)
    is deliberately excluded to prevent prompt-injection attacks.

    Args:
        pack: A fully-loaded :class:`~agent_factory.pack_loader.AgentPack`.

    Returns:
        A flat dict of template variables suitable for Jinja2 rendering.
    """
    sop = pack.sop_ir
    cfg = pack.config

    return {
        # ── Pack identity ──────────────────────────────────────────────
        "pack_id": pack.pack_id,
        "pack_name": cfg.name,
        "pack_version": cfg.version,
        "pack_description": cfg.description,
        "owner_team": cfg.owner_team,

        # ── SOP-IR metadata ───────────────────────────────────────────
        "systems": list(sop.metadata.systems),
        "tags": list(sop.metadata.tags),

        # ── Diagnostics (id + human-readable purpose) ─────────────────
        "diagnostics": [
            {"id": d.id, "purpose": d.purpose}
            for d in sop.diagnostics
        ],

        # ── Runbooks (enough for decision / action prompts) ────────────
        "runbooks": [
            {
                "id": rb.id,
                "card_id": rb.card_id or rb.id.replace("RUNBOOK-", ""),
                "name": rb.name,
                "description": rb.description,
                "tags": dict(rb.tags),
            }
            for rb in sop.runbooks
        ],

        # ── Decision rules ────────────────────────────────────────────
        "decision_rules": [
            {
                "when_all": list(rule.when.all),
                "when_any": list(rule.when.any),
                "when_expressions": list(rule.when.expressions),
                "then_runbook": rule.then_runbook,
            }
            for rule in sop.decision_rules
        ],

        # ── Intake ────────────────────────────────────────────────────
        "intake_required_inputs": list(sop.intake.required_inputs),
    }


def render_prompt(raw_template: str, context: dict[str, Any]) -> str:
    """Render a prompt string through the sandboxed Jinja2 environment.

    If the template contains no Jinja2 syntax (plain-text .txt files),
    the string is returned *unchanged* — rendering is a no-op.

    On ``TemplateSyntaxError`` the raw template is returned and a warning is
    emitted, so a malformed .j2 file never crashes the agent build pipeline.
    Any other exception also falls back to the raw template with a warning.

    Args:
        raw_template: Raw prompt string (plain text or Jinja2 template).
        context: Variables available to the template.  **Must** contain only
            static pack data produced by :func:`build_pack_context` —
            never user-supplied input.

    Returns:
        Rendered prompt string, or the original string on failure.
    """
    if not raw_template:
        return raw_template

    try:
        tmpl = _JINJA_ENV.from_string(raw_template)
        return tmpl.render(**context)
    except jinja2.TemplateSyntaxError as exc:
        logger.warning(
            "Jinja2 syntax error in prompt template at line %d: %s. "
            "Returning raw template — fix the .j2 syntax.",
            exc.lineno,
            exc.message,
        )
        return raw_template
    except Exception as exc:  # noqa: BLE001 — intentional broad catch for safety
        logger.warning(
            "Unexpected error rendering prompt template: %s. "
            "Returning raw template.",
            exc,
        )
        return raw_template
