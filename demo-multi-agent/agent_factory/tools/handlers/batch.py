"""Batch handler — fan-out runner for another tool.

Runs a single target tool in parallel for a list of parameter dicts,
bounded by ``spec.max_concurrency``.  Used by packs that need to
sweep a check across many candidates (e.g. "validate dimensions for
each line item on this order").

The handler invokes the target tool through the executor's resolved
callable registry (:meth:`ToolExecutor.get_callable`) — that lets a
``python_function`` tool, an ``http_api`` tool, or any other type be
batched without the batch handler caring which.

Calling convention (set by :meth:`ToolExecutor._make_batch_wrapper`):

  * The LLM's tool call passes a single ``items`` arg, a JSON-encoded
    list of param dicts.
  * The wrapper forwards it as ``params["items_json"]`` so this
    handler can match the standard ``execute(*, params=...)`` ABC
    signature.

Return shape::

    {
        "total":     N,
        "succeeded": K,
        "failed":    N - K,
        "results":   [{"index": 0, "result": ...}, ...],   # in index order
        "errors":    [{"index": 3, "error": "...", "params": {...}}, ...],
    }
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Callable, TYPE_CHECKING

from ._base import ToolHandler

if TYPE_CHECKING:  # pragma: no cover
    from ..executor import ToolExecutor
    from ..pack_models import ToolSpec


class BatchHandler(ToolHandler):
    type_name = "batch"

    async def execute(
        self,
        *,
        tool_id: str,
        spec: "ToolSpec",
        params: dict[str, Any],
        executor: "ToolExecutor",
    ) -> dict[str, Any]:
        if spec.type != "batch":
            return {"error": f"Tool '{tool_id}' is not a batch tool"}

        target_tool = executor.get_callable(spec.batch_tool_id)
        if not target_tool:
            return {
                "error": f"Batch target tool '{spec.batch_tool_id}' not resolved"
            }

        items_json = params.get("items_json", params.get("items", "[]"))
        try:
            items = json.loads(items_json) if isinstance(items_json, str) else items_json
        except json.JSONDecodeError:
            return {"error": "items must be a JSON-encoded list of param dicts"}

        if not isinstance(items, list):
            return {"error": "items must be a list"}

        semaphore = asyncio.Semaphore(spec.max_concurrency)
        results: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []

        async def run_one(item_params: dict, index: int) -> None:
            async with semaphore:
                try:
                    if isinstance(target_tool, Callable):
                        result = await target_tool(**item_params)
                        results.append({"index": index, "result": result})
                except Exception as exc:  # noqa: BLE001 — fan-out swallow + surface
                    errors.append(
                        {"index": index, "error": str(exc), "params": item_params}
                    )

        tasks = [run_one(item, i) for i, item in enumerate(items)]
        await asyncio.gather(*tasks, return_exceptions=True)

        return {
            "total": len(items),
            "succeeded": len(results),
            "failed": len(errors),
            "results": sorted(results, key=lambda r: r["index"]),
            "errors": sorted(errors, key=lambda e: e["index"]),
        }


__all__ = ["BatchHandler"]
