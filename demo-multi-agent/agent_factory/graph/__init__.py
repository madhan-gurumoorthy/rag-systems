"""LangGraph plumbing kept by the runtime.

This package now exposes only the two pieces the chat path needs:

* :mod:`agent_factory.graph.state` — :class:`BaseAgentState` TypedDict and
  shared reducers consumed by every pack's ``state.py``.
* :mod:`agent_factory.graph.checkpointer` — the singleton
  :class:`LangGraphCheckpointer` that backs multi-turn chat memory on
  top of the shared Postgres pool.
"""
from agent_factory.graph.checkpointer import (
    LangGraphCheckpointer,
    langgraph_checkpointer,
)
from agent_factory.graph.state import (
    BaseAgentState,
    add_messages,
    append_error,
    empty_state,
    merge_dict,
    sum_usage,
)

__all__ = [
    "BaseAgentState",
    "empty_state",
    "add_messages",
    "merge_dict",
    "sum_usage",
    "append_error",
    "LangGraphCheckpointer",
    "langgraph_checkpointer",
]
