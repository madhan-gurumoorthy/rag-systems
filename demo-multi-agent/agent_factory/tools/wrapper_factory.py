"""LangChain wrapper factories for declarative tools.

Builds the async callables that
:class:`langchain_core.tools.StructuredTool.from_function` will wrap
into a ``StructuredTool``.  LangChain introspects each wrapper's
``__signature__`` + ``__annotations__`` to generate the JSON schema
sent to the LLM, so every wrapper must have an explicit, typed
signature — plain ``**kwargs`` produces a schema with no properties
and the LLM cannot bind arguments.

Two wrapper shapes:

* :func:`build_typed_wrapper` — typed-param wrapper for any tool whose
  type has a registered :class:`~agent_factory.tools.handlers.ToolHandler`.
  Reads ``spec.params`` (from ``tools.yaml``) and builds an
  :class:`inspect.Signature` that mirrors them so LangChain emits the
  correct schema.  The body of the wrapper dispatches into the
  handler registry once at build time and stashes the handler reference
  in the closure, so the hot path is a single ``handler.execute(...)``
  call.

* :func:`build_batch_wrapper` — single-string wrapper for the
  ``batch`` tool type.  Batch tools take a JSON-encoded list of
  parameter dicts and fan them out in parallel, so their schema is
  uniform (``items: str``) regardless of the underlying tool.

Both factories live at module scope (not as instance methods on
:class:`~agent_factory.tools.executor.ToolExecutor`) so they can be
exercised in isolation without standing up a full executor instance.
The executor's :meth:`_resolve_all` calls them directly.
"""
from __future__ import annotations

import inspect
import json
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .executor import ToolExecutor
    from ..pack_models import ToolSpec


# LangChain's ``StructuredTool.from_function`` and
# ``create_tool_calling_agent`` introspect the wrapper's
# ``__signature__`` + ``__annotations__`` to build the JSON schema
# sent to the LLM, so every wrapper needs an explicit typed signature
# (NOT plain ``**kwargs``).
_PARAM_TYPE_MAP: dict[str, type] = {
    "str": str,
    "string": str,
    "int": int,
    "integer": int,
    "float": float,
    "number": float,
    "bool": bool,
    "boolean": bool,
}


def build_typed_wrapper(
    tool_id: str,
    spec: "ToolSpec",
    executor: "ToolExecutor",
) -> Callable:
    """Build an async wrapper with explicit typed parameters.

    LangChain's ``StructuredTool.from_function`` introspects the
    function signature to build the JSON schema sent to the LLM.
    Every parameter must have a matching type hint — plain
    ``**kwargs`` produces a schema with no properties and the LLM
    cannot bind arguments.

    Reads ``spec.params`` (from ``tools.yaml``) and dynamically sets
    ``__signature__`` and ``__annotations__`` so LangChain can
    generate the correct JSON schema.

    The wrapper dispatches through the handler registry.  At
    wrapper-build time we resolve and stash the handler reference so
    the hot path is a single ``handler.execute(...)`` call — no
    per-invocation registry lookup.

    Raises
    ------
    ValueError
        If no :class:`ToolHandler` is registered for ``spec.type``.
    """
    # Lazy import — handlers/__init__.py pulls from executor at import
    # time, and executor imports this module, so a module-level import
    # would create a cycle.
    from .handlers import get_handler
    from .executor import logger

    handler = get_handler(spec.type)
    if handler is None:
        raise ValueError(f"No handler registered for tool type '{spec.type}'")

    async def tool_fn(**kwargs) -> str:
        logger.info(f"[DEBUG] Tool invoked: {tool_id} type={spec.type} params={list(kwargs.keys())}")
        try:
            result = await handler.execute(
                tool_id=tool_id, spec=spec, params=kwargs, executor=executor,
            )
            logger.info(f"[DEBUG] Tool {tool_id} completed: status={'ok' if 'error' not in str(result).lower() else 'error'}")
        except Exception as e:
            logger.error(f"[DEBUG] Tool {tool_id} EXCEPTION: {type(e).__name__}: {e}")
            raise
        return json.dumps(result, default=str)

    tool_fn.__name__ = tool_id.replace("-", "_").lower()
    tool_fn.__doc__ = spec.description or f"{spec.type} tool: {tool_id}"

    # Build typed signature from spec.params for LangChain introspection
    if spec.params:
        parameters = []
        annotations: dict[str, Any] = {"return": str}
        for p in spec.params:
            py_type = _PARAM_TYPE_MAP.get(p.type, str)
            annotations[p.name] = py_type
            if p.required and p.default is None:
                param = inspect.Parameter(
                    p.name,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    annotation=py_type,
                )
            else:
                param = inspect.Parameter(
                    p.name,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    default=p.default if p.default is not None else "",
                    annotation=py_type,
                )
            parameters.append(param)
        tool_fn.__signature__ = inspect.Signature(
            parameters=parameters, return_annotation=str,
        )
        tool_fn.__annotations__ = annotations
    else:
        # Fallback: single generic query parameter so LangChain has something
        tool_fn.__signature__ = inspect.Signature(
            parameters=[
                inspect.Parameter(
                    "query", inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    annotation=str, default="",
                ),
            ],
            return_annotation=str,
        )
        tool_fn.__annotations__ = {"query": str, "return": str}

    return tool_fn


def build_batch_wrapper(
    tool_id: str,
    spec: "ToolSpec",
    executor: "ToolExecutor",
) -> Callable:
    """Create an async callable wrapper for a batch tool.

    The batch tool runs another tool in parallel for multiple
    parameter sets.  Caller passes ``items`` as a JSON-encoded list of
    param dicts.
    """

    async def batch_tool(items: str) -> str:
        result = await executor.execute_batch(tool_id, items)
        return json.dumps(result, default=str)

    batch_tool.__name__ = tool_id.replace("-", "_").lower()
    batch_tool.__doc__ = spec.description or f"Batch tool: {tool_id}"
    return batch_tool


__all__ = ["build_typed_wrapper", "build_batch_wrapper"]
