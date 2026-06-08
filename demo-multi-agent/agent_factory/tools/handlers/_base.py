"""Base class for declarative-tool handlers.

The tool executor in :mod:`agent_factory.tools.executor` historically
held one ``execute_<type>`` method per tool type — 14 of them, totaling
~1.7k lines of business logic in a single class.  The handler-registry
pattern splits each one into its own module so that:

  * Adding a new tool type means dropping a new file under
    ``agent_factory/tools/handlers/`` and registering it once — no edits
    to the executor (OCP).
  * Each handler is independently testable without booting the full
    executor + pack-loader chain.
  * Module-level imports of heavy clients (aiohttp, pyodbc, kafka,
    confluent_kafka, snowflake-connector-python, …) move into the
    handler that needs them — cold-start time for packs that don't
    use that type drops.

Handlers are *stateless*.  All per-tool config lives on the
:class:`agent_factory.pack_models.ToolSpec`; all per-call inputs live
in the ``params`` dict.  The executor passes itself in as well so
handlers can reach cross-cutting helpers (auth resolution, response
shaping, retry config) without duplicating them.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - import-cycle guard
    from ..executor import ToolExecutor
    from ..pack_models import ToolSpec


class ToolHandler(ABC):
    """Base class for a single tool-type handler.

    Subclasses MUST set ``type_name`` to the string value matching
    :attr:`ToolSpec.type` and implement :meth:`execute`.
    """

    #: The string value of ``ToolSpec.type`` this handler owns.
    type_name: str = ""

    @abstractmethod
    async def execute(
        self,
        *,
        tool_id: str,
        spec: "ToolSpec",
        params: dict[str, Any],
        executor: "ToolExecutor",
    ) -> Any:
        """Run the tool and return the raw result.

        The executor is responsible for any post-processing (outcome
        derivation, response shaping, serialisation for the LLM) — the
        handler returns the raw business-logic payload.

        Implementations MUST be safe to call concurrently with the
        same instance; handler instances are shared across the
        executor's lifetime.
        """
        raise NotImplementedError


__all__ = ["ToolHandler"]
