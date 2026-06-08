"""Forward shim — re-exports the production chat surface from the
historical home at :mod:`agent_factory.langchain_chat`.

The runtime substrate sits at :mod:`agent_factory.runtime` as a
single namespace for the LangChain-driven runtime pieces.  The chat
implementation stays at the historical path because the unit-test suite
(``tests/unit/test_langchain_chat.py``) patches ``_resolve_pack``,
``LangChainAgentBuilder``, and ``asyncio.sleep`` through that module's
attribute table — moving the body would invalidate those patches.

New code may import from the new namespace unchanged::

    from agent_factory.runtime.chat import run_chat, run_chat_stream
"""
from __future__ import annotations

from agent_factory.langchain_chat import (  # noqa: F401
    BACKOFF_MULTIPLIER,
    DEFAULT_CHAT_HISTORY_TURNS,
    INITIAL_BACKOFF_SECONDS,
    MAX_RETRIES,
    _build_chat_history_messages,
    _build_token_usage_callback,
    _is_connection_error,
    _is_retryable_error,
    get_pipeline_agent_names,
    run_chat,
    run_chat_stream,
)

__all__ = [
    "run_chat",
    "run_chat_stream",
    "get_pipeline_agent_names",
    "MAX_RETRIES",
    "INITIAL_BACKOFF_SECONDS",
    "BACKOFF_MULTIPLIER",
    "DEFAULT_CHAT_HISTORY_TURNS",
]
