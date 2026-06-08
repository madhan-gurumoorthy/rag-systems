"""Mount the matbot-multi-agents landing page onto the FastAPI app.

The landing page is a Vite + React + TypeScript SPA whose source lives
in ``frontend/`` at the repo root. ``npm run build`` (or the Docker
``frontend-build`` stage) emits to ``frontend/dist/``, which is the
directory mounted here.

Contract:

* Mount the SPA last — after every API router is registered — so
  paths like ``/a2a/*``, ``/healthz``, ``/dashboard`` resolve to the
  agent backend instead of the static mount.
* ``/`` returns ``index.html`` (``StaticFiles`` ``html=True``).
* Hashed bundle assets emitted by Vite live under ``/assets/`` and are
  served verbatim by ``StaticFiles``.
* A request for a path that is neither an API route, an existing
  static file, nor an asset (e.g. someone deep-links into a future
  client-side route) is rewritten to ``index.html`` so the SPA can
  take over. Only 404s are rewritten — 403 / 5xx propagate untouched.

When the ``frontend/dist`` directory is absent the mount is skipped
and a hint is logged; the rest of the app keeps working so the agent
API is usable in pure-backend dev loops.
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

logger = logging.getLogger("agent_factory.api.homepage")

# repo-root / frontend / dist
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DIST_DIR = _REPO_ROOT / "frontend" / "dist"


class _SpaStaticFiles(StaticFiles):
    """``StaticFiles`` with SPA-aware 404 fallback.

    Only 404 is rewritten — 403 / 500 propagate so misconfigured
    permissions or upstream bugs surface naturally.
    """

    async def get_response(self, path: str, scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404:
                raise
            return await super().get_response("index.html", scope)


def mount_homepage(app: FastAPI, *, prefix: str = "/") -> bool:
    """Mount the landing-page static-files sub-app onto ``app``.

    Args:
        app: The FastAPI app to mount onto. MUST already have every
            API router registered — the mount catches all otherwise
            unmatched paths.
        prefix: Mount path. Default ``/``.

    Returns:
        ``True`` when the mount succeeded, ``False`` when the build
        artefact is missing.
    """
    if not _DIST_DIR.is_dir() or not (_DIST_DIR / "index.html").is_file():
        logger.warning(
            "Homepage build missing — expected %s. "
            "Run `cd frontend && npm install && npm run build` "
            "to emit the dist directory. Mount skipped.",
            _DIST_DIR,
        )
        return False

    app.mount(
        prefix,
        _SpaStaticFiles(directory=str(_DIST_DIR), html=True),
        name="homepage",
    )
    return True


__all__ = ["mount_homepage"]
