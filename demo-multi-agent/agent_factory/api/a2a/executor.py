"""A2A AgentExecutor that runs matbot's chat pipeline.

For every inbound A2A message the executor:

  1. Resolves the target pack from ``metadata.agent_id`` / ``metadata.skill_id``
     (falls back to the registry default).
  2. Uses the A2A ``context_id`` as the matbot ``session_id`` so multi-turn
     history flows through the existing ``session`` / ``event`` tables.
  3. Calls :func:`agent_factory.langchain_chat.run_chat` (sync) or
     :func:`run_chat_stream` (streaming) and forwards the response to A2A
     as a Task artifact + completion event.
  4. Persists the dispatch / tool / llm events via
     :mod:`agent_factory.api.chat_persistence` so dashboards keep working.

Streaming detection: the underlying queue exposes the SDK's
``AsyncEventQueue`` for ``message/stream`` and the plain queue for
``message/send``.  We forward each chunk via ``TaskUpdater.update_status``
in the streaming case; otherwise we wait for the full response and emit
a single artifact + ``complete``.
"""
from __future__ import annotations

import time
import uuid
from typing import Any

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import TaskState
from a2a.utils import new_agent_text_message, new_task, new_text_artifact

from agent_factory.api.chat_persistence import (
    ensure_session,
    load_chat_history,
    write_dispatch_event,
    write_llm_event,
    write_tool_events,
)
from agent_factory.common.logging import (
    get_logger,
    log_operation_timing,
    set_full_context,
)
from agent_factory.common.tracing import traced_operation
from agent_factory.infrastructure.settings import get_config
from agent_factory.observability import (
    clear_request_context,
    set_request_context,
)
from agent_factory.registry import pack_registry

logger = get_logger("agent_factory_api.a2a.executor")


def _merge_request_metadata(context: RequestContext, message: Any) -> dict[str, Any]:
    """Collect metadata from every plausible A2A surface in priority order.

    Later sources win.  Per the A2A spec, message metadata is more
    specific than request metadata, so we read it last.
    """
    merged: dict[str, Any] = {}

    ctx_meta = getattr(context, "metadata", None)
    if isinstance(ctx_meta, dict):
        merged.update(ctx_meta)

    params = getattr(context, "params", None)
    if isinstance(params, dict) and isinstance(params.get("metadata"), dict):
        merged.update(params["metadata"])

    request_obj = getattr(context, "request", None)
    if isinstance(request_obj, dict) and isinstance(request_obj.get("params"), dict):
        req_params = request_obj["params"]
        if isinstance(req_params.get("metadata"), dict):
            merged.update(req_params["metadata"])

    call_context = getattr(context, "call_context", None)
    call_state = getattr(call_context, "state", None) if call_context is not None else None
    if isinstance(call_state, dict) and isinstance(call_state.get("metadata"), dict):
        merged.update(call_state["metadata"])

    msg_meta = getattr(message, "metadata", None) if message is not None else None
    if isinstance(msg_meta, dict):
        merged.update(msg_meta)

    return merged


def _resolve_pack(metadata: dict[str, Any]):
    """Pick the target pack id from request metadata, then look it up.

    Priority: ``agent_id`` > ``skill_id`` > ``pack_id`` > registry default.
    Untrusted strings are routed through
    :meth:`PackRegistry.validate_pack_id` so we never address a pack the
    registry didn't load.
    """
    for key in ("agent_id", "skill_id", "pack_id"):
        candidate = metadata.get(key)
        if not candidate:
            continue
        validated = pack_registry.validate_pack_id(candidate)
        if validated:
            return pack_registry.get_pack(validated)
        logger.warning(
            "A2A metadata.%s='%s' is not a loaded pack; falling back to default.",
            key, candidate,
        )
    return pack_registry.get_pack()


def _coerce_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip() or default


def _is_streaming_queue(event_queue: EventQueue) -> bool:
    """Heuristic: the SDK uses different queue classes for stream vs send."""
    cls_name = event_queue.__class__.__name__.lower()
    return "async" in cls_name or "stream" in cls_name


class MatbotAgentExecutor(AgentExecutor):
    """A2A executor that wraps matbot's chat pipeline."""

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        message = context.message
        if message is None:
            raise ValueError("A2A request carried no message")

        # Task bookkeeping ---------------------------------------------
        task = context.current_task
        if task is None:
            task = new_task(message)
            await event_queue.enqueue_event(task)

        task_id = task.id
        context_id = (
            task.context_id
            or getattr(context, "context_id", None)
            or getattr(message, "context_id", None)
            or str(uuid.uuid4())
        )
        if not task.context_id:
            task.context_id = context_id

        message_id = getattr(message, "message_id", None) or str(uuid.uuid4())
        if hasattr(message, "message_id") and not message.message_id:
            message.message_id = message_id

        updater = TaskUpdater(event_queue, task_id=task_id, context_id=context_id)

        # Inputs --------------------------------------------------------
        query = context.get_user_input() or ""
        query = query.strip()
        if not query:
            await updater.failed(
                new_agent_text_message(
                    "No text content found in message.",
                    context_id=context_id,
                    task_id=task_id,
                )
            )
            return

        metadata = _merge_request_metadata(context, message)
        user_id = _coerce_str(metadata.get("user_id") or metadata.get("userId"), "unknown")
        tenant_id = _coerce_str(metadata.get("tenant_id") or metadata.get("tenantId"))
        calling_agent = _coerce_str(metadata.get("calling_agent") or metadata.get("callingAgent"))

        pack = _resolve_pack(metadata)
        config = get_config()
        agent_id = pack.pack_id if pack is not None else getattr(config, "AGENT_NAME", "agent")
        if not tenant_id and pack is not None:
            tenant_id = _coerce_str(getattr(pack.config, "tenant_id", ""))

        set_full_context(
            user_id, context_id,
            message_id=message_id,
            agent_name=agent_id,
            calling_agent=calling_agent or None,
        )
        set_request_context(
            session_id=context_id,
            agent_id=agent_id,
            tenant_id=tenant_id,
        )

        streaming = _is_streaming_queue(event_queue)
        logger.info(
            "A2A execute: pack=%s session=%s message=%s streaming=%s",
            agent_id, context_id, message_id, streaming,
        )

        try:
            await updater.start_work()
            await self._run(
                query=query,
                session_id=context_id,
                message_id=message_id,
                user_id=user_id,
                tenant_id=tenant_id,
                agent_id=agent_id,
                pack=pack,
                calling_agent=calling_agent,
                streaming=streaming,
                task_id=task_id,
                context_id=context_id,
                updater=updater,
            )
        except Exception as exc:
            logger.exception("A2A execute failed: %s", exc)
            await updater.failed(
                new_agent_text_message(
                    f"Internal error: {exc}",
                    context_id=context_id,
                    task_id=task_id,
                )
            )
        finally:
            try:
                clear_request_context()
            except Exception:
                pass

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """No-op: matbot chat invocations are short and atomic; nothing to abort."""
        logger.info("A2A cancel requested for context=%s", getattr(context, "context_id", "?"))

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    async def _run(
        self,
        *,
        query: str,
        session_id: str,
        message_id: str,
        user_id: str,
        tenant_id: str,
        agent_id: str,
        pack,
        calling_agent: str,
        streaming: bool,
        task_id: str,
        context_id: str,
        updater: TaskUpdater,
    ) -> None:
        # Lazy import so unit tests can stub `langchain_chat`.
        from agent_factory import langchain_chat

        await ensure_session(
            agent_id=agent_id, tenant_id=tenant_id, session_id=session_id,
        )
        prior_history = await load_chat_history(session_id)
        with traced_operation(
            "state.save_user_message",
            session_id=session_id, message_type="user",
        ):
            await write_dispatch_event(
                session_id=session_id,
                agent_id=agent_id,
                tenant_id=tenant_id,
                user_id=user_id,
                message_id=message_id,
                query=query,
                source_channel=calling_agent or "a2a",
            )

        pack_id = pack.pack_id if pack is not None else None
        start = time.time()

        if streaming:
            await self._run_stream(
                langchain_chat=langchain_chat,
                query=query,
                session_id=session_id,
                pack_id=pack_id,
                prior_history=prior_history,
                agent_id=agent_id,
                tenant_id=tenant_id,
                user_id=user_id,
                task_id=task_id,
                context_id=context_id,
                updater=updater,
            )
        else:
            await self._run_sync(
                langchain_chat=langchain_chat,
                query=query,
                session_id=session_id,
                pack_id=pack_id,
                prior_history=prior_history,
                agent_id=agent_id,
                tenant_id=tenant_id,
                user_id=user_id,
                task_id=task_id,
                context_id=context_id,
                updater=updater,
            )

        log_operation_timing(
            logger, "a2a.execute", (time.time() - start) * 1000, success=True,
        )

    async def _run_sync(
        self,
        *,
        langchain_chat,
        query: str,
        session_id: str,
        pack_id: str | None,
        prior_history: list[dict],
        agent_id: str,
        tenant_id: str,
        user_id: str,
        task_id: str,
        context_id: str,
        updater: TaskUpdater,
    ) -> None:
        with traced_operation(
            "retrieval.process", query=query[:100], session_id=session_id,
        ) as span:
            content, team_state = await langchain_chat.run_chat(
                query,
                session_id=session_id,
                pack_id=pack_id,
                chat_history=prior_history,
            )
            span.set_attribute("retrieval.response_length", len(content))

        steps = team_state.get("_intermediate_steps") or []
        llm_calls = team_state.get("_llm_calls") or []
        token_usage = team_state.get("_token_usage", {}) or {}

        await write_tool_events(
            steps,
            session_id=session_id,
            agent_id=agent_id,
            tenant_id=tenant_id,
        )
        await write_llm_event(
            session_id=session_id,
            agent_id=agent_id,
            tenant_id=tenant_id,
            user_id=user_id,
            content=content,
            token_usage=token_usage,
            llm_calls=llm_calls,
        )

        artifact = new_text_artifact(
            name="response",
            text=content,
            description=f"Response from {agent_id}",
        )
        await updater.add_artifact(
            parts=list(artifact.parts),
            artifact_id=artifact.artifact_id,
            name=artifact.name,
        )
        await updater.complete(
            new_agent_text_message(
                content,
                context_id=context_id,
                task_id=task_id,
            )
        )

    async def _run_stream(
        self,
        *,
        langchain_chat,
        query: str,
        session_id: str,
        pack_id: str | None,
        prior_history: list[dict],
        agent_id: str,
        tenant_id: str,
        user_id: str,
        task_id: str,
        context_id: str,
        updater: TaskUpdater,
    ) -> None:
        chunks: list[str] = []
        team_state: dict = {}
        async for item in langchain_chat.run_chat_stream(
            query,
            session_id=session_id,
            pack_id=pack_id,
            chat_history=prior_history,
        ):
            if isinstance(item, tuple) and len(item) == 2 and item[0] == "done":
                team_state = item[1] or {}
                break
            if not isinstance(item, str) or not item:
                continue
            chunks.append(item)
            await updater.update_status(
                TaskState.working,
                message=new_agent_text_message(
                    item, context_id=context_id, task_id=task_id,
                ),
            )

        content = "".join(chunks).strip() or "No response generated"
        steps = team_state.get("_intermediate_steps") or []
        llm_calls = team_state.get("_llm_calls") or []
        token_usage = team_state.get("_token_usage", {}) or {}

        await write_tool_events(
            steps,
            session_id=session_id,
            agent_id=agent_id,
            tenant_id=tenant_id,
        )
        await write_llm_event(
            session_id=session_id,
            agent_id=agent_id,
            tenant_id=tenant_id,
            user_id=user_id,
            content=content,
            token_usage=token_usage,
            llm_calls=llm_calls,
        )

        artifact = new_text_artifact(
            name="response",
            text=content,
            description=f"Response from {agent_id}",
        )
        await updater.add_artifact(
            parts=list(artifact.parts),
            artifact_id=artifact.artifact_id,
            name=artifact.name,
        )
        await updater.complete(
            new_agent_text_message(
                content,
                context_id=context_id,
                task_id=task_id,
            )
        )


def create_executor() -> MatbotAgentExecutor:
    """Factory used by the FastAPI adapter at startup."""
    return MatbotAgentExecutor()
