"""SOP-Pack subsystem — loading, modelling, registry, and prompts.

This package groups the four modules that operate on SOP Packs under
one cohesive namespace.  The actual implementations live at the
historical top-level paths (``agent_factory.pack_loader``,
``agent_factory.pack_models``, ``agent_factory.registry``,
``agent_factory.prompts``) because the unit-test suite patches their
attribute tables — moving the bodies would invalidate those patches.

The sub-modules of this package are forward re-export shims, so new
code can import from a single cohesive namespace::

    from agent_factory.pack.loader   import load_pack, AgentPack
    from agent_factory.pack.models   import PipelineAgentSpec
    from agent_factory.pack.registry import pack_registry, PackRegistry
    from agent_factory.pack.prompts  import render_prompt, build_pack_context

Public surface re-exported at the package level for convenience:

* ``AgentPack``         — loaded SOP Pack object.
* ``load_pack``         — pack-from-disk factory.
* ``pack_registry``     — process-wide singleton ``PackRegistry``.
* ``PackRegistry``      — registry class.
* ``render_prompt``     — render a pack prompt template.
* ``build_pack_context``— build the Jinja context for prompt rendering.
"""
from __future__ import annotations

from agent_factory.pack.loader import AgentPack, load_pack  # noqa: F401
from agent_factory.pack.prompts import build_pack_context, render_prompt  # noqa: F401
from agent_factory.pack.registry import PackRegistry, pack_registry  # noqa: F401

__all__ = [
    "AgentPack",
    "load_pack",
    "PackRegistry",
    "pack_registry",
    "render_prompt",
    "build_pack_context",
]
