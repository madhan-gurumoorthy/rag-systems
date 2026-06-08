"""Mount the local-only test console onto a FastAPI app.

Exposes :func:`mount_console`, which ``app.mount``s a ``StaticFiles``
instance at ``/console`` (or a caller-supplied prefix) so the operator
can hit ``http://localhost:8000/console`` after starting ``run_dev.sh``.

The console is a Vite + React + TypeScript SPA whose source lives in
``ui/`` next to this module. ``npm run build`` emits to
``static/dist/``, which is the directory mounted here. When the dist
directory is absent the mount is skipped and a hint is logged; the rest
of the app keeps working.

A deep link like ``/console/some-tab`` MUST hydrate ``index.html``
rather than 404, otherwise client-side routing breaks on refresh.
``_SpaStaticFiles`` catches Starlette's 404 from ``StaticFiles`` and
replays the request against ``index.html``; every other status
propagates untouched.
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

logger = logging.getLogger("dev.local_console")

_STATIC_DIR = Path(__file__).resolve().parent / "static" / "dist"


class _SpaStaticFiles(StaticFiles):
    """``StaticFiles`` with SPA-aware 404 fallback.

    Only 404 is rewritten — 403/500 propagate so misconfigured
    permissions or upstream bugs surface naturally.
    """

    async def get_response(self, path: str, scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404:
                raise
            return await super().get_response("index.html", scope)


def mount_console(app: FastAPI, *, prefix: str = "/console") -> bool:
    """Mount the console static-files sub-app onto ``app``.

    Args:
        app: The FastAPI app to mount onto.
        prefix: Mount path. Default ``/console``.

    Returns:
        ``True`` when the mount succeeded, ``False`` when the static
        directory is missing. The caller logs at the call site so the
        operator sees the right diagnostic either way.
    """
    if not _STATIC_DIR.is_dir() or not (_STATIC_DIR / "index.html").is_file():
        logger.warning(
            "Local console static dir missing — expected %s. "
            "Run `cd dev/local_console/ui && npm install && npm run build` "
            "to emit the dist directory. Mount skipped.",
            _STATIC_DIR,
        )
        return False

    app.mount(
        prefix,
        _SpaStaticFiles(directory=str(_STATIC_DIR), html=True),
        name="local_console",
    )
    return True


__all__ = ["mount_console"]
