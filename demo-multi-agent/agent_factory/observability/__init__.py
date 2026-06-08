"""Observability primitives for the agent runtime.

Exposes:

* ``record_api_call``  — async context manager that emits one ``api_call``
  ``event`` row per outbound upstream invocation (REST / BigQuery / Kafka /
  anything).
* ``set_request_context`` — populates the contextvars that scope every
  ``api_call`` event to the active session / agent / tenant / work item /
  parent tool call.
* ``InstrumentedHTTPXTransport`` — drop-in ``httpx.AsyncHTTPTransport``
  subclass that turns every outbound request into an ``api_call`` event
  automatically, with bounded redacted request/response previews.

Pack-agnostic by contract — no domain vocabulary leaks in here.
"""
from agent_factory.observability.api_call_recorder import (
    ET_API_CALL,
    record_api_call,
    set_request_context,
    clear_request_context,
    current_context,
)
from agent_factory.observability.http_instrumentation import (
    InstrumentedHTTPXTransport,
    infer_service_name,
)

__all__ = [
    "ET_API_CALL",
    "record_api_call",
    "set_request_context",
    "clear_request_context",
    "current_context",
    "InstrumentedHTTPXTransport",
    "infer_service_name",
]
