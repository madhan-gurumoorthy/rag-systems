"""
OL Triage Pack — FastAPI router.

Endpoints:
  POST /ol/invoke                   → synchronous LLM-powered triage (human-readable report)
  POST /ol/invoke-stream            → streaming SSE version of above
  POST /ol/evaluate                 → deterministic triage, NO LLM (structured JSON for machines)

  GET  /ol/ui                       → test UI (triage form + streaming/sync toggle)
  GET  /ol/session                  → session checkpoint dashboard
  GET  /ol/session/{session_id}     → session data API (messages + LangGraph checkpoints)
"""
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Header
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

_UI_DIR = Path(__file__).parent / "ui"

from agent_factory.common.logging import get_logger

logger = get_logger("ol_triage.api")

router = APIRouter(prefix="/ol", tags=["OL Triage"])


class OLTriageRequest(BaseModel):
    query: str
    session_id: Optional[str] = None


class OLEvaluateRequest(BaseModel):
    """Request model for deterministic evaluation (no LLM)."""
    offer_id: str
    store_id: str
    mart_id: str = "0"


# ── POST /ol/invoke ────────────────────────────────────────────────────────────

@router.post("/invoke")
async def ol_invoke(
    request: OLTriageRequest,
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
):
    """Synchronous OL triage — returns a complete analysis report.

    Uses the fast-path (0 LLM calls) when the query contains a recognisable
    offer ID and store number; falls back to the LangGraph ReAct loop otherwise.
    """
    from packs.offer_intelligence.workflow import run_ol_agent

    session_id = request.session_id or x_session_id or str(uuid.uuid4())
    start = time.time()
    logger.info(f"ol_invoke.start query={request.query[:80]} session={session_id}")

    try:
        content = await run_ol_agent(request.query, session_id=session_id)
    except Exception as exc:
        logger.error(f"ol_invoke.error error={exc}")
        return JSONResponse(status_code=500, content={"error": str(exc)})

    duration = time.time() - start
    logger.info(f"ol_invoke.done duration_s={round(duration, 2)}")

    return JSONResponse(content={
        "response": content,
        "session_id": session_id,
        "agent": "ol-triage-agent",
        "time_taken": duration,
    })


# ── POST /ol/invoke-stream ─────────────────────────────────────────────────────

@router.post("/invoke-stream")
async def ol_invoke_stream(
    request: OLTriageRequest,
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
):
    """Streaming OL triage — returns SSE events as the agent works.

    Event types emitted:
      start       — agent is starting
      log         — informational message
      tool_start  — a tool call is about to execute
      tool_result — abbreviated tool output preview
      chunk       — content fragment (final report arrives as one chunk)
      done        — analysis complete; carries full accumulated response
      error       — unrecoverable error
    """
    from packs.offer_intelligence.workflow import stream_ol_agent

    session_id = request.session_id or x_session_id or str(uuid.uuid4())
    seq = 0

    def _make_event(event_type: str, data: dict) -> str:
        nonlocal seq
        payload = {
            "event": event_type,
            "seq": seq,
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "data": data,
        }
        seq += 1
        return f"data: {json.dumps(payload)}\n\n"

    async def generate():
        yield _make_event("start", {"session_id": session_id, "message": "Starting OL triage..."})
        full_response: list[str] = []

        try:
            async for event in stream_ol_agent(request.query, session_id=session_id):
                etype = event.get("type", "log")
                content = event.get("content", "")

                if etype == "start":
                    yield _make_event("log", {"message": content})
                elif etype == "tool_start":
                    yield _make_event("tool_start", {
                        "message": content,
                        "tool": event.get("tool", ""),
                    })
                elif etype == "tool_result":
                    yield _make_event("tool_result", {
                        "tool": event.get("tool", ""),
                        "preview": content[:120],
                    })
                elif etype == "chunk":
                    full_response.append(content)
                    yield _make_event("chunk", {"content": content})
                elif etype == "done":
                    yield _make_event("done", {
                        "session_id": session_id,
                        "response": "".join(full_response),
                    })
                elif etype == "error":
                    yield _make_event("error", {"error": content})

        except Exception as exc:
            logger.error(f"ol_stream.error error={exc}")
            yield _make_event("error", {"error": str(exc)})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── POST /ol/evaluate ──────────────────────────────────────────────────────────

@router.post("/evaluate")
async def ol_evaluate(request: OLEvaluateRequest):
    """Deterministic OL triage — NO LLM, pure rule evaluation.

    Returns structured JSON with per-rule verdicts for machine consumption.
    Suitable for: TransOne agent callbacks, batch jobs, Kafka consumers.
    """
    from packs.offer_intelligence.triage_engine import get_engine

    start = time.time()
    logger.info(f"ol_evaluate.start offer={request.offer_id} store={request.store_id}")

    try:
        engine = get_engine()
        result = await engine.triage_offer(
            offer_id=request.offer_id,
            store_id=request.store_id,
            mart_id=request.mart_id,
        )
    except Exception as exc:
        logger.error(f"ol_evaluate.error error={exc}")
        return JSONResponse(status_code=500, content={"error": str(exc)})

    duration = time.time() - start
    logger.info(
        f"ol_evaluate.done offer={request.offer_id} store={request.store_id} "
        f"verdict={result.overall_verdict} duration_s={round(duration, 2)}"
    )

    return JSONResponse(content={
        **result.to_dict(),
        "time_taken": duration,
    })


# ── GET /ol/ui ─────────────────────────────────────────────────────────────────

@router.get("/ui", include_in_schema=False)
async def ol_ui():
    """Serve the OL Triage test UI."""
    return FileResponse(_UI_DIR / "triage.html", media_type="text/html")


# ── GET /ol/session (viewer page) ─────────────────────────────────────────────

@router.get("/session", include_in_schema=False)
async def ol_session_viewer():
    """Serve the session checkpoint dashboard."""
    return FileResponse(_UI_DIR / "session.html", media_type="text/html")


# ── GET /ol/session/{session_id} (data API) ───────────────────────────────────

@router.get("/session/{session_id}")
async def ol_session_data(session_id: str):
    """Return messages and LangGraph checkpoints for a session.

    Messages come from postgres_state_manager (if available).
    Checkpoints come from the workflow's MemorySaver (in-process lifetime only).
    """
    from packs.offer_intelligence.workflow import get_graph

    # ── Messages from postgres state manager ──
    messages: list[dict[str, Any]] = []
    try:
        from storage.state_store import postgres_state_manager
        if postgres_state_manager.is_available():
            rows = await postgres_state_manager.get_session_messages(session_id, limit=200)
            messages = [dict(r) for r in (rows or [])]
    except Exception as exc:
        logger.warning(f"ol_session_data.messages_error session={session_id} error={exc}")

    # ── Checkpoints from MemorySaver ──
    checkpoints: list[dict[str, Any]] = []
    tool_call_count = 0
    fast_path_count = 0

    try:
        graph = get_graph()
        cp_config = {"configurable": {"thread_id": session_id}}
        async for cp_tuple in graph.checkpointer.alist(cp_config):
            cp = cp_tuple.checkpoint or {}
            meta = cp_tuple.metadata or {}

            # Count tool calls in this checkpoint's messages
            for msg in (cp.get("channel_values") or {}).get("messages", []):
                tc = getattr(msg, "tool_calls", None) or (msg.get("tool_calls") if isinstance(msg, dict) else None)
                if tc:
                    tool_call_count += len(tc)

            checkpoints.append({
                "metadata": meta,
                "checkpoint": {
                    "ts": cp.get("ts"),
                    "id": cp.get("id"),
                    "channel_values": {
                        k: _serialise_channel(v)
                        for k, v in (cp.get("channel_values") or {}).items()
                    },
                },
                "parent_config": cp_tuple.parent_config,
            })
    except Exception as exc:
        logger.warning(f"ol_session_data.checkpoints_error session={session_id} error={exc}")

    # Estimate fast-path hits: requests with no tool calls in the messages
    # are either fast-path or pure conversational answers.
    user_msgs = [m for m in messages if m.get("msg_type") in ("user",)]
    fast_path_count = max(0, len(user_msgs) - tool_call_count)

    return JSONResponse(content={
        "session_id": session_id,
        "messages": messages,
        "checkpoints": list(reversed(checkpoints)),  # newest first
        "tool_call_count": tool_call_count,
        "fast_path_count": fast_path_count,
    })


def _serialise_channel(value: Any) -> Any:
    """Make a LangGraph channel value JSON-serialisable."""
    if isinstance(value, list):
        return [_serialise_channel(v) for v in value]
    if isinstance(value, dict):
        return {k: _serialise_channel(v) for k, v in value.items()}
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump()
        except Exception:
            pass
    if hasattr(value, "__dict__"):
        try:
            return {k: _serialise_channel(v) for k, v in value.__dict__.items() if not k.startswith("_")}
        except Exception:
            pass
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return str(value)
