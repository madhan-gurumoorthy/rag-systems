"""Forward shim — re-exports the pack loader from its historical home.

The actual implementation lives at :mod:`agent_factory.pack_loader`.
This shim gives callers a cohesive namespace::

    from agent_factory.pack.loader import load_pack, AgentPack

The original path keeps working unchanged so existing imports and
tests don't need to be touched.
"""
from __future__ import annotations

from agent_factory.pack_loader import *  # noqa: F401,F403
from agent_factory.pack_loader import AgentPack, PackValidationResult, load_pack  # noqa: F401

__all__ = ["AgentPack", "PackValidationResult", "load_pack"]
