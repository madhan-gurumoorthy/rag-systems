"""Agent Factory — config-driven multi-agent runtime.

This module is intentionally thin.  Everything substantive (lifespan
wiring, route handlers, helpers) lives under ``agent_factory/api``.
``app.py`` only:

  * Builds the ``FastAPI`` instance with the lifespan context manager.
  * Wires global exception handlers + request-validation logging.
  * Mounts every route module's ``APIRouter`` onto the app.
  * Provides the uvicorn entrypoint for direct invocation.
"""
from __future__ import annotations

import os

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from agent_factory.api.homepage import mount_homepage
from agent_factory.api.lifespan import lifespan
from agent_factory.api.routes import (
    dashboard as dashboard_routes,
    factory as factory_routes,
    health as health_routes,
)
from agent_factory.common.errors import (
    agent_exception_handler,
    general_exception_handler,
)
from agent_factory.common.logging import get_logger
from agent_factory.common.tracing import setup_tracing
from agent_factory.infrastructure.settings import get_config

# Initialize tracing early so route imports can pick up the configured
# instrumentation.
setup_tracing()

logger = get_logger("agent_factory_api")

_config = get_config()
_APP_TITLE = getattr(_config, "APP_TITLE", None) or getattr(_config, "AGENT_NAME", "MatBot Agent Factory")
_APP_DESCRIPTION = getattr(
    _config, "APP_DESCRIPTION",
    "Config-driven multi-agent runtime — drop an SOP Pack, get a deployable agent."
)

app = FastAPI(
    title=_APP_TITLE,
    description=_APP_DESCRIPTION,
    version="1.0.0",
    lifespan=lifespan,
)

# ─────────────────────────────────────────────────────────────────────
# CORS middleware (browser cross-origin policy)
# ─────────────────────────────────────────────────────────────────────
# Driven entirely by ``[default.cors]`` in ``secrets.toml`` — no
# hard-coded origins.  If the block is absent the middleware is not
# installed, which is the right default for server-to-server-only
# deployments. The React dashboard team picks its origins per
# environment by editing that block.

def _install_cors(app: FastAPI) -> None:
    cors_cfg = getattr(_config, "cors", None)
    if cors_cfg is None:
        logger.info("CORS not configured ([default.cors] missing) — middleware skipped")
        return
    if hasattr(cors_cfg, "to_dict"):
        cors_cfg = cors_cfg.to_dict()
    if not isinstance(cors_cfg, dict):
        logger.warning("CORS config is not a mapping; middleware skipped")
        return

    # Dynaconf uppercases TOML keys; accept either case so a future
    # operator can write either ALLOW_ORIGINS or allow_origins.
    def _pick(key: str, default):
        for variant in (key, key.upper(), key.lower()):
            if variant in cors_cfg:
                return cors_cfg[variant]
        return default

    allow_origins = list(_pick("allow_origins", []))
    allow_origin_regex = _pick("allow_origin_regex", None) or None
    if not allow_origins and not allow_origin_regex:
        logger.info(
            "CORS [default.cors] has no ALLOW_ORIGINS or ALLOW_ORIGIN_REGEX — middleware skipped"
        )
        return

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_origin_regex=allow_origin_regex,
        allow_credentials=bool(_pick("allow_credentials", True)),
        allow_methods=list(_pick("allow_methods", ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])),
        allow_headers=list(_pick("allow_headers", ["*"])),
        expose_headers=list(_pick("expose_headers", []) or []),
        max_age=int(_pick("max_age_seconds", 600)),
    )
    logger.info(
        "CORS middleware installed: exact_origins=%d regex=%s credentials=%s",
        len(allow_origins),
        "yes" if allow_origin_regex else "no",
        _pick("allow_credentials", True),
    )


_install_cors(app)

# ─────────────────────────────────────────────────────────────────────
# Global exception handlers
# ─────────────────────────────────────────────────────────────────────

from fastapi import HTTPException

app.add_exception_handler(HTTPException, agent_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Return structured Pydantic validation errors with no body echo.

    The response carries only ``exc.errors()`` (field-level diagnostics
    from Pydantic) and the path that failed.  The raw request body is
    NEVER echoed back to the client and NEVER written to logs — callers
    can route arbitrary content (incl. tokens) into the body, and a
    validation failure must not become a disclosure channel.
    """
    logger.warning(
        "Validation error on %s %s: %d field error(s)",
        request.method, request.url.path, len(exc.errors()),
    )
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )


# ─────────────────────────────────────────────────────────────────────
# Mount route modules
# ─────────────────────────────────────────────────────────────────────

_IS_PARENT = os.getenv("IS_PARENT", "").lower() in ("1", "true", "yes", "on")

# A2A routes (POST /a2a + GET /.well-known/agent-card.json) are mounted
# during lifespan startup after init_a2a() builds the AgentCard from the
# loaded pack registry.  See agent_factory/api/lifespan.py.

app.include_router(factory_routes.router)
app.include_router(health_routes.router)
if _IS_PARENT:
    app.include_router(dashboard_routes.router)


# ─────────────────────────────────────────────────────────────────────
# Local-only test console (opt-in via env var)
# ─────────────────────────────────────────────────────────────────────
# When MATBOT_ENABLE_CONSOLE is truthy, mount the dev SPA at /console.
# Never imported on deployed instances — kitt.yml does not set the var.
# MUST mount before the landing page at "/" — Starlette evaluates mounts
# in registration order and the "/" SPA fallback would otherwise swallow
# /console and serve frontend/dist/index.html instead of the console.
if os.getenv("MATBOT_ENABLE_CONSOLE", "").lower() in ("1", "true", "yes", "on"):
    try:
        from fastapi.responses import RedirectResponse

        from dev.local_console import mount_console as _mount_console

        # Bare /console (no trailing slash) does not hit the StaticFiles
        # mount's html=True fallback; redirect to /console/ so the SPA
        # bootstraps. Must be registered BEFORE the mount so the explicit
        # route wins over the prefix match.
        @app.get("/console", include_in_schema=False)
        async def _console_redirect() -> RedirectResponse:
            return RedirectResponse(url="/console/", status_code=307)

        if _mount_console(app):
            logger.info("Local test console mounted at /console")
        else:
            logger.warning(
                "MATBOT_ENABLE_CONSOLE is set but the console build is missing — "
                "run `cd dev/local_console/ui && npm install && npm run build`."
            )
    except Exception as _console_exc:
        logger.warning("Failed to mount local console: %s", _console_exc)


# Landing page and dashboard surface live on the parent runtime only.
# Child pack runtimes set IS_PARENT unset/falsy and keep the SPA off.
if _IS_PARENT:
    if mount_homepage(app):
        logger.info("Landing page mounted at /")
    else:
        logger.info(
            "Landing page not mounted — frontend/dist is missing. "
            "Build with `cd frontend && npm install && npm run build`."
        )
else:
    logger.info("Pack runtime — landing page and dashboard routes disabled")


if __name__ == "__main__":
    try:
        logger.info("Starting Agent Factory server...")
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            access_log=False,
            log_config=None,
        )
    except Exception as e:
        logger.error(f"Failed to start application: {str(e)}", exc_info=True)
        exit(1)
