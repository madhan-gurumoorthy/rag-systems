"""Pack-local factory for instrumented HTTP clients.

Every outbound call from this pack goes through :func:`instrumented_httpx_client`
so each request is wrapped in the framework's auto instrumentation
(:mod:`agent_factory.observability.http_instrumentation`) and produces one
``api_call`` event row per upstream invocation — with redacted request /
response previews when the body is JSON.

Each service passes its own ``service_name`` so the resulting event's
``domain_data.service`` field is the canonical name the dashboard
groups by (``siv``, ``hat_path``, ``merloc``, etc.) rather than
something derived from the raw host header.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Optional

import httpx

from agent_factory.observability import InstrumentedHTTPXTransport


@asynccontextmanager
async def instrumented_httpx_client(
    *,
    service_name: str,
    verify: Any = True,
    timeout: Optional[float] = 15.0,
    **client_kwargs: Any,
) -> AsyncIterator[httpx.AsyncClient]:
    """Yield an ``httpx.AsyncClient`` whose requests emit ``api_call`` events.

    All requests issued through the returned client carry
    ``domain_data.service = service_name`` so the dashboard can group
    fan-out across heterogeneous hosts under one canonical name.
    """
    transport = InstrumentedHTTPXTransport(
        verify=verify,
        # Map any host this client touches to the canonical service name.
        service_overrides={"": service_name},
    )
    async with httpx.AsyncClient(
        transport=transport,
        verify=verify,
        timeout=timeout,
        **client_kwargs,
    ) as client:
        yield client
