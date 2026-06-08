"""Forward shim — re-exports the pack registry from its historical home.

The actual implementation lives at :mod:`agent_factory.registry`.
This shim gives callers a cohesive namespace::

    from agent_factory.pack.registry import pack_registry, PackRegistry

The original path keeps working unchanged so existing imports and
tests (which patch ``agent_factory.registry.load_pack`` and
``agent_factory.registry.logger``) don't need to be touched.
"""
from __future__ import annotations

from agent_factory.registry import *  # noqa: F401,F403
from agent_factory.registry import DEFAULT_PACK_ID, PackRegistry, pack_registry  # noqa: F401

__all__ = ["DEFAULT_PACK_ID", "PackRegistry", "pack_registry"]
