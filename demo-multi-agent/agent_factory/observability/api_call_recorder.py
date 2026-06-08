"""Per-upstream-call event recording.

Every outbound REST call, BigQuery query, Kafka publish, or other upstream
invocation should be wrapped in :func:`record_api_call` so a row appears
in the ``event`` table with ``event_type = 'api_call'``. The dashboard
then renders the full fan-out under each owning tool, rather than the
single aggregate ``tool`` row LangGraph emits on ``on_tool_end``.

Identity (session / agent / tenant / work item / parent tool call) is
carried via contextvars seeded once per request by the dispatcher, so
nothing has to thread these arguments through every service call.
"""
from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Any, AsyncIterator, Optional

try:
    from agent_factory.common.logging import get_logger
    logger = get_logger("observability.api_call_recorder")
except ImportError:  # pragma: no cover
    import logging
    logger = logging.getLogger("observability.api_call_recorder")


ET_API_CALL = "api_call"


# ── Contextvars ────────────────────────────────────────────────────────
# Set by the dispatcher (api/invoke_dispatcher.py) before tool execution.
# Read by record_api_call (and the auto HTTP transports) when emitting.
_session_ctx:   ContextVar[Optional[str]] = ContextVar("af_session_id",   default=None)
_agent_ctx:     ContextVar[Optional[str]] = ContextVar("af_agent_id",     default=None)
_tenant_ctx:    ContextVar[Optional[str]] = ContextVar("af_tenant_id",    default=None)
_work_item_ctx: ContextVar[Optional[str]] = ContextVar("af_work_item_id", default=None)
_tool_call_ctx: ContextVar[Optional[str]] = ContextVar("af_tool_call_id", default=None)


def set_request_context(
    *,
    session_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    work_item_id: Optional[str] = None,
    tool_call_id: Optional[str] = None,
) -> dict:
    """Populate the per-request contextvars. Returns the prior values so
    the caller can restore them (typically via :func:`clear_request_context`).

    Each argument is optional; ``None`` leaves the slot unchanged. To
    explicitly clear a slot, pass the empty string ``""``.
    """
    prior = {
        "session_id":   _session_ctx.get(),
        "agent_id":     _agent_ctx.get(),
        "tenant_id":    _tenant_ctx.get(),
        "work_item_id": _work_item_ctx.get(),
        "tool_call_id": _tool_call_ctx.get(),
    }
    if session_id   is not None: _session_ctx.set(session_id   or None)
    if agent_id     is not None: _agent_ctx.set(agent_id       or None)
    if tenant_id    is not None: _tenant_ctx.set(tenant_id     or None)
    if work_item_id is not None: _work_item_ctx.set(work_item_id or None)
    if tool_call_id is not None: _tool_call_ctx.set(tool_call_id or None)
    return prior


def clear_request_context(prior: Optional[dict] = None) -> None:
    """Restore contextvars to the snapshot returned by
    :func:`set_request_context`, or clear them entirely when ``prior`` is
    omitted.
    """
    if prior is None:
        _session_ctx.set(None)
        _agent_ctx.set(None)
        _tenant_ctx.set(None)
        _work_item_ctx.set(None)
        _tool_call_ctx.set(None)
        return
    _session_ctx.set(prior.get("session_id"))
    _agent_ctx.set(prior.get("agent_id"))
    _tenant_ctx.set(prior.get("tenant_id"))
    _work_item_ctx.set(prior.get("work_item_id"))
    _tool_call_ctx.set(prior.get("tool_call_id"))


def current_context() -> dict:
    """Read the active contextvars (for callers that need to forward them
    explicitly — e.g. when spawning a thread or process where the
    contextvars do not propagate)."""
    return {
        "session_id":   _session_ctx.get(),
        "agent_id":     _agent_ctx.get(),
        "tenant_id":    _tenant_ctx.get(),
        "work_item_id": _work_item_ctx.get(),
        "tool_call_id": _tool_call_ctx.get(),
    }


# ── The recorder ───────────────────────────────────────────────────────

@asynccontextmanager
async def record_api_call(
    service: str,
    endpoint: str,
    *,
    method: str = "GET",
    domain_data: Optional[dict] = None,
) -> AsyncIterator[dict]:
    """Time the wrapped block and emit one ``api_call`` event on exit.

    The yielded dict is mutable — callers populate it with whatever
    transport-specific fields they have (``status_code``, ``response_bytes``,
    ``row_count``, ``bytes_billed``, ``error``, etc.) and those are merged
    into ``domain_data`` before the event is written.

    Example::

        async with record_api_call("siv", "/offer/specs", method="GET",
                                   domain_data={"offer_id": offer_id}) as rec:
            resp = await client.get(url)
            rec["status_code"] = resp.status_code
            rec["response_bytes"] = len(resp.content)

    Best-effort: any failure inside the recorder is swallowed so a
    bookkeeping bug cannot break the tool. If the originating call
    raises, the exception propagates unchanged after the event is logged
    with ``error`` populated.
    """
    rec: dict = {}
    started_at = time.time()
    started = time.perf_counter()
    err: Optional[BaseException] = None
    try:
        yield rec
    except BaseException as exc:  # noqa: BLE001 — we re-raise unchanged
        err = exc
        rec.setdefault("error", repr(exc))
        raise
    finally:
        latency_ms = int((time.perf_counter() - started) * 1000)
        # Fire-and-forget — never block the upstream call on event persistence.
        # The DB insert runs on the event loop concurrently with whatever the
        # caller does next.  See ``_schedule_emit`` for the shutdown drain
        # hook (``await drain_pending_api_call_events()`` to flush before
        # process exit).
        _schedule_emit(
            service=service,
            endpoint=endpoint,
            method=method,
            started_at=started_at,
            latency_ms=latency_ms,
            domain_data=domain_data,
            extra=rec,
            errored=err is not None,
        )


# Tracks scheduled emit tasks so callers (the dispatcher) can drain them
# at the end of a request or on shutdown. WeakSet-style — we discard the
# task reference as soon as it completes.
_pending_emits: set[asyncio.Task] = set()


def _schedule_emit(**kwargs: Any) -> None:
    """Schedule an ``_emit`` call without awaiting it.

    Falls back to a synchronous swallow if there is no running event loop
    (e.g. unit tests calling :func:`record_api_call` outside an async
    context). In that case nothing is persisted, which is the right
    behaviour — there's no DB connection pool to talk to anyway.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    task = loop.create_task(_emit(**kwargs))
    _pending_emits.add(task)
    task.add_done_callback(_pending_emits.discard)


async def drain_pending_api_call_events(timeout: float = 5.0) -> None:
    """Await any in-flight ``api_call`` event writes.

    Call this at request shutdown (or process shutdown) when you need
    to guarantee that every fire-and-forget insert has landed. Returns
    silently after ``timeout`` seconds if some inserts are still pending
    — those events are dropped rather than blocking forever.
    """
    if not _pending_emits:
        return
    try:
        await asyncio.wait_for(
            asyncio.gather(*list(_pending_emits), return_exceptions=True),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "drain_pending_api_call_events timed out with %d task(s) still pending",
            len(_pending_emits),
        )


async def _emit(
    *,
    service: str,
    endpoint: str,
    method: str,
    started_at: float,
    latency_ms: int,
    domain_data: Optional[dict],
    extra: dict,
    errored: bool,
) -> None:
    """Write a single ``api_call`` row. Best-effort — never raises."""
    try:
        from storage.event_store import event_store
    except Exception as exc:  # pragma: no cover — import error path
        logger.warning("api_call event skipped (event_store import): %s", exc)
        return

    if not getattr(event_store, "is_available", False):
        return

    ctx = current_context()
    session_id   = ctx["session_id"]
    agent_id     = ctx["agent_id"]
    tenant_id    = ctx["tenant_id"]
    work_item_id = ctx["work_item_id"]
    tool_call_id = ctx["tool_call_id"]

    # All three are NOT NULL on the event table. Skip silently if the
    # caller forgot to seed the contextvars — better to drop the row
    # than to crash the upstream call.
    if not (session_id and agent_id and tenant_id):
        return

    merged: dict[str, Any] = {
        "service":    service,
        "endpoint":   endpoint,
        "method":     method.upper(),
        "errored":    errored,
        "started_at": started_at,
        "latency_ms": latency_ms,
    }
    if tool_call_id:
        merged["parent_tool_call_id"] = tool_call_id
    if domain_data:
        merged.update(domain_data)
    if extra:
        merged.update(extra)

    # Heavy work — JSON parse + PII redaction of any stashed payload
    # bytes — runs HERE (background task), not on the caller's path.
    try:
        from agent_factory.observability.payload_capture import finalize_preview
        finalize_preview(merged)
    except Exception as exc:  # pragma: no cover — best-effort
        logger.debug("finalize_preview failed: %s", exc)

    try:
        await event_store.append_event(
            session_id=session_id,
            agent_id=agent_id,
            tenant_id=tenant_id,
            event_type=ET_API_CALL,
            work_item_id=work_item_id,
            tool_latency_ms=latency_ms,
            domain_data=merged,
        )
    except Exception as exc:  # pragma: no cover — best-effort path
        logger.warning("api_call event append failed (%s %s): %s",
                       service, endpoint, exc)
