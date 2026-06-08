"""Back-compat re-export shim for :mod:`agent_factory.runtime.model_client`.

The Walmart-gateway-aware ``AzureChatOpenAI`` factory now lives at
:mod:`agent_factory.runtime.model_client`.  This shim keeps the historic
import path (``from agent_factory.core.langchain_model_client import …``)
working unchanged.

Prefer the new path in new code::

    from agent_factory.runtime.model_client import build_langchain_model_client
"""
from __future__ import annotations

from agent_factory.runtime.model_client import (  # noqa: F401
    build_langchain_model_client,
)

__all__ = ["build_langchain_model_client"]
