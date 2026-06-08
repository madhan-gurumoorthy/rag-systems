"""Forward shim — re-exports the prompt-rendering helpers from their
historical home.

The actual implementation lives at :mod:`agent_factory.prompts`.
This shim gives callers a cohesive namespace::

    from agent_factory.pack.prompts import build_pack_context, render_prompt

The original path keeps working unchanged so existing imports and
tests don't need to be touched.
"""
from __future__ import annotations

from agent_factory.prompts import *  # noqa: F401,F403
from agent_factory.prompts import build_pack_context, render_prompt  # noqa: F401

__all__ = ["build_pack_context", "render_prompt"]
