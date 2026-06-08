"""Kubernetes-style health and readiness endpoints."""
from datetime import datetime

from fastapi import APIRouter

from agent_factory.api.middleware.timing import api_timer
from agent_factory.api.schemas import HealthResponse, ReadinessResponse
from agent_factory.common.errors import handle_internal_error
from agent_factory.registry import pack_registry
from storage.state_store import postgres_state_manager

router = APIRouter(tags=["health"])


@router.get("/healthz", response_model=HealthResponse)
@api_timer("healthz_check")
async def healthz():
    """Consolidated liveness endpoint."""
    postgres_ready = postgres_state_manager.pool is not None
    factory_ready = pack_registry.initialized
    status = "healthy" if postgres_ready else "degraded"
    return HealthResponse(
        status=status,
        timestamp=datetime.utcnow().isoformat() + 'Z',
        rag_ready=True,
        postgres_ready=postgres_ready,
        redis_ready=False,
        version="1.0.0",
        dependencies={
            "postgres": {"status": "healthy" if postgres_ready else "unhealthy"},
            "agent_factory": {
                "status": "healthy" if factory_ready else "degraded",
                "packs": pack_registry.list_packs(),
            },
        }
    )


@router.get("/readyz", response_model=ReadinessResponse)
@api_timer("readiness_check")
async def readyz():
    """Kubernetes readiness check."""
    postgres_ready = postgres_state_manager.pool is not None
    factory_ready = pack_registry.initialized
    ready = postgres_ready and factory_ready

    blocking_dependencies = []
    if not postgres_ready:
        blocking_dependencies.append("postgres_database")
    if not factory_ready:
        blocking_dependencies.append("pack_registry")

    if ready:
        return ReadinessResponse(
            status="ready",
            timestamp=datetime.utcnow().isoformat() + 'Z',
            ready=True,
            blocking_dependencies=[],
            details={
                "postgres_ready": postgres_ready,
                "factory_ready": factory_ready,
            }
        )
    else:
        return handle_internal_error(
            "Service not ready",
            details={
                "postgres_ready": postgres_ready,
                "blocking_dependencies": blocking_dependencies,
            }
        )
