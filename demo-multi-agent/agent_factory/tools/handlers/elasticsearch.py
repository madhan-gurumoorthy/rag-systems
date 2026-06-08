"""Elasticsearch handler — declarative ES/OpenSearch queries over httpx.

Resolves connection details from Dynaconf via ``spec.es_connection``,
renders the index template + query DSL against the call params, and
POSTs to ``{es_url}/{index}/_search``.  The hit-set is normalised into
``{rows, count, total, took_ms}`` for the response processor.

Auth resolution order (first match wins):

  1. Headers produced by :func:`_resolve_auth_headers` from ``spec.auth``.
  2. Basic auth built from ``conn_cfg.username`` + ``conn_cfg.password``
     (or the ``ES_USER`` / ``ES_PASSWORD`` legacy field names).
  3. API-key auth from ``conn_cfg.api_key`` (or ``ES_API_KEY``).

YAML config (on the ``ToolSpec``)::

    type:                  elasticsearch
    es_connection:         logs_cluster        # Dynaconf section name
    es_index_template:     "logs-{{tenant}}-*"
    es_query_template:     {query: {match: {message: "{{search}}"}}}
    es_size:               25
    es_sort:               [{timestamp: "desc"}]
    es_source_fields:      ["timestamp", "message", "severity"]
    response:
      processor:           all_rows
      error_outcomes:      {default: ES_DOWN}

The handler reaches back through ``executor._enrich_params_from_templates``
and ``executor._get_ssl_context`` — both stay as instance methods on
:class:`~agent_factory.tools.executor.ToolExecutor` because tests patch
them directly.
"""
from __future__ import annotations

import json
from typing import Any, TYPE_CHECKING

from ._base import ToolHandler
from ..executor import _render_template, _resolve_auth_headers, logger

if TYPE_CHECKING:  # pragma: no cover
    from ..executor import ToolExecutor
    from ..pack_models import ToolSpec


class ElasticsearchHandler(ToolHandler):
    type_name = "elasticsearch"

    async def execute(
        self,
        *,
        tool_id: str,
        spec: "ToolSpec",
        params: dict[str, Any],
        executor: "ToolExecutor",
    ) -> dict[str, Any]:
        if spec.type != "elasticsearch":
            return {"error": f"Tool '{tool_id}' is not an elasticsearch tool"}

        import httpx
        from ..response_processors import apply_processor
        from agent_factory.infrastructure.settings import get_config

        config = get_config()
        conn_cfg = (
            getattr(config, spec.es_connection, None)
            if spec.es_connection else None
        )
        if not conn_cfg:
            return {
                "error": f"Elasticsearch connection '{spec.es_connection}' not configured"
            }

        enriched = executor._enrich_params_from_templates(params, [
            spec.es_index_template,
            json.dumps(spec.es_query_template) if spec.es_query_template else "",
        ])

        # Resolve connection details
        es_url = getattr(conn_cfg, "url", "") or getattr(conn_cfg, "ES_URL", "")
        if not es_url:
            hosts = getattr(conn_cfg, "hosts", "") or getattr(conn_cfg, "ES_HOSTS", "")
            if hosts:
                es_url = hosts.split(",")[0].strip()
        if not es_url:
            return {"error": "Elasticsearch URL not configured"}

        index = (
            _render_template(spec.es_index_template, enriched)
            if spec.es_index_template else "*"
        )

        # Build query body from DSL template
        if spec.es_query_template:
            query_str = json.dumps(spec.es_query_template)
            query_str = _render_template(query_str, enriched)
            query_body = json.loads(query_str)
        else:
            # Fallback: match_all or simple query_string
            search_text = enriched.get("query", enriched.get("q", "*"))
            query_body = {"query": {"query_string": {"query": search_text}}}

        # Add size, sort, _source
        query_body["size"] = spec.es_size
        if spec.es_sort:
            sort_str = json.dumps(spec.es_sort)
            sort_str = _render_template(sort_str, enriched)
            query_body["sort"] = json.loads(sort_str)
        if spec.es_source_fields:
            query_body["_source"] = spec.es_source_fields

        # Build headers + auth
        headers = {"Content-Type": "application/json"}
        auth_headers = _resolve_auth_headers(spec.auth, enriched)
        headers.update(auth_headers)

        # Fallback: basic auth from connection config
        if "Authorization" not in headers:
            import base64
            username = getattr(conn_cfg, "username", "") or getattr(conn_cfg, "ES_USER", "")
            password = getattr(conn_cfg, "password", "") or getattr(conn_cfg, "ES_PASSWORD", "")
            if username:
                encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
                headers["Authorization"] = f"Basic {encoded}"
            # Also check for API key auth
            api_key = getattr(conn_cfg, "api_key", "") or getattr(conn_cfg, "ES_API_KEY", "")
            if api_key:
                headers["Authorization"] = f"ApiKey {api_key}"

        try:
            verify = executor._get_ssl_context()
            search_url = f"{es_url.rstrip('/')}/{index}/_search"

            async with httpx.AsyncClient(timeout=spec.timeout_seconds, verify=verify) as client:
                resp = await client.post(search_url, json=query_body, headers=headers)
                resp.raise_for_status()
                es_data = resp.json()

            # Normalize ES response
            hits = es_data.get("hits", {})
            total = hits.get("total", {})
            total_count = total.get("value", 0) if isinstance(total, dict) else total
            records = [
                {**hit.get("_source", {}), "_id": hit.get("_id"), "_score": hit.get("_score")}
                for hit in hits.get("hits", [])
            ]

            data = {
                "rows": records,
                "count": len(records),
                "total": total_count,
                "took_ms": es_data.get("took", 0),
            }

            result = apply_processor(
                spec.response.processor, data, spec.response, params,
            )
            if "count" not in result:
                result["count"] = len(records)
            if "total" not in result:
                result["total"] = total_count
            return result

        except httpx.HTTPStatusError as e:
            status_code = str(e.response.status_code)
            error_outcomes = spec.response.error_outcomes
            outcome = error_outcomes.get(status_code) or error_outcomes.get("default")
            if outcome:
                return {"outcome": outcome, "error": f"ES HTTP {status_code}", **params}
            return {"error": f"ES HTTP {status_code}: {e.response.text[:500]}", **params}
        except Exception as e:  # noqa: BLE001 — surface to caller
            error_outcomes = spec.response.error_outcomes
            outcome = error_outcomes.get("default")
            if outcome:
                return {"outcome": outcome, "error": str(e), **params}
            logger.error(f"elasticsearch tool '{tool_id}' failed: {e}", exc_info=True)
            return {"error": str(e), **params}


__all__ = ["ElasticsearchHandler"]
