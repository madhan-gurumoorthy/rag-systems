"""A2A (agent-to-agent) handler — declarative wrapper over ``AgentClient``.

Bridges YAML-defined a2a tools to
:class:`agent_factory.common.agent_comm.AgentClient`, the common
HTTP/SSE client that handles trace propagation, retries, and SSE
streaming for cross-agent calls.

Responsibilities:

  * Resolve ``{{KEY}}`` references in the target URL and payload template
    by reaching back to the executor's ``_enrich_params_from_templates``
    helper (which pulls values from Dynaconf).
  * Render the rendered URL + JSON payload via
    :func:`agent_factory.tools.executor._render_template`.
  * Compute auth headers via
    :func:`agent_factory.tools.executor._resolve_auth_headers`.
  * Generate a UUID4 session id when none is provided.
  * Choose between ``client.invoke`` (request/response) and
    ``client.invoke_stream`` (SSE) based on ``spec.a2a_stream``.
  * Pass the resulting data through the spec's response processor.
  * Surface ``error_outcomes.default`` when set, otherwise return a plain
    error envelope.

This handler relies on the executor's ``_enrich_params_from_templates``
instance method — that lookup is why the
:class:`~agent_factory.tools.handlers._base.ToolHandler` contract carries
an ``executor`` back-reference.
"""
from __future__ import annotations

import json
from typing import Any, TYPE_CHECKING

from ._base import ToolHandler
from ..executor import _render_template, _resolve_auth_headers, logger

if TYPE_CHECKING:  # pragma: no cover
    from ..executor import ToolExecutor
    from ..pack_models import ToolSpec


class A2AHandler(ToolHandler):
    type_name = "a2a"

    async def execute(
        self,
        *,
        tool_id: str,
        spec: "ToolSpec",
        params: dict[str, Any],
        executor: "ToolExecutor",
    ) -> dict[str, Any]:
        if spec.type != "a2a":
            return {"error": f"Tool '{tool_id}' is not an a2a tool"}

        from ..response_processors import apply_processor

        enriched_params = executor._enrich_params_from_templates(params, [
            spec.target_agent_url,
            *[str(v) for v in spec.a2a_payload_template.values()],
        ])

        # Render target URL
        url = _render_template(spec.target_agent_url, enriched_params)

        # Build payload from template
        payload: dict[str, Any] = {}
        if spec.a2a_payload_template:
            payload_str = json.dumps(spec.a2a_payload_template)
            payload_str = _render_template(payload_str, enriched_params)
            payload = json.loads(payload_str)

        # Resolve session_id from params or generate one
        session_id = ""
        if spec.a2a_session_field and spec.a2a_session_field in enriched_params:
            session_id = str(enriched_params[spec.a2a_session_field])
        if not session_id:
            import uuid
            session_id = str(uuid.uuid4())

        # Resolve auth headers for the A2A call
        auth_headers = _resolve_auth_headers(spec.auth, enriched_params)

        try:
            from agent_factory.common.agent_comm import AgentClient

            client = AgentClient(
                timeout=float(spec.timeout_seconds),
                base_headers=auth_headers,
            )

            if spec.a2a_stream:
                # Streaming: collect all chunks into a combined result
                chunks: list[str] = []
                async for chunk in client.invoke_stream(
                    target_agent_url=url,
                    payload=payload,
                    session_id=session_id,
                    user_id=enriched_params.get("user_id"),
                ):
                    chunks.append(chunk)

                # Try to parse the last chunk as JSON for processing
                combined = "\n".join(chunks)
                try:
                    data = json.loads(combined)
                except (json.JSONDecodeError, ValueError):
                    data = {"text": combined}
            else:
                response = await client.invoke(
                    target_agent_url=url,
                    payload=payload,
                    session_id=session_id,
                    user_id=enriched_params.get("user_id"),
                )
                data = response.get("data", response)

            # Apply response processor
            result = apply_processor(
                spec.response.processor, data, spec.response, params,
            )
            result["session_id"] = session_id
            return result

        except ImportError:
            return {"error": "utils.agent_client not available"}
        except Exception as e:  # noqa: BLE001 — surface to caller
            error_outcomes = spec.response.error_outcomes
            outcome = error_outcomes.get("default")
            if outcome:
                return {"outcome": outcome, "error": str(e), **params}
            logger.error(f"a2a tool '{tool_id}' failed: {e}", exc_info=True)
            return {"error": str(e), **params}


__all__ = ["A2AHandler"]
