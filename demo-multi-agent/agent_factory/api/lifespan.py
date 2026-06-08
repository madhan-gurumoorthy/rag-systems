"""FastAPI lifespan — startup/shutdown wiring for the Agent Factory.

Responsibilities (in order):

1. Initialize the shared PostgreSQL pool (``postgres_state_manager``) and
   bind every store to that pool when available.
2. Discover and load every pack under ``packs/`` via ``pack_registry``.
3. Upsert each loaded pack into ``agent_registry`` so chat sessions have
   a valid FK target.
4. Initialise the LangGraph checkpointer so multi-turn chat history can
   ride on the LangGraph Postgres saver.
5. Build the A2A AgentCard + executor and stash them in the adapter
   singleton ready for :func:`mount_a2a` in ``app.py``.
6. Mount any pack-supplied ``api.py`` ``router`` so packs can expose
   their own debug surfaces.
7. Expose ``app.state.in_flight`` as an anchor for detached background
   tasks.

Boot is fail-loud for the *default pack* and fail-soft for non-default
packs — a broken side pack must not prevent the rest from coming up.
"""
from __future__ import annotations

import asyncio
import importlib
import os
from contextlib import asynccontextmanager
from typing import Iterable

from fastapi import FastAPI

from agent_factory.api.a2a import init_a2a
from agent_factory.common.logging import get_logger
from agent_factory.infrastructure.settings import get_config
from agent_factory.registry import PACK_ID_PATTERN, pack_registry
from agent_factory.graph.checkpointer import langgraph_checkpointer

from storage.state_store import postgres_state_manager
from storage.work_item_store import work_item_store
from storage.event_store import event_store
from storage.agent_registry_store import agent_registry_store
from storage.session_store import session_store

logger = get_logger("agent_factory_api.lifespan")

# ─────────────────────────────────────────────────────────────────────
# Schema health check — run immediately after pool init.
# ─────────────────────────────────────────────────────────────────────
_SCHEMA_PROBE_TABLES = ("agent_registry", "session", "work_item", "event")


async def _check_schema_health(pool) -> None:
    """Verify the 4 canonical tables exist and are queryable.

    Raises ``RuntimeError`` with an actionable message if any table is
    missing — better to fail loud at boot than to surface a cryptic
    asyncpg ``UndefinedTableError`` on the first real request.
    """
    missing: list[str] = []
    async with pool.acquire() as conn:
        for table in _SCHEMA_PROBE_TABLES:
            try:
                await conn.fetchval(
                    f"SELECT 1 FROM {table} LIMIT 1"      # noqa: S608
                )
            except Exception:
                missing.append(table)

    if missing:
        raise RuntimeError(
            f"Schema health check failed — missing tables: "
            f"{', '.join(missing)}.  Run: "
            f"psql \"$DATABASE_URL\" -f storage/schema.sql"
        )
    logger.info(
        "✅ Schema health check passed (%d tables verified)",
        len(_SCHEMA_PROBE_TABLES),
    )


# ─────────────────────────────────────────────────────────────────────
# Shutdown drain — bounded grace window for detached runner tasks.
# Tunable via constant; can be promoted to a config knob if operations
# needs runtime override.  The settle window after cancellation gives
# finaliser coroutines a chance to write the terminal `failed` row
# before the pool is closed.
# ─────────────────────────────────────────────────────────────────────
RUN_SHUTDOWN_GRACE_SECONDS = 5.0
RUN_SHUTDOWN_CANCEL_SETTLE_SECONDS = 1.0


async def _drain_in_flight(
    in_flight: Iterable[asyncio.Task],
    *,
    grace_seconds: float = RUN_SHUTDOWN_GRACE_SECONDS,
    cancel_settle_seconds: float = RUN_SHUTDOWN_CANCEL_SETTLE_SECONDS,
) -> dict:
    """Drain detached runner tasks at shutdown.

    Waits up to ``grace_seconds`` for tasks to complete naturally, then
    cancels any still pending.  A short ``cancel_settle_seconds`` window
    after cancellation lets the finaliser coroutines write the terminal
    ``failed`` row before the pool is torn down.

    Returns a small report dict ``{"drained": int, "cancelled": int}``
    suitable for logging.  Never raises — defensive try/except wraps the
    inner ``asyncio.wait`` calls so a hung task can't prevent shutdown.
    """
    pending = [t for t in in_flight if not t.done()]
    if not pending:
        return {"drained": 0, "cancelled": 0}

    try:
        done, still_pending = await asyncio.wait(
            pending, timeout=grace_seconds
        )
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("Drain wait failed: %s", exc)
        done = set()
        still_pending = set(pending)

    if still_pending:
        for t in still_pending:
            t.cancel()
        try:
            await asyncio.wait(still_pending, timeout=cancel_settle_seconds)
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning("Cancellation settle failed: %s", exc)

    return {"drained": len(done), "cancelled": len(still_pending)}


async def _upsert_pack_to_agent_registry(pack) -> bool:
    """Upsert a loaded pack into ``agent_registry``. Returns True on success."""
    cfg = pack.config
    mcfg = getattr(cfg, "model", None)
    return await agent_registry_store.upsert_agent(
        pack.pack_id,
        agent_name=getattr(cfg, "name", "") or pack.pack_id,
        agent_version=getattr(cfg, "version", "1.0.0"),
        owner_team=getattr(cfg, "owner_team", "") or "unknown",
        status="active",
        config={
            "pack_id": pack.pack_id,
            "description": getattr(cfg, "description", ""),
            "model": {
                "provider": getattr(mcfg, "provider", "azure_openai"),
                "default": getattr(mcfg, "model", "") or "gpt-4.1-mini",
                "deployment": getattr(mcfg, "deployment", ""),
                "max_tokens": getattr(mcfg, "max_tokens", 4096),
                "temperature": getattr(mcfg, "temperature", 0.1),
            } if mcfg else {},
            "capabilities": {
                "supports_hitl": True,
                "supports_streaming": True,
            },
        },
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI app initialization."""
    logger.info("Starting Agent Factory initialization...")

    # Anchor for detached runner tasks created when the deadline race
    # times out.  Initialised before any startup step that could raise
    # so handlers always find a usable set if they run despite a
    # partial-startup failure.
    app.state.in_flight = set()

    try:
        config = get_config()

        _pack_id_env = os.environ.get("DEFAULT_PACK_ID", "").strip()
        agent_name = (
            _pack_id_env
            if _pack_id_env and PACK_ID_PATTERN.match(_pack_id_env)
            else "agent-factory"
        )

        # ── PostgreSQL state manager (optional — graceful fallback) ──
        logger.info("Initializing PostgreSQL state manager...")
        pg_config = getattr(config, 'postgresql', None)
        pg_initialized = await postgres_state_manager.initialize(
            agent_name, pg_config=pg_config
        )

        if pg_initialized:
            logger.info("✅ PostgreSQL state manager initialized")
            work_item_store.bind_pool(postgres_state_manager.pool)
            event_store.bind_pool(postgres_state_manager.pool)
            agent_registry_store.bind_pool(postgres_state_manager.pool)
            session_store.bind_pool(postgres_state_manager.pool)
            logger.info("✅ All stores bound to shared pool")

            # Verify the 4 canonical tables exist before accepting traffic
            await _check_schema_health(postgres_state_manager.pool)
        else:
            logger.warning(
                "⚠️  PostgreSQL not configured — conversation state will NOT persist. "
                "Configure [postgresql] in agent_factory/infrastructure/secrets.toml to enable."
            )

        # ── Pack discovery ──────────────────────────────────────────
        loaded_packs = pack_registry.discover_and_load_all(packs_root="packs")
        logger.info(
            f"Pack registry: loaded {len(loaded_packs)} pack(s) — "
            f"default='{pack_registry.default_pack_id}'"
        )
        pack_health = pack_registry.get_pack_health()
        for pid, health in pack_health.items():
            logger.info(
                f"  Pack '{pid}': {health['tools_bound']}/{health['tools_total']} tools bound, "
                f"{health['warnings']} warnings"
            )

        # ── Pack HTTP router auto-discovery ────────────────────────────
        # Any pack that ships a packs/<id>/api.py with a top-level
        # ``router`` (FastAPI ``APIRouter``) is mounted automatically.
        # Packs without an api.py are silently skipped; failures are
        # logged as warnings so a broken pack router cannot prevent boot.
        for _api_pid in pack_registry.list_packs():
            _api_module_name = f"packs.{_api_pid}.api"
            try:
                _api_mod = importlib.import_module(_api_module_name)
                if hasattr(_api_mod, "router"):
                    app.include_router(_api_mod.router)
                    logger.info("✅ Mounted pack HTTP router: %s", _api_pid)
            except ModuleNotFoundError as _mnfe:
                # Suppress only when the pack itself has no api.py — any
                # ModuleNotFoundError raised inside the module's own imports
                # is a real error and must surface as a warning.
                if _mnfe.name == _api_module_name:
                    pass  # pack has no api.py — expected for most packs
                else:
                    logger.warning(
                        "Pack router import error for %s (broken dependency '%s'): %s",
                        _api_pid, _mnfe.name, _mnfe,
                    )
            except Exception as _api_exc:
                logger.warning(
                    "Pack router mount failed for %s: %s", _api_pid, _api_exc
                )

        # ── agent_registry upsert ───────────────────────────────────
        _default_pack = pack_registry.get_pack()
        if _default_pack and pg_initialized:
            for _pid in pack_registry.list_packs():
                _pack = pack_registry.get_pack(_pid)
                if _pack is None:
                    continue
                upsert_ok = await _upsert_pack_to_agent_registry(_pack)
                if upsert_ok:
                    logger.info(
                        "✅ agent_registry upserted for pack_id=%s",
                        _pack.pack_id,
                    )
                elif _pack.pack_id == _default_pack.pack_id:
                    raise RuntimeError(
                        f"agent_registry upsert failed for default "
                        f"pack_id={_pack.pack_id} — LangGraph runs "
                        f"would FK-violate on work_item insert.  Fix "
                        f"the database before booting."
                    )
                else:
                    logger.error(
                        "agent_registry upsert failed for non-default "
                        "pack_id=%s — incidents routed to that pack "
                        "will FK-violate until the row is restored.",
                        _pack.pack_id,
                    )

        # ── LangGraph checkpointer (powers multi-turn chat memory) ──
        if pg_initialized:
            cp_ok = await langgraph_checkpointer.initialize(pg_config=pg_config)
            if cp_ok:
                logger.info("✅ LangGraph checkpointer initialized (chat memory)")
            else:
                logger.warning(
                    "⚠️  LangGraph checkpointer init failed — chat will run without persistent memory."
                )

        # ── A2A AgentCard + executor ──────────────────────────────
        # Built after packs are loaded so each pack is advertised as an
        # AgentSkill on the card.  Mounted onto the live FastAPI app
        # immediately so /a2a is reachable on the first request.
        from agent_factory.api.a2a import mount_a2a
        if init_a2a():
            if mount_a2a(app):
                logger.info("✅ A2A adapter initialised and mounted at /a2a")
            else:
                logger.warning("⚠️  A2A adapter initialised but route mount failed.")
        else:
            logger.warning("⚠️  A2A adapter failed to initialise — /a2a will not be available.")

        logger.info("Agent Factory startup completed")
    except Exception as e:
        logger.error(f"Failed during startup: {str(e)}")
        raise
    yield
    logger.info("Agent Factory shutting down...")

    # Drain detached runner tasks before tearing down the pool so
    # finaliser coroutines have a chance to flush their terminal rows.
    in_flight = getattr(app.state, "in_flight", None) or set()
    if in_flight:
        try:
            report = await _drain_in_flight(list(in_flight))
            if report["drained"]:
                logger.info(
                    "✅ %d runner task(s) drained cleanly.", report["drained"]
                )
            if report["cancelled"]:
                logger.warning(
                    "Cancelled %d runner task(s) that exceeded the %ss grace window.",
                    report["cancelled"],
                    RUN_SHUTDOWN_GRACE_SECONDS,
                )
        except Exception as e:  # pragma: no cover — defensive
            logger.error("Drain on shutdown failed: %s", e)

    # Release the LangGraph checkpointer's internal pool, if held.
    try:
        await langgraph_checkpointer.close()
    except Exception as e:  # pragma: no cover
        logger.error(f"checkpointer shutdown failed: {e}")


__all__ = ["lifespan"]
