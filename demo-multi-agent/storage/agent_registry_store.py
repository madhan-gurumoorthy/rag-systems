"""Agent registry storage — one row per deployed agent.

Holds platform-level metadata: agent_id (PK), agent_name, agent_version,
owner_team, status, and a JSONB `config` blob containing model defaults,
budget caps, capabilities, SLOs, and topology hash (see ADR-013).

Uses the shared asyncpg pool from `state_store.postgres_state_manager`.

This is part of the new LangGraph-native data model (migration 005).
"""
from __future__ import annotations

import json
import traceback
from typing import Any, Optional

try:
    from agent_factory.common.logging import get_logger
    logger = get_logger("storage.agent_registry")
except ImportError:  # pragma: no cover
    import logging
    logger = logging.getLogger("storage.agent_registry")

from storage.models import AgentRegistryRow

_TABLE = "agent_registry"


class AgentRegistryStore:
    """Manages the agent_registry table — one row per agent."""

    def __init__(self):
        self._pool = None

    def bind_pool(self, pool) -> None:
        """Bind an existing asyncpg pool (from postgres_state_manager)."""
        self._pool = pool

    @property
    def is_available(self) -> bool:
        return self._pool is not None

    # ── Write operations ─────────────────────────────────────────────

    async def upsert_agent(
        self,
        agent_id: str,
        *,
        agent_name: str,
        agent_version: str,
        owner_team: str,
        status: str = "active",
        config: Optional[dict] = None,
    ) -> bool:
        """Create or update an agent row.

        Called at startup from `agent_factory.registry.PackRegistry.initialize`
        so the database always reflects the deployed pack metadata.
        """
        if not self.is_available:
            return False
        try:
            config_json = json.dumps(config or {}, default=str)
            async with self._pool.acquire() as conn:
                await conn.execute(
                    f"""
                    INSERT INTO {_TABLE}
                        (agent_id, agent_name, agent_version, owner_team, status, config)
                    VALUES ($1, $2, $3, $4, $5, $6::jsonb)
                    ON CONFLICT (agent_id) DO UPDATE SET
                        agent_name    = EXCLUDED.agent_name,
                        agent_version = EXCLUDED.agent_version,
                        owner_team    = EXCLUDED.owner_team,
                        status        = EXCLUDED.status,
                        config        = EXCLUDED.config,
                        updated_at    = NOW()
                    """,
                    agent_id, agent_name, agent_version, owner_team, status, config_json,
                )
            logger.info(f"agent_registry upserted: {agent_id}@{agent_version}")
            return True
        except Exception as e:
            logger.error(f"upsert_agent failed: {e}")
            logger.debug(traceback.format_exc())
            return False

    async def archive_agent(self, agent_id: str) -> bool:
        """Set archived_at — soft-delete; rows remain for foreign-key integrity."""
        if not self.is_available:
            return False
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    f"UPDATE {_TABLE} SET archived_at = NOW(), status = 'retired' "
                    f"WHERE agent_id = $1 AND archived_at IS NULL",
                    agent_id,
                )
            return True
        except Exception as e:
            logger.error(f"archive_agent failed: {e}")
            return False

    # ── Read operations ──────────────────────────────────────────────

    async def get_agent(self, agent_id: str) -> Optional[AgentRegistryRow]:
        """Fetch a single agent row, or None if not found."""
        if not self.is_available:
            return None
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    f"SELECT * FROM {_TABLE} WHERE agent_id = $1",
                    agent_id,
                )
            return _row_to_dict(row) if row else None
        except Exception as e:
            logger.error(f"get_agent failed: {e}")
            return None

    async def list_agents(self, *, include_archived: bool = False) -> list[AgentRegistryRow]:
        """List all agents, sorted by agent_id."""
        if not self.is_available:
            return []
        try:
            async with self._pool.acquire() as conn:
                if include_archived:
                    rows = await conn.fetch(f"SELECT * FROM {_TABLE} ORDER BY agent_id ASC")
                else:
                    rows = await conn.fetch(
                        f"SELECT * FROM {_TABLE} "
                        f"WHERE archived_at IS NULL ORDER BY agent_id ASC"
                    )
            return [_row_to_dict(r) for r in rows]
        except Exception as e:
            logger.error(f"list_agents failed: {e}")
            return []

    async def get_config(self, agent_id: str) -> dict:
        """Convenience: return only the JSONB config blob (or empty dict)."""
        agent = await self.get_agent(agent_id)
        if not agent:
            return {}
        cfg = agent.config or {}
        if isinstance(cfg, str):
            try:
                cfg = json.loads(cfg)
            except (json.JSONDecodeError, TypeError):
                cfg = {}
        return cfg if isinstance(cfg, dict) else {}


def _row_to_dict(row) -> AgentRegistryRow:
    """Coerce asyncpg Record → ``AgentRegistryRow``; parse JSONB."""
    d = dict(row)
    raw = d.get("config")
    if isinstance(raw, str):
        try:
            d["config"] = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            d["config"] = {}
    return AgentRegistryRow.model_validate(d)


# Global singleton (exported)
agent_registry_store = AgentRegistryStore()

__all__ = ["AgentRegistryStore", "agent_registry_store", "AgentRegistryRow"]
