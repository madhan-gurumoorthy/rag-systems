"""Analytics helpers — thin wrappers around ``event_store``.

Provides convenience functions for recording session-lifecycle analytics
events (dispatch, state transitions, error summaries) without callers
having to import ``event_store`` directly or construct the full
``append_event`` signature.

All writes are best-effort: failures are logged at WARNING and
swallowed so an analytics miss can never 500 a request.
"""
from __future__ import annotations

from typing import Any, Optional

try:
    from agent_factory.common.logging import get_logger
    logger = get_logger("storage.analytics")
except ImportError:  # pragma: no cover
    import logging
    logger = logging.getLogger("storage.analytics")


async def record_session_event(
    session_id: str,
    event_type: str,
    *,
    agent_id: str = "",
    tenant_id: str = "",
    work_item_id: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> Optional[str]:
    """Record a session-level analytics event via ``event_store``.

    Wraps ``event_store.append_event`` with a best-effort contract:
    failures are logged and swallowed so analytics never blocks the
    request path.

    Args:
        session_id: UUID string of the session thread.
        event_type: One of the canonical event types
            (``dispatch``, ``state``, ``error``, etc.).
        agent_id: Agent identity — required by the event schema but
            defaulted to ``""`` for callers that don't have it handy.
        tenant_id: Tenant axis — same contract as ``agent_id``.
        work_item_id: Optional work_item correlation.
        metadata: Arbitrary dict merged into ``domain_data``.

    Returns:
        The ``event_id`` string on success, ``None`` on failure.
    """
    try:
        from storage.event_store import event_store

        if not event_store.is_available:
            logger.debug(
                "analytics event skipped (store unavailable): "
                "%s session=%s",
                event_type, session_id[:8] if session_id else "?",
            )
            return None

        return await event_store.append_event(
            session_id=session_id,
            agent_id=agent_id,
            tenant_id=tenant_id,
            event_type=event_type,
            work_item_id=work_item_id,
            domain_data=metadata,
        )
    except Exception as exc:
        logger.warning(
            "analytics event failed (non-fatal): %s session=%s err=%s",
            event_type,
            session_id[:8] if session_id else "?",
            exc,
        )
        return None


async def record_token_usage(
    session_id: str,
    *,
    agent_id: str = "",
    tenant_id: str = "",
    work_item_id: Optional[str] = None,
    model_provider: Optional[str] = None,
    model_name: Optional[str] = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_creation_tokens: int = 0,
    reasoning_tokens: int = 0,
    llm_latency_ms: Optional[int] = None,
) -> Optional[str]:
    """Record an LLM token-usage event for cost accounting.

    Best-effort wrapper — failures are swallowed.
    """
    try:
        from storage.event_store import event_store

        if not event_store.is_available:
            return None

        return await event_store.append_event(
            session_id=session_id,
            agent_id=agent_id,
            tenant_id=tenant_id,
            event_type="llm",
            work_item_id=work_item_id,
            model_provider=model_provider,
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_creation_tokens=cache_creation_tokens,
            reasoning_tokens=reasoning_tokens,
            llm_latency_ms=llm_latency_ms,
        )
    except Exception as exc:
        logger.warning(
            "analytics token_usage failed (non-fatal): session=%s err=%s",
            session_id[:8] if session_id else "?",
            exc,
        )
        return None


__all__ = [
    "record_session_event",
    "record_token_usage",
]
