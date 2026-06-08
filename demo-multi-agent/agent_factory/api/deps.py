"""Shared FastAPI dependencies / helpers used by route modules.

Pure functions only — no FastAPI state, no module-level side effects.
Each helper is callable from within a request handler and may raise
``HTTPException`` for client-facing errors.
"""
from __future__ import annotations

from typing import Optional

from fastapi import HTTPException

from agent_factory.registry import pack_registry


def resolve_tenant_id(header_value: Optional[str]) -> str:
    """Resolve tenant ID from request header, then pack default, then 400.

    Resolution order:
    1. ``X-Tenant-Id`` header (trimmed, non-empty wins)
    2. ``PackConfig.tenant_id`` on the active pack
    3. HTTP 400 — tenant ID is mandatory
    """
    header = (header_value or "").strip()
    if header:
        return header

    active_pack = pack_registry.get_pack()
    pack_default = ""
    if active_pack is not None:
        pack_default = (getattr(active_pack.config, "tenant_id", "") or "").strip()

    if pack_default:
        return pack_default

    raise HTTPException(
        status_code=400,
        detail=(
            "tenant_id is required: send X-Tenant-Id header or configure "
            "PackConfig.tenant_id on the active pack"
        ),
    )


def parse_trace_id_from_traceparent(traceparent: Optional[str]) -> Optional[str]:
    """Extract the 32-hex ``trace_id`` from a W3C ``traceparent`` header.

    Format: ``00-{trace_id:32hex}-{span_id:16hex}-{flags:2hex}``.

    Returns ``None`` when the header is missing, malformed, or the
    ``trace_id`` portion is the all-zeros sentinel (per W3C §3.2.2.3, an
    invalid trace_id MUST be treated as if no traceparent had been
    received).
    """
    if not traceparent:
        return None
    parts = traceparent.split("-")
    if len(parts) < 3:
        return None
    tid = parts[1]
    if len(tid) != 32 or tid == "0" * 32:
        return None
    return tid


__all__ = ["resolve_tenant_id", "parse_trace_id_from_traceparent"]
