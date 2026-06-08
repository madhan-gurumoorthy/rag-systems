"""Handler registry for declarative tool types.

Each tool type (``threshold_check``, ``decision_matrix``, ``http_api``,
``sql_query``, ``jira``, ``kafka``, …) has a single
:class:`~agent_factory.tools.handlers._base.ToolHandler` subclass that
owns its execution logic.  The executor dispatches by
``ToolSpec.type`` via :func:`get_handler`.

Adding a new tool type:

    1. Create ``handlers/<type_name>.py`` with a ``ToolHandler``
       subclass whose ``type_name`` matches the YAML enum.
    2. Import + call :func:`register` here at module-load time so the
       executor sees it without bootstrapping logic.
"""
from __future__ import annotations

from typing import Type

from ._base import ToolHandler
from .a2a import A2AHandler
from .batch import BatchHandler
from .bigquery_query import BigQueryQueryHandler
from .cassandra import CassandraHandler
from .decision_matrix import DecisionMatrixHandler
from .elasticsearch import ElasticsearchHandler
from .graphql import GraphQLHandler
from .http_api import HttpApiHandler
from .jira import JiraHandler
from .kafka import KafkaHandler
from .redis import RedisHandler
from .sql_query import SqlQueryHandler
from .threshold_check import ThresholdCheckHandler

_HANDLERS: dict[str, ToolHandler] = {}


def register(handler_cls: Type[ToolHandler]) -> Type[ToolHandler]:
    """Register a handler class (idempotent, last-write-wins).

    Returns the class so this can be used as a decorator:

    .. code-block:: python

        @register
        class MyHandler(ToolHandler):
            type_name = "my_type"
            ...
    """
    instance = handler_cls()
    if not instance.type_name:
        raise ValueError(
            f"{handler_cls.__name__} must set a non-empty `type_name`"
        )
    _HANDLERS[instance.type_name] = instance
    return handler_cls


def get_handler(type_name: str) -> ToolHandler | None:
    """Return the handler for ``type_name``, or ``None`` if unregistered."""
    return _HANDLERS.get(type_name)


def known_types() -> tuple[str, ...]:
    """Tuple of all registered tool-type names (stable order)."""
    return tuple(_HANDLERS.keys())


# ── Bundled handlers ─────────────────────────────────────────────────
# Eager-register at import time — keeps lookup O(1) on the hot path and
# avoids per-request import overhead.
register(ThresholdCheckHandler)
register(DecisionMatrixHandler)
register(BatchHandler)
register(BigQueryQueryHandler)
register(A2AHandler)
register(CassandraHandler)
register(SqlQueryHandler)
register(GraphQLHandler)
register(RedisHandler)
register(HttpApiHandler)
register(ElasticsearchHandler)
register(JiraHandler)
register(KafkaHandler)


__all__ = ["ToolHandler", "register", "get_handler", "known_types"]
