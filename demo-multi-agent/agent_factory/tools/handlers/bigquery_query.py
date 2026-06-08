"""BigQuery query handler — runs parameterized BigQuery SQL.

Renders ``spec.query_template`` against the call params (with ``project``
and ``dataset`` auto-injected from the spec when not provided by the
caller), executes the query via the ``google-cloud-bigquery`` client, and
passes the row-set through the spec's response processor.

The ``google-cloud-bigquery`` package is imported lazily so packs that do
not use BigQuery do not have to install it.

YAML config (on the ``ToolSpec``)::

    type:            bigquery_query
    project:         "my-gcp-project"     # optional, falls back to ADC default
    dataset:         "warehouse"          # optional, injected as {{dataset}}
    query_template:  "SELECT * FROM `{{project}}.{{dataset}}.orders` WHERE id = '{{order_id}}'"
    response:
      processor:     count_rows           # or first_row, all_rows, ...

Return shape: whatever ``apply_processor`` yields, with ``count`` guaranteed.
"""
from __future__ import annotations

from typing import Any, TYPE_CHECKING

from ._base import ToolHandler
from ..executor import _render_template, logger

if TYPE_CHECKING:  # pragma: no cover
    from ..executor import ToolExecutor
    from ..pack_models import ToolSpec


class BigQueryQueryHandler(ToolHandler):
    type_name = "bigquery_query"

    async def execute(
        self,
        *,
        tool_id: str,
        spec: "ToolSpec",
        params: dict[str, Any],
        executor: "ToolExecutor",
    ) -> dict[str, Any]:
        if spec.type != "bigquery_query":
            return {"error": f"Tool '{tool_id}' is not a bigquery_query tool"}

        from ..response_processors import apply_processor

        # Inject project and dataset into params for template rendering
        enriched = {**params}
        if spec.project:
            enriched.setdefault("project", spec.project)
        if spec.dataset:
            enriched.setdefault("dataset", spec.dataset)

        query = _render_template(spec.query_template, enriched)

        try:
            from google.cloud import bigquery  # type: ignore

            client = bigquery.Client(project=spec.project or None)
            query_job = client.query(query)
            results = query_job.result()
            rows = [dict(row) for row in results]

            data = {"rows": rows, "count": len(rows)}

            result = apply_processor(
                spec.response.processor,
                data,
                spec.response,
                params,
            )
            if "count" not in result:
                result["count"] = len(rows)
            return result

        except ImportError:
            return {"error": "google-cloud-bigquery not installed"}
        except Exception as e:  # noqa: BLE001 — surface to caller
            logger.error(f"bigquery_query tool '{tool_id}' failed: {e}", exc_info=True)
            return {"error": str(e), **params}


__all__ = ["BigQueryQueryHandler"]
