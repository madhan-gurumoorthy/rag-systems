"""Forward shim — re-exports the Pydantic pack-model schema from its
historical home.

The actual implementation lives at :mod:`agent_factory.pack_models`.
This shim gives callers a cohesive namespace::

    from agent_factory.pack.models import PipelineAgentSpec, ToolSpec

The original path keeps working unchanged so existing imports and
tests don't need to be touched.
"""
from __future__ import annotations

from agent_factory.pack_models import *  # noqa: F401,F403
