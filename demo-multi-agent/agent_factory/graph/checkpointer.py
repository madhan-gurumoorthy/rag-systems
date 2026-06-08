"""LangGraph AsyncPostgresSaver wrapper — durable checkpointer for StateGraphs.

Persists every super-step so graphs can be resumed after a crash, HITL pause,
or Concord callback.  Initialize at startup, pass ``checkpointer.saver`` into
``graph.compile(checkpointer=...)``, call ``close()`` on shutdown.
"""
from __future__ import annotations

import os
import traceback
from typing import Optional

try:
    from agent_factory.common.logging import get_logger
    logger = get_logger("graph.checkpointer")
except ImportError:  # pragma: no cover
    import logging
    logger = logging.getLogger("graph.checkpointer")

try:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    LANGGRAPH_AVAILABLE = True
except ImportError:  # pragma: no cover
    AsyncPostgresSaver = None  # type: ignore
    LANGGRAPH_AVAILABLE = False
    logger.warning(
        "langgraph-checkpoint-postgres not installed; "
        "checkpointer will be unavailable until requirements.txt is installed"
    )


def _build_conn_string(pg_config=None) -> Optional[str]:
    """Build a libpq-style connection string from pg_config or env vars.

    Returns None if any required field is missing.  Matches the resolution
    order used by `state_store.PostgreSQLStateManager.initialize`.
    """
    if pg_config:
        host     = getattr(pg_config, "LIGHTRAG_POSTGRES_HOST",     None)
        port     = getattr(pg_config, "LIGHTRAG_POSTGRES_PORT",     "5432")
        user     = getattr(pg_config, "LIGHTRAG_POSTGRES_USER",     None)
        password = getattr(pg_config, "LIGHTRAG_POSTGRES_PASSWORD", None)
        database = getattr(pg_config, "LIGHTRAG_POSTGRES_DATABASE", None)
    else:
        host     = os.getenv("POSTGRES_HOST")
        port     = os.getenv("POSTGRES_PORT", "5432")
        user     = os.getenv("POSTGRES_USER")
        password = os.getenv("POSTGRES_PASSWORD")
        database = os.getenv("POSTGRES_DATABASE")

    if not (host and user and password and database):
        return None
    return (
        f"postgresql://{user}:{password}@{host}:{port}/{database}?sslmode=prefer"
    )


class LangGraphCheckpointer:
    """Singleton wrapper around AsyncPostgresSaver.

    Usage:
        await langgraph_checkpointer.initialize(pg_config)   # at startup
        graph = builder.compile(checkpointer=langgraph_checkpointer.saver)
        ...
        await langgraph_checkpointer.close()                 # at shutdown
    """

    def __init__(self):
        self._saver: Optional["AsyncPostgresSaver"] = None
        self._cm = None                                   # async context manager handle
        self._initialized: bool = False

    @property
    def is_available(self) -> bool:
        return self._initialized and self._saver is not None

    @property
    def saver(self) -> Optional["AsyncPostgresSaver"]:
        """Return the underlying saver for `graph.compile(checkpointer=...)`."""
        return self._saver

    async def initialize(self, pg_config=None) -> bool:
        """Create the AsyncPostgresSaver and run idempotent table setup.

        Safe to call multiple times — second + calls short-circuit.
        Returns True on success, False if config or library is missing.
        """
        if self._initialized:
            return True
        if not LANGGRAPH_AVAILABLE:
            logger.warning("langgraph not installed; checkpointer disabled")
            return False

        conn_str = _build_conn_string(pg_config)
        if not conn_str:
            logger.warning(
                "PostgreSQL config missing; LangGraph checkpointer disabled"
            )
            return False

        try:
            # from_conn_string returns an async context manager — we enter it
            # manually so the pool stays alive for the app's lifetime.
            self._cm = AsyncPostgresSaver.from_conn_string(conn_str)
            self._saver = await self._cm.__aenter__()
            # Idempotent — creates langgraph.checkpoints / .writes / etc.
            await self._saver.setup()
            self._initialized = True
            logger.info("LangGraph checkpointer initialized (Postgres backend)")
            return True
        except Exception as e:
            logger.error(f"LangGraph checkpointer init failed: {e}")
            logger.debug(traceback.format_exc())
            self._saver = None
            self._cm = None
            self._initialized = False
            return False

    async def close(self) -> None:
        """Release the saver's internal pool — call on shutdown."""
        if self._cm is not None:
            try:
                await self._cm.__aexit__(None, None, None)
                logger.info("LangGraph checkpointer closed")
            except Exception as e:  # pragma: no cover
                logger.error(f"checkpointer close failed: {e}")
            finally:
                self._saver = None
                self._cm = None
                self._initialized = False


# Global singleton (exported)
langgraph_checkpointer = LangGraphCheckpointer()

__all__ = ["LangGraphCheckpointer", "langgraph_checkpointer"]
