"""LangChain runtime substrate for the agent factory.

This package is the canonical namespace for the LangChain/LangGraph
runtime pieces:

* :mod:`agent_factory.runtime.builder`       — ``LangChainAgentBuilder``
  (pack → agent-graph factory).
* :mod:`agent_factory.runtime.chat`          — production chat surface
  (``run_chat``, ``run_chat_stream``, ``get_pipeline_agent_names``).
* :mod:`agent_factory.runtime.model_client``  — Walmart-gateway-aware
  ``AzureChatOpenAI`` factory used by both the chat path and the
  LangGraph work-item topology.

``builder`` and ``chat`` re-export their implementations from
``agent_factory.langchain_builder`` / ``agent_factory.langchain_chat``;
callers should import from this ``runtime`` package so they stay
decoupled from the physical module layout.
"""
from __future__ import annotations

from agent_factory.runtime.builder import LangChainAgentBuilder  # noqa: F401
from agent_factory.runtime.chat import (  # noqa: F401
    get_pipeline_agent_names,
    run_chat,
    run_chat_stream,
)
from agent_factory.runtime.model_client import (  # noqa: F401
    build_langchain_model_client,
)

__all__ = [
    "LangChainAgentBuilder",
    "build_langchain_model_client",
    "get_pipeline_agent_names",
    "run_chat",
    "run_chat_stream",
]
