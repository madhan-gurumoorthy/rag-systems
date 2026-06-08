"""Pack/agent introspection endpoints.

Endpoints:
  * GET /api/factory/health    — health/status for all loaded packs
  * GET /api/factory/tools     — per-pack tool availability report
  * GET /api/pack/info         — metadata about the active default pack

A2A discovery lives at ``/.well-known/agent-card.json`` and is served
by ``agent_factory/api/a2a/adapter.py``.
"""
import os
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from agent_factory.api.middleware.timing import api_timer
from agent_factory.common.logging import get_logger
from agent_factory.registry import pack_registry

logger = get_logger("agent_factory_api.factory")
router = APIRouter(tags=["factory"])


@router.get("/api/factory/health")
@api_timer("factory_health")
async def factory_health():
    """Return health/status for all loaded SOP Packs."""
    health = pack_registry.get_pack_health()
    return JSONResponse(content={
        "initialized": pack_registry.initialized,
        "default_pack": pack_registry.default_pack_id,
        "packs": health,
    })


@router.get("/api/factory/tools")
@api_timer("factory_tools")
async def factory_tools(pack_id: Optional[str] = None):
    """Return tool availability report for a pack.

    The caller-supplied ``pack_id`` is gated through
    :meth:`PackRegistry.validate_pack_id` so the value that reaches
    :meth:`get_pack` is either a key drawn from the loaded registry or
    ``None`` (which selects the default pack).  Inputs that fail the
    allowlist or shape check return 404 with the original buffer left
    out of the response.
    """
    if pack_id is None:
        safe_pack_id: Optional[str] = None
    else:
        safe_pack_id = pack_registry.validate_pack_id(pack_id)
        if safe_pack_id is None:
            raise HTTPException(status_code=404, detail="Pack not found")
    pack = pack_registry.get_pack(safe_pack_id)
    if not pack:
        raise HTTPException(
            status_code=404,
            detail=f"Pack '{safe_pack_id or 'default'}' not found",
        )
    from agent_factory.tools.executor import ToolExecutor
    executor = ToolExecutor(pack.tools_manifest)
    return JSONResponse(content=executor.get_availability_report())


@router.get("/api/pack/info")
async def pack_info():
    """Return metadata about the currently loaded SOP Pack."""
    pack = pack_registry.get_pack()
    if not pack:
        return {"error": "No pack loaded"}
    cfg = pack.config
    return {
        "id": cfg.id,
        "name": cfg.name,
        "version": cfg.version,
        "owner_team": cfg.owner_team,
        "description": cfg.description,
        "agent_count": sum(len(p.agents) for p in cfg.pipelines.values()),
        "tool_count": len(pack.tools_manifest.tools),
        "pipeline_count": len(cfg.pipelines),
        "pipelines": {name: [a.name for a in p.agents] for name, p in cfg.pipelines.items()},
    }
