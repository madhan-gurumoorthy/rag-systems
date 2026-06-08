"""Shared response/event helpers for the API layer."""
from __future__ import annotations

import json
from datetime import datetime

from agent_factory.api.schemas import StreamEvent


def create_stream_event(event_type: str, seq: int, data: dict) -> str:
    """Serialise a ``StreamEvent`` into an SSE-compatible payload string.

    Format: ``"data: {<json>}\\n\\n"``.  Used by the streaming chat
    endpoint to push tokens, progress, and lifecycle events to clients.
    """
    event = StreamEvent(
        event=event_type,
        seq=seq,
        ts=datetime.utcnow().isoformat() + 'Z',
        data=data,
    )
    return f"data: {json.dumps(event.model_dump(), default=str)}\n\n"


__all__ = ["create_stream_event"]
