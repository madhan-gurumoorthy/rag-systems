"""Drop-in HTTP-client instrumentation.

Wires httpx clients so every outbound request emits an ``api_call``
event with no per-callsite code change. The service name is inferred
from the request host using a config-driven taxonomy so the framework
stays domain-agnostic — packs (or operators) populate the host→service
map.

Service-name resolution order (first non-empty wins):

1. ``api_call_taxonomy`` mapping passed at construction time (highest
   priority — lets a pack override the default for one specific client).
2. ``[default.api_call_taxonomy]`` block in ``secrets.toml``.
3. The hostname minus its public suffix (e.g. ``siv.walmart.com`` →
   ``siv``) — a sensible fallback that surfaces *something* useful
   even before the taxonomy is configured.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional
from urllib.parse import urlsplit

try:
    from agent_factory.common.logging import get_logger
    logger = get_logger("observability.http_instrumentation")
except ImportError:  # pragma: no cover
    import logging
    logger = logging.getLogger("observability.http_instrumentation")


# ── Taxonomy resolution ────────────────────────────────────────────────

def _load_taxonomy_from_settings() -> dict[str, str]:
    """Read host→service mapping from the dynaconf settings block.

    Returns an empty dict if the block is missing or the settings module
    is not importable — never raises.
    """
    try:
        from agent_factory.infrastructure.settings import get_settings
        s = get_settings()
        block = getattr(s, "api_call_taxonomy", None)
        if block is None:
            return {}
        if hasattr(block, "to_dict"):
            block = block.to_dict()
        if isinstance(block, dict):
            return {str(k).lower(): str(v) for k, v in block.items()}
    except Exception as exc:  # pragma: no cover
        logger.debug("api_call_taxonomy load failed: %s", exc)
    return {}


_TAXONOMY_CACHE: Optional[dict[str, str]] = None


def _taxonomy() -> dict[str, str]:
    global _TAXONOMY_CACHE
    if _TAXONOMY_CACHE is None:
        _TAXONOMY_CACHE = _load_taxonomy_from_settings()
    return _TAXONOMY_CACHE


def infer_service_name(
    url: str,
    *,
    overrides: Optional[Mapping[str, str]] = None,
) -> str:
    """Map a full URL to a stable, human-readable service id.

    Lookup order: ``overrides`` → settings taxonomy → host first label.
    """
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if not host:
        return "unknown"

    if overrides:
        if host in overrides:
            return overrides[host]
        for suffix, name in overrides.items():
            if host.endswith(suffix.lower()):
                return name

    tax = _taxonomy()
    if host in tax:
        return tax[host]
    for suffix, name in tax.items():
        if host.endswith(suffix):
            return name

    # Fallback: first label of the host (siv.walmart.com → "siv").
    return host.split(".", 1)[0] or host


# ── httpx ──────────────────────────────────────────────────────────────

def _build_httpx_transport_classes():
    """Lazy-build the httpx transport classes so importing this module
    does not require httpx. Returns ``(AsyncTransport, SyncTransport)``
    or ``(None, None)`` if httpx is not installed.
    """
    try:
        import httpx
    except ImportError:  # pragma: no cover
        return None, None

    from agent_factory.observability.api_call_recorder import record_api_call
    from agent_factory.observability.payload_capture import (
        capture_disabled_for,
        stash_request_bytes,
        stash_response_bytes,
    )

    class _AsyncTransport(httpx.AsyncHTTPTransport):
        """httpx async transport that emits one ``api_call`` per request.

        Also stashes request/response bytes onto the recorder dict (cheap,
        bounded) so the background ``_emit`` task can attach a redacted
        JSON preview to the event without adding latency on the caller's
        path.
        """

        def __init__(
            self,
            *args,
            service_overrides: Optional[Mapping[str, str]] = None,
            **kwargs,
        ):
            super().__init__(*args, **kwargs)
            self._overrides = service_overrides

        async def handle_async_request(self, request):  # type: ignore[override]
            url = str(request.url)
            service = infer_service_name(url, overrides=self._overrides)
            capture_off = capture_disabled_for(service)

            # Request bytes are already buffered by httpx — capturing them
            # is just a reference copy.
            req_bytes: Optional[bytes] = None
            req_ct: Optional[str] = None
            if not capture_off:
                try:
                    req_bytes = request.content
                    req_ct = request.headers.get("content-type")
                except Exception:
                    req_bytes = None

            async with record_api_call(
                service=service,
                endpoint=request.url.path or "/",
                method=request.method,
                domain_data={
                    "url": url,
                    "host": request.url.host,
                    "transport": "httpx",
                },
            ) as rec:
                if req_bytes:
                    stash_request_bytes(rec, content=req_bytes, content_type=req_ct)

                resp = await super().handle_async_request(request)
                rec["status_code"] = resp.status_code

                clen = resp.headers.get("content-length")
                if clen and clen.isdigit():
                    rec["response_bytes"] = int(clen)

                if not capture_off:
                    resp_ct = resp.headers.get("content-type", "")
                    # Pre-read JSON-ish responses so the background _emit
                    # task can attach a redacted preview. The caller will
                    # call .json() / .content next, which uses the same
                    # cached body — no extra network I/O, no added wall-
                    # clock. Binary / non-JSON content-types are skipped.
                    #
                    # A Content-Length above the safety cap (1 MB) skips
                    # the pre-read entirely; the preview marker still
                    # captures the byte count so the dashboard shows the
                    # call happened.
                    SAFETY_CAP = 1024 * 1024  # 1 MB hard ceiling
                    if "json" in (resp_ct or "").lower():
                        if clen and clen.isdigit() and int(clen) > SAFETY_CAP:
                            rec["response_preview"] = {
                                "_truncated": True, "_bytes": int(clen),
                            }
                        else:
                            try:
                                body = await resp.aread()  # caches into resp._content
                                stash_response_bytes(
                                    rec, content=body, content_type=resp_ct,
                                )
                            except Exception:
                                # Streaming/transport quirks — never
                                # break the caller.
                                pass
                return resp

    return _AsyncTransport, None  # sync transport TBD when needed


def InstrumentedHTTPXTransport(*args, **kwargs):  # noqa: N802 — class-like factory
    """Return an instrumented ``httpx.AsyncHTTPTransport``.

    Usage::

        client = httpx.AsyncClient(transport=InstrumentedHTTPXTransport(verify=False))

    Accepts a ``service_overrides`` kwarg (``Mapping[str, str]``) to
    pin specific hosts/suffixes to a service name, plus any standard
    ``httpx.AsyncHTTPTransport`` kwargs.
    """
    AsyncT, _ = _build_httpx_transport_classes()
    if AsyncT is None:
        raise ImportError(
            "httpx is not installed; install it to use InstrumentedHTTPXTransport."
        )
    return AsyncT(*args, **kwargs)
