"""Forward shim — re-exports :class:`LangChainAgentBuilder` and its
helpers from the historical home at :mod:`agent_factory.langchain_builder`.

The runtime substrate sits at :mod:`agent_factory.runtime` as a
single namespace for the LangChain-driven runtime pieces.  The actual
implementation of the builder lives at the historical path because the
unit-test suite (``tests/unit/test_langchain_builder.py``) patches helpers
through that module's attribute table — moving the body would invalidate
those patches.  This shim lets new code import from the new namespace
unchanged::

    from agent_factory.runtime.builder import LangChainAgentBuilder
"""
from __future__ import annotations

from agent_factory.langchain_builder import (  # noqa: F401
    LangChainAgentBuilder,
    _build_stub_model,
    _resolve_prompt,
    _wrap_tools_for_langchain,
)

__all__ = ["LangChainAgentBuilder"]
