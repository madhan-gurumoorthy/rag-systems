"""Read-only observability dashboard.

Two-tab HTML console (Homepage + Conversations) backed by JSON
aggregates over the canonical ``session`` and ``event`` tables.
Read-only: no writes, no schema changes, pack-agnostic.

Endpoints
---------

* ``GET /dashboard``                                — single-page HTML console
* ``GET /api/dashboard/agents``                     — distinct agent_id / pack_id values for the filter
* ``GET /api/dashboard/homepage``                   — Homepage KPIs + charts (filters: agent_id, hours)
* ``GET /api/dashboard/sessions``                   — Conversations grid rows (filters: agent_id, hours, limit)
* ``GET /api/dashboard/summary``                    — legacy top-line counters (no filters)
* ``GET /api/dashboard/session/{session_id}``       — drill-down: session metadata + event timeline
"""
import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse


def _json_default(obj: Any) -> Any:
    """Coerce non-JSON-native values asyncpg returns (datetime, UUID, Decimal)."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"{type(obj).__name__} not JSON serializable")


def _jsonable(payload: Any) -> Any:
    """Round-trip through json with the default coercer so FastAPI's
    encoder sees pure-Python primitives only."""
    return json.loads(json.dumps(payload, default=_json_default))


# JSONB columns that asyncpg returns as ``str`` because we don't register
# a codec on the pool.  The dashboard JS expects them as objects/arrays.
_EVENT_JSONB_COLS = ("input_messages", "output_message", "llm_metadata", "domain_data")
_SESSION_JSONB_COLS = ("domain_data",)


def _decode_jsonb(row: dict, cols: tuple[str, ...]) -> dict:
    """Best-effort: parse JSONB columns from raw ``str`` into Python.

    asyncpg returns ``jsonb`` as text by default.  We avoid registering a
    pool-wide codec (writers pass ``json.dumps`` strings via ``$N::jsonb``
    casts and a codec would round-trip those), so the dashboard decodes
    here instead.  Values that are already dicts/lists are left alone.
    """
    for col in cols:
        value = row.get(col)
        if isinstance(value, str):
            try:
                row[col] = json.loads(value)
            except (TypeError, ValueError):
                pass  # leave the raw string; the UI will degrade gracefully
    return row


from agent_factory.common.logging import get_logger
from storage import postgres_state_manager

logger = get_logger("agent_factory_api.dashboard")
router = APIRouter(tags=["dashboard"])


def _agent_clause(agent_id: Optional[str], alias: str) -> tuple[str, list[Any]]:
    """Build an optional ``alias.agent_id = $N`` predicate."""
    if agent_id:
        return f" AND {alias}.agent_id = $%d", [agent_id]
    return "", []


# ── JSON endpoints ──────────────────────────────────────────────────


@router.get("/api/dashboard/agents", response_class=JSONResponse)
async def dashboard_agents():
    """Distinct ``agent_id`` values seen in the session table, for the
    homepage filter dropdown."""
    pool = postgres_state_manager.pool
    if pool is None:
        raise HTTPException(status_code=503, detail="postgres not available")

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT agent_id, count(*) AS n "
            "FROM session "
            "GROUP BY agent_id "
            "ORDER BY n DESC"
        )
    return JSONResponse(content=_jsonable({"agents": [dict(r) for r in rows]}))


@router.get("/api/dashboard/homepage", response_class=JSONResponse)
async def dashboard_homepage(
    agent_id: Optional[str] = Query(None, description="Filter by agent_id; omit for all agents"),
    hours: int = Query(168, ge=1, le=24 * 365, description="Look-back window in hours"),
):
    """Homepage aggregate: KPIs + per-day conversations + LLM totals +
    per-agent usage breakdown.  All counts are scoped to the window
    ``[now() - hours, now()]`` and, optionally, a single ``agent_id``.
    """
    pool = postgres_state_manager.pool
    if pool is None:
        raise HTTPException(status_code=503, detail="postgres not available")

    # Build a single ``$1::interval`` window expression we can reuse in
    # every CTE — simpler than threading the same NOW() - interval
    # subtraction through five separate statements.  asyncpg binds
    # interval params as ``timedelta``; the string form fails encoding.
    params: list[Any] = [timedelta(hours=hours)]
    agent_pred = ""
    if agent_id:
        params.append(agent_id)
        agent_pred = f" AND s.agent_id = ${len(params)}"

    async with pool.acquire() as conn:
        # ── KPI: conversations in window
        kpi_sessions = await conn.fetchval(
            f"SELECT count(*) FROM session s "
            f"WHERE s.started_at >= NOW() - $1::interval{agent_pred}",
            *params,
        )

        # ── LLM totals
        llm_totals = await conn.fetchrow(
            f"""
            SELECT
              COALESCE(SUM(e.input_tokens), 0)                       AS input_tokens,
              COALESCE(SUM(e.output_tokens), 0)                      AS output_tokens,
              COALESCE(SUM(e.reasoning_tokens), 0)                   AS reasoning_tokens,
              COUNT(*) FILTER (WHERE e.event_type = 'llm')           AS llm_calls,
              COALESCE(AVG(e.llm_latency_ms)
                       FILTER (WHERE e.event_type = 'llm'
                               AND e.llm_latency_ms IS NOT NULL), 0) AS llm_avg_ms
            FROM event e
            JOIN session s USING (session_id)
            WHERE s.started_at >= NOW() - $1::interval{agent_pred}
            """,
            *params,
        )

        # ── Conversations over time (bucketed by day OR hour depending
        #     on window width).  Buckets keep the chart legible whether
        #     the window is 2h or 90d.
        bucket = "hour" if hours <= 48 else "day"
        conv_rows = await conn.fetch(
            f"""
            SELECT date_trunc('{bucket}', s.started_at) AS bucket,
                   count(*) AS n
            FROM session s
            WHERE s.started_at >= NOW() - $1::interval{agent_pred}
            GROUP BY bucket
            ORDER BY bucket ASC
            """,
            *params,
        )

        # ── Per-agent usage breakdown (always grouped; respects window)
        agent_rows = await conn.fetch(
            f"""
            SELECT s.agent_id, count(*) AS n
            FROM session s
            WHERE s.started_at >= NOW() - $1::interval{agent_pred}
            GROUP BY s.agent_id
            ORDER BY n DESC
            """,
            *params,
        )

    return JSONResponse(content=_jsonable({
        "window_hours": hours,
        "agent_id": agent_id,
        "bucket": bucket,
        "kpis": {
            "conversations": kpi_sessions or 0,
        },
        "llm": dict(llm_totals) if llm_totals else {},
        "conversations_series": [
            {"bucket": r["bucket"], "n": r["n"]} for r in conv_rows
        ],
        "agent_breakdown": [dict(r) for r in agent_rows],
    }))


@router.get("/api/dashboard/summary", response_class=JSONResponse)
async def dashboard_summary():
    """Legacy unscoped top-line counters (kept for backward compat)."""
    pool = postgres_state_manager.pool
    if pool is None:
        raise HTTPException(status_code=503, detail="postgres not available")

    async with pool.acquire() as conn:
        sess_count = await conn.fetchval("SELECT count(*) FROM session")
        ev_count = await conn.fetchval("SELECT count(*) FROM event")
        ev_tokens = await conn.fetchrow(
            "SELECT "
            "  COALESCE(SUM(input_tokens), 0) AS input_tokens, "
            "  COALESCE(SUM(output_tokens), 0) AS output_tokens, "
            "  COALESCE(SUM(cache_read_tokens), 0) AS cache_read_tokens, "
            "  COALESCE(SUM(cache_creation_tokens), 0) AS cache_creation_tokens, "
            "  COALESCE(SUM(reasoning_tokens), 0) AS reasoning_tokens "
            "FROM event"
        )
        agents = await conn.fetch(
            "SELECT agent_id, count(*) AS n FROM session GROUP BY agent_id ORDER BY n DESC"
        )

    return JSONResponse(
        content=_jsonable({
            "sessions": sess_count,
            "events": ev_count,
            "tokens": dict(ev_tokens),
            "agents": [dict(r) for r in agents],
        })
    )


@router.get("/api/dashboard/sessions", response_class=JSONResponse)
async def dashboard_sessions(
    limit: int = Query(200, ge=1, le=2000),
    agent_id: Optional[str] = Query(None),
    hours: Optional[int] = Query(None, ge=1, le=24 * 365),
):
    """List sessions (newest first) with event counts.  Optional
    ``agent_id`` and ``hours`` filters power the Conversations tab's
    per-agent / time-range slicer."""
    pool = postgres_state_manager.pool
    if pool is None:
        raise HTTPException(status_code=503, detail="postgres not available")

    params: list[Any] = [limit]
    where_parts: list[str] = []
    if agent_id:
        params.append(agent_id)
        where_parts.append(f"s.agent_id = ${len(params)}")
    if hours is not None:
        params.append(timedelta(hours=hours))
        where_parts.append(f"s.started_at >= NOW() - ${len(params)}::interval")
    where_sql = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT
              s.session_id::text           AS session_id,
              s.agent_id,
              s.tenant_id,
              s.status,
              s.trace_id,
              s.started_at,
              s.ended_at,
              s.archived_at,
              COALESCE(ev.n_events, 0)      AS n_events,
              COALESCE(ev.input_tokens, 0)  AS input_tokens,
              COALESCE(ev.output_tokens, 0) AS output_tokens,
              COALESCE(ev.llm_count,  0)    AS llm_count,
              COALESCE(ev.tool_count, 0)    AS tool_count
            FROM session s
            LEFT JOIN (
              SELECT
                session_id,
                count(*)                                          AS n_events,
                SUM(input_tokens)                                 AS input_tokens,
                SUM(output_tokens)                                AS output_tokens,
                COUNT(*) FILTER (WHERE event_type = 'llm')        AS llm_count,
                COUNT(*) FILTER (WHERE event_type = 'tool')       AS tool_count
              FROM event GROUP BY session_id
            ) ev USING (session_id)
            {where_sql}
            ORDER BY s.started_at DESC NULLS LAST
            LIMIT $1
            """,
            *params,
        )

    return JSONResponse(content=_jsonable({"sessions": [dict(r) for r in rows]}))


@router.get("/api/dashboard/session/{session_id}", response_class=JSONResponse)
async def dashboard_session_detail(session_id: str):
    """Drill-down view: session row + its events."""
    pool = postgres_state_manager.pool
    if pool is None:
        raise HTTPException(status_code=503, detail="postgres not available")

    async with pool.acquire() as conn:
        session_row = await conn.fetchrow(
            "SELECT session_id::text, agent_id, tenant_id, status, trace_id, "
            "       started_at, ended_at, archived_at, domain_data "
            "FROM session WHERE session_id = $1::uuid",
            session_id,
        )
        if session_row is None:
            raise HTTPException(status_code=404, detail="session not found")

        events = await conn.fetch(
            """
            SELECT
              event_id::text AS event_id,
              event_type, seq_num, trace_id,
              model_provider, model_name,
              input_tokens, output_tokens,
              cache_read_tokens, cache_creation_tokens, reasoning_tokens,
              llm_latency_ms, tool_latency_ms, time_to_first_token_ms,
              input_messages, output_message, llm_metadata, domain_data,
              created_at,
              work_item_id::text AS work_item_id
            FROM event
            WHERE session_id = $1::uuid
            ORDER BY created_at ASC, seq_num ASC
            """,
            session_id,
        )

    session_dict = _decode_jsonb(dict(session_row), _SESSION_JSONB_COLS)
    event_dicts = [_decode_jsonb(dict(r), _EVENT_JSONB_COLS) for r in events]

    return JSONResponse(
        content=_jsonable({
            "session": session_dict,
            "events": event_dicts,
        }),
    )


# ── HTML dashboard ──────────────────────────────────────────────────


_DASHBOARD_HTML = r"""<!doctype html>
<html lang="en" data-theme="light">
<head>
  <meta charset="utf-8">
  <title>Agent Factory — Dashboard</title>
  <style>
    /* ── Living Design tokens (light) ───────────────────────────── */
    :root {
      --ld-blue:        #0053e2;
      --ld-blue-dark:   #002185;
      --ld-blue-light:  #e6eeff;
      --ld-spark:       #ffc220;
      --ld-spark-dark:  #f59b00;
      --ld-positive:    #1a8b3c;
      --ld-positive-bg: #e6f5ea;
      --ld-negative:    #c42e26;
      --ld-negative-bg: #fce9e8;
      --ld-warning:     #fc934d;
      --ld-warning-bg:  #fff4ec;
      --ld-text:        #2e2f32;
      --ld-text-2:      #515357;
      --ld-text-subtle: #74767c;
      --ld-surface:     #ffffff;
      --ld-surface-2:   #f8f8f8;
      --ld-surface-3:   #eef0f3;
      --ld-bg:          #f1f1f2;
      --ld-separator:   #e3e4e5;
      --ld-border:      #babbbe;
      --ld-shadow-card: 0 .0625rem .125rem .0625rem rgba(0,0,0,.10),
                        0 -.0625rem .125rem 0 rgba(0,0,0,.06);
      --ld-shadow-elev: 0 .1875rem .3125rem .125rem rgba(0,0,0,.12),
                        0 -.0625rem .1875rem 0 rgba(0,0,0,.08);
      --ld-font:        'EverydaySans','Helvetica Neue',Arial,sans-serif;
      --ld-font-mono:   'EverydaySansMono','Courier New',monospace;
      --ld-font-display:'Bogle','EverydaySans','Helvetica Neue',sans-serif;
      --topbar-h:       3.25rem;
    }
    /* ── Dark mode tokens ──────────────────────────────────────── */
    html[data-theme="dark"] {
      --ld-blue:        #4c8dff;
      --ld-blue-light:  #15243f;
      --ld-positive:    #4cc28a;
      --ld-positive-bg: #16291f;
      --ld-negative:    #ff6b6b;
      --ld-negative-bg: #2a1518;
      --ld-warning:     #ffb47a;
      --ld-warning-bg:  #2a1f12;
      --ld-spark-dark:  #ffc220;
      --ld-text:        #e6e9ef;
      --ld-text-2:      #b9bdc6;
      --ld-text-subtle: #8a93a6;
      --ld-surface:     #161a22;
      --ld-surface-2:   #1c2230;
      --ld-surface-3:   #232a3a;
      --ld-bg:          #0f1115;
      --ld-separator:   #2a2f3a;
      --ld-border:      #3a4150;
      --ld-shadow-card: 0 .0625rem .125rem .0625rem rgba(0,0,0,.4),
                        0 -.0625rem .125rem 0 rgba(0,0,0,.3);
      --ld-shadow-elev: 0 .1875rem .3125rem .125rem rgba(0,0,0,.5),
                        0 -.0625rem .1875rem 0 rgba(0,0,0,.4);
    }

    *, *::before, *::after { box-sizing: border-box; margin:0; padding:0; }
    body {
      font-family: var(--ld-font); font-size: 14px; line-height: 1.5;
      background: var(--ld-bg); color: var(--ld-text); min-height: 100vh;
      -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale;
    }

    /* ── Top bar ──────────────────────────────────────────────── */
    .topbar {
      position: sticky; top: 0; z-index: 100;
      display: flex; align-items: center; gap: 1rem;
      height: var(--topbar-h); padding: 0 1.5rem;
      background: var(--ld-surface); border-bottom: 1px solid var(--ld-separator);
      box-shadow: var(--ld-shadow-card);
    }
    .brand { display: flex; align-items: center; gap: .5rem; }
    .brand-spark {
      width: 1.5rem; height: 1.5rem; border-radius: 50%;
      background: radial-gradient(circle at 30% 30%, var(--ld-spark), var(--ld-spark-dark));
      box-shadow: 0 0 0 2px rgba(255,194,32,.15);
    }
    .brand-text {
      font-family: var(--ld-font-display); font-weight: 700; font-size: 1rem;
      color: var(--ld-text);
    }
    .tabs { display: flex; align-items: center; gap: .125rem; flex: 1; }
    .tab {
      padding: .5rem 1rem; color: var(--ld-text-2); font-size: .875rem;
      font-weight: 600; border-radius: .5rem; cursor: pointer; position: relative;
      transition: background .15s, color .15s; user-select: none;
    }
    .tab:hover { background: var(--ld-surface-2); color: var(--ld-text); }
    .tab.active { color: var(--ld-blue); background: var(--ld-blue-light); }
    .tab.active::after {
      content: ''; position: absolute; left: 1rem; right: 1rem; bottom: -.5625rem;
      height: 3px; background: var(--ld-blue); border-radius: 3px 3px 0 0;
    }
    .topbar-actions { display: flex; align-items: center; gap: .75rem; margin-left: auto; }
    .ld-select, .ld-btn {
      padding: .35rem .75rem; height: 2.1rem; border-radius: .25rem;
      border: 1px solid var(--ld-border); background: var(--ld-surface);
      color: var(--ld-text); font-family: var(--ld-font); font-size: .8125rem;
      cursor: pointer; transition: border-color .15s, background .15s;
    }
    .ld-select:focus, .ld-btn:focus {
      outline: none; border-color: var(--ld-blue);
      box-shadow: 0 0 0 2px rgba(0,83,226,.2);
    }
    .ld-btn:hover { background: var(--ld-surface-2); }
    .ld-btn-primary {
      background: var(--ld-blue); border-color: var(--ld-blue); color: #fff;
    }
    .ld-btn-primary:hover { background: var(--ld-blue-dark); }
    .icon-btn {
      width: 2.1rem; height: 2.1rem; display: inline-flex; align-items: center;
      justify-content: center; font-size: 1rem; padding: 0;
    }

    /* ── Layout ──────────────────────────────────────────────── */
    .content { padding: 1.25rem 1.5rem; max-width: 1600px; margin: 0 auto; }
    .content h1 {
      font-family: var(--ld-font-display); font-size: 1.375rem; font-weight: 700;
      color: var(--ld-text); margin-bottom: .25rem;
    }
    .subtitle { color: var(--ld-text-subtle); font-size: .8125rem; margin-bottom: 1.25rem; }

    /* ── KPI cards ──────────────────────────────────────────── */
    .kpi-row {
      display: grid; gap: 1rem; margin-bottom: 1.25rem;
      grid-template-columns: repeat(4, 1fr);
    }
    @media (max-width: 1000px) { .kpi-row { grid-template-columns: repeat(2, 1fr); } }
    .kpi-card {
      background: var(--ld-surface); border-radius: .5rem;
      padding: 1rem 1.25rem; box-shadow: var(--ld-shadow-card);
      transition: transform .15s, box-shadow .15s;
    }
    .kpi-card:hover { transform: translateY(-1px); box-shadow: var(--ld-shadow-elev); }
    .kpi-value {
      font-family: var(--ld-font-display); font-size: 1.75rem; font-weight: 700;
      color: var(--ld-blue); line-height: 1.1;
    }
    .kpi-value.success  { color: var(--ld-positive); }
    .kpi-value.hitl     { color: var(--ld-spark-dark); }
    .kpi-value.negative { color: var(--ld-negative); }
    .kpi-value.warning  { color: var(--ld-warning); }
    .kpi-label {
      font-size: .7rem; font-weight: 700; color: var(--ld-text-subtle);
      text-transform: uppercase; letter-spacing: .5px; margin-top: .35rem;
    }
    .kpi-sub { font-size: .7rem; color: var(--ld-text-subtle); margin-top: .25rem; }

    /* ── Panels / charts ────────────────────────────────────── */
    .panel-row {
      display: grid; gap: 1rem; margin-bottom: 1.25rem;
      grid-template-columns: 1.4fr 1fr 1.4fr;
    }
    @media (max-width: 1100px) { .panel-row { grid-template-columns: 1fr; } }
    .panel {
      background: var(--ld-surface); border-radius: .5rem;
      box-shadow: var(--ld-shadow-card); padding: 1rem 1.25rem;
    }
    .panel h3 {
      font-family: var(--ld-font-display); font-size: .8125rem; font-weight: 700;
      color: var(--ld-text); margin-bottom: .15rem;
    }
    .panel .sub {
      font-size: .7rem; color: var(--ld-text-subtle); margin-bottom: .75rem;
    }

    /* CSS bar charts */
    .bar-chart {
      display: flex; align-items: flex-end; gap: .5rem; height: 200px;
      padding: .5rem 0 1.25rem;
      border-bottom: 1px dashed var(--ld-separator); position: relative;
    }
    .bar-col {
      flex: 1; display: flex; flex-direction: column; align-items: center;
      gap: .35rem; min-width: 0;
    }
    .bar {
      width: 100%; max-width: 36px; background: var(--ld-blue);
      border-radius: 3px 3px 0 0; transition: height .3s ease-out;
      position: relative;
    }
    .bar:hover { background: var(--ld-blue-dark); }
    .bar-label {
      font-size: .65rem; color: var(--ld-text-subtle);
      text-align: center; max-width: 100%; overflow: hidden;
      text-overflow: ellipsis; white-space: nowrap;
    }
    .bar-tooltip {
      position: absolute; bottom: 100%; left: 50%; transform: translateX(-50%);
      background: var(--ld-text); color: var(--ld-surface); padding: .15rem .4rem;
      border-radius: 3px; font-size: .65rem; white-space: nowrap;
      opacity: 0; pointer-events: none; transition: opacity .15s;
    }
    .bar:hover .bar-tooltip { opacity: 1; }
    .bar.agent { background: var(--ld-spark-dark); }
    .bar.agent:hover { background: var(--ld-spark); }

    /* ── Conversations tab ─────────────────────────────────── */
    .convo-toolbar {
      display: flex; gap: .75rem; align-items: center; flex-wrap: wrap;
      margin-bottom: .75rem;
    }
    .convo-count {
      background: var(--ld-surface-3); color: var(--ld-text-2);
      padding: .15rem .5rem; border-radius: 999px; font-size: .75rem; font-weight: 600;
    }
    .convo-table-wrap {
      background: var(--ld-surface); border-radius: .5rem;
      box-shadow: var(--ld-shadow-card); overflow: hidden;
    }
    .convo-table { width: 100%; border-collapse: collapse; }
    .convo-table th, .convo-table td {
      text-align: left; padding: .55rem .85rem; font-size: .8125rem;
      border-bottom: 1px solid var(--ld-separator);
    }
    .convo-table th {
      background: var(--ld-surface-2); color: var(--ld-text-2);
      font-size: .7rem; font-weight: 700; text-transform: uppercase;
      letter-spacing: .3px; position: sticky; top: 0;
    }
    .convo-table tr.row { cursor: pointer; transition: background .1s; }
    .convo-table tr.row:hover { background: var(--ld-surface-2); }
    .convo-table tr.row.active { background: var(--ld-blue-light); }
    .convo-table .mono { font-family: var(--ld-font-mono); font-size: .75rem; }
    .convo-table .num  { text-align: right; font-family: var(--ld-font-mono); }
    .convo-row-search {
      flex: 1; min-width: 240px; padding: .35rem .75rem;
      border: 1px solid var(--ld-border); border-radius: .25rem;
      background: var(--ld-surface); color: var(--ld-text); font-size: .8125rem;
    }

    /* Badges */
    .badge {
      display: inline-block; padding: 1px 8px; border-radius: 8px;
      font-size: .7rem; font-weight: 600;
      background: var(--ld-surface-3); color: var(--ld-text-2);
    }
    .badge.ok      { background: var(--ld-positive-bg);  color: var(--ld-positive); }
    .badge.warn    { background: var(--ld-warning-bg);   color: var(--ld-warning); }
    .badge.err     { background: var(--ld-negative-bg);  color: var(--ld-negative); }
    .badge.info    { background: var(--ld-blue-light);   color: var(--ld-blue); }

    /* Detail drawer */
    .drawer-overlay {
      position: fixed; inset: 0; background: rgba(0,0,0,.4); display: none;
      z-index: 200; align-items: stretch; justify-content: flex-end;
    }
    .drawer-overlay.open { display: flex; }
    .drawer {
      width: min(900px, 100%); background: var(--ld-bg); height: 100%;
      box-shadow: var(--ld-shadow-elev); overflow-y: auto;
      animation: slideIn .2s ease-out;
    }
    @keyframes slideIn { from { transform: translateX(40px); opacity: 0; } to { transform: none; opacity: 1; } }
    .drawer-header {
      position: sticky; top: 0; background: var(--ld-surface);
      border-bottom: 1px solid var(--ld-separator);
      padding: .85rem 1.25rem; display: flex; align-items: center; gap: .75rem;
      z-index: 1;
    }
    .drawer-body { padding: 1rem 1.25rem; }
    .drawer h2 {
      font-family: var(--ld-font-display); font-size: 1rem; font-weight: 700;
    }
    .drawer .sub {
      font-family: var(--ld-font-mono); font-size: .75rem; color: var(--ld-text-subtle);
      word-break: break-all;
    }
    .drawer .panel { margin-bottom: 1rem; }
    table.kv { width: 100%; border-collapse: collapse; font-size: .8125rem; }
    table.kv th, table.kv td {
      text-align: left; padding: .35rem .5rem;
      border-bottom: 1px solid var(--ld-separator);
    }
    table.kv th { color: var(--ld-text-subtle); font-weight: 600; width: 30%; }

    /* Pipeline event cards (drill-down) */
    .timeline { display: flex; flex-direction: column; gap: .5rem; }
    .ev-card {
      background: var(--ld-surface-2); border-radius: .35rem;
      border-left: 3px solid var(--ld-border); overflow: hidden;
    }
    .ev-card.ev-dispatch { border-left-color: var(--ld-blue); }
    .ev-card.ev-llm      { border-left-color: var(--ld-positive); }
    .ev-card.ev-tool     { border-left-color: var(--ld-warning); }
    .ev-card.ev-hitl     { border-left-color: var(--ld-spark-dark); }
    .ev-card.ev-error    { border-left-color: var(--ld-negative); }
    .ev-card.ev-state    { border-left-color: var(--ld-text-subtle); }
    .ev-hdr {
      display: flex; align-items: center; gap: .5rem; padding: .4rem .75rem;
      background: var(--ld-surface-3); flex-wrap: wrap; font-size: .75rem;
    }
    .ev-body { padding: .5rem .75rem; font-size: .8125rem; }
    .ev-label {
      font-size: .65rem; font-weight: 700; color: var(--ld-text-subtle);
      text-transform: uppercase; letter-spacing: .4px; margin-bottom: .25rem;
    }
    .ev-text { white-space: pre-wrap; word-break: break-word; }
    pre.ev-pre {
      background: var(--ld-bg); border: 1px solid var(--ld-separator);
      border-radius: 3px; padding: .4rem .55rem; font-size: .7rem;
      max-height: 200px; overflow: auto; font-family: var(--ld-font-mono);
      white-space: pre; margin-top: .25rem;
    }
    details.ev-raw { padding: 0 .75rem .5rem; }
    details.ev-raw summary {
      cursor: pointer; outline: none; font-size: .7rem; color: var(--ld-text-subtle);
    }
    details.ev-raw pre {
      background: var(--ld-bg); border: 1px solid var(--ld-separator);
      border-radius: 3px; padding: .55rem; font-size: .7rem; overflow: auto;
      font-family: var(--ld-font-mono); margin-top: .25rem;
    }

    .empty {
      color: var(--ld-text-subtle); text-align: center; padding: 2.5rem 1rem;
      font-size: .85rem;
    }
    .meta-line { font-size: .75rem; color: var(--ld-text-subtle); margin-left: .25rem; }
    .hidden { display: none !important; }
  </style>
</head>
<body>

<header class="topbar">
  <div class="brand">
    <span class="brand-spark" aria-hidden="true"></span>
    <span class="brand-text">Agent Factory</span>
  </div>
  <nav class="tabs">
    <span class="tab active" data-tab="homepage" onclick="switchTab('homepage', this)">Homepage</span>
    <span class="tab" data-tab="conversations" onclick="switchTab('conversations', this)">Conversations</span>
  </nav>
  <div class="topbar-actions">
    <select id="agentFilter" class="ld-select" title="Agent / pack" onchange="onFilterChange()">
      <option value="">All agents</option>
    </select>
    <select id="hoursFilter" class="ld-select" title="Time range" onchange="onFilterChange()">
      <option value="2">Last 2 hours</option>
      <option value="8">Last 8 hours</option>
      <option value="72">Last 3 days</option>
      <option value="168" selected>Last 7 days</option>
      <option value="360">Last 15 days</option>
      <option value="2160">Last 90 days</option>
    </select>
    <button class="ld-btn icon-btn" id="themeToggle" title="Toggle theme"
            onclick="toggleTheme()" aria-label="Toggle theme">🌙</button>
    <button class="ld-btn ld-btn-primary" onclick="refreshAll()" title="Refresh">Refresh</button>
  </div>
</header>

<main class="content">

  <!-- ═══ Homepage tab ═══════════════════════════════════════════ -->
  <section data-section="homepage">
    <h1>Homepage</h1>
    <p class="subtitle" id="homepageSubtitle">Pipeline activity in the selected window</p>

    <div class="kpi-row">
      <div class="kpi-card">
        <div class="kpi-value" id="kpiConversations">—</div>
        <div class="kpi-label">Total Conversations</div>
        <div class="kpi-sub">Sessions in window</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-value success" id="kpiLlmCalls">—</div>
        <div class="kpi-label">LLM Calls</div>
        <div class="kpi-sub">Model invocations</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-value" id="kpiTokens">—</div>
        <div class="kpi-label">Total Tokens</div>
        <div class="kpi-sub" id="kpiTokensSub">—</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-value warning" id="kpiAvgLatency">—</div>
        <div class="kpi-label">Avg LLM Latency</div>
        <div class="kpi-sub">ms per call</div>
      </div>
    </div>

    <div class="panel-row" style="grid-template-columns: 1fr 1fr">
      <div class="panel">
        <h3>Conversations Over Time</h3>
        <div class="sub" id="convTimeSub">Per-bucket session volume</div>
        <div class="bar-chart" id="convTimeChart"></div>
      </div>

      <div class="panel">
        <h3>Agent Usage</h3>
        <div class="sub">Sessions per agent / pack in window</div>
        <div class="bar-chart" id="agentUsageChart"></div>
      </div>
    </div>
  </section>

  <!-- ═══ Conversations tab ═══════════════════════════════════════ -->
  <section data-section="conversations" class="hidden">
    <h1>Conversations</h1>
    <p class="subtitle">Sessions and their drill-down timeline. Click any row to inspect work items and events.</p>

    <div class="convo-toolbar">
      <span class="convo-count" id="convoCount">0 sessions</span>
      <input type="text" id="convoSearch" class="convo-row-search"
             placeholder="Search by session id, agent, or status…"
             oninput="renderConvoTable()">
    </div>

    <div class="convo-table-wrap">
      <table class="convo-table">
        <thead>
          <tr>
            <th>Session</th>
            <th>Agent</th>
            <th>Status</th>
            <th>Started</th>
            <th class="num">Events</th>
            <th class="num">LLM</th>
            <th class="num">Tools</th>
            <th class="num">Tokens</th>
          </tr>
        </thead>
        <tbody id="convoTbody">
          <tr><td colspan="8" class="empty">Loading…</td></tr>
        </tbody>
      </table>
    </div>
  </section>

</main>

<!-- ── Session detail drawer (used from both tabs) ─────────────────── -->
<div class="drawer-overlay" id="drawer" onclick="if(event.target===this) closeDrawer()">
  <aside class="drawer">
    <div class="drawer-header">
      <h2 id="drawerTitle">Session</h2>
      <span class="sub" id="drawerSid"></span>
      <div style="flex:1"></div>
      <button class="ld-btn" onclick="closeDrawer()">Close</button>
    </div>
    <div class="drawer-body" id="drawerBody">
      <div class="empty">Loading…</div>
    </div>
  </aside>
</div>

<script>
  // ── State ───────────────────────────────────────────────────────
  const state = {
    tab: 'homepage',
    agentId: '',
    hours: 168,
    sessions: [],
    activeSid: null,
  };

  // ── Tab switching ──────────────────────────────────────────────
  function switchTab(name, el) {
    state.tab = name;
    document.querySelectorAll('.tab').forEach(t =>
      t.classList.toggle('active', t.dataset.tab === name));
    document.querySelectorAll('section[data-section]').forEach(s =>
      s.classList.toggle('hidden', s.dataset.section !== name));
    refreshAll();
  }

  // ── Theme toggle ───────────────────────────────────────────────
  function toggleTheme() {
    const cur = document.documentElement.getAttribute('data-theme') || 'light';
    const next = cur === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', next);
    try { localStorage.setItem('af-theme', next); } catch(_) {}
    document.getElementById('themeToggle').textContent = next === 'dark' ? '☀️' : '🌙';
  }
  (function initTheme() {
    let saved = 'light';
    try { saved = localStorage.getItem('af-theme') || 'light'; } catch(_) {}
    document.documentElement.setAttribute('data-theme', saved);
    document.getElementById('themeToggle').textContent = saved === 'dark' ? '☀️' : '🌙';
  })();

  // ── Filter helpers ─────────────────────────────────────────────
  function onFilterChange() {
    state.agentId = document.getElementById('agentFilter').value || '';
    state.hours = parseInt(document.getElementById('hoursFilter').value, 10) || 168;
    refreshAll();
  }

  function qs() {
    const p = new URLSearchParams();
    if (state.agentId) p.set('agent_id', state.agentId);
    p.set('hours', String(state.hours));
    return p.toString();
  }

  // ── Fetchers ───────────────────────────────────────────────────
  async function loadAgents() {
    try {
      const r = await fetch('/api/dashboard/agents');
      const d = await r.json();
      const sel = document.getElementById('agentFilter');
      const cur = sel.value;
      const opts = ['<option value="">All agents</option>']
        .concat((d.agents || []).map(a =>
          `<option value="${esc(a.agent_id)}">${esc(a.agent_id)} (${a.n})</option>`));
      sel.innerHTML = opts.join('');
      sel.value = cur || state.agentId || '';
    } catch (e) { console.warn('loadAgents failed', e); }
  }

  async function loadHomepage() {
    try {
      const r = await fetch('/api/dashboard/homepage?' + qs());
      const d = await r.json();
      renderKpis(d.kpis, d.llm);
      renderConvTime(d.conversations_series, d.bucket);
      renderAgentUsage(d.agent_breakdown);
      document.getElementById('homepageSubtitle').textContent =
        windowLabel(state.hours) + (state.agentId ? ' · agent: ' + state.agentId : ' · all agents');
    } catch (e) {
      console.error('loadHomepage failed', e);
    }
  }

  async function loadConversations() {
    try {
      const r = await fetch('/api/dashboard/sessions?' + qs() + '&limit=500');
      const d = await r.json();
      state.sessions = d.sessions || [];
      renderConvoTable();
    } catch (e) {
      console.error('loadConversations failed', e);
    }
  }

  async function refreshAll() {
    await loadAgents();
    if (state.tab === 'homepage') await loadHomepage();
    else await loadConversations();
  }

  // ── Renderers ──────────────────────────────────────────────────
  function fmt(n) {
    if (n == null) return '—';
    if (typeof n === 'number' && Number.isFinite(n)) return n.toLocaleString();
    return String(n);
  }

  function renderKpis(k, llm) {
    k = k || {};
    llm = llm || {};
    document.getElementById('kpiConversations').textContent = fmt(k.conversations || 0);
    document.getElementById('kpiLlmCalls').textContent       = fmt(+llm.llm_calls || 0);
    const promptTok = +llm.input_tokens || 0;
    const respTok   = +llm.output_tokens || 0;
    document.getElementById('kpiTokens').textContent    = fmt(promptTok + respTok);
    document.getElementById('kpiTokensSub').textContent =
      'prompt: ' + fmt(promptTok) + ' · response: ' + fmt(respTok);
    const avg = +llm.llm_avg_ms || 0;
    document.getElementById('kpiAvgLatency').textContent = fmt(Math.round(avg)) + ' ms';
  }

  function renderConvTime(series, bucket) {
    const el = document.getElementById('convTimeChart');
    document.getElementById('convTimeSub').textContent =
      'Per-' + (bucket || 'day') + ' session volume · ' + windowLabel(state.hours);
    if (!series || series.length === 0) {
      el.innerHTML = '<div class="empty">No sessions in window</div>';
      return;
    }
    const max = Math.max(...series.map(s => +s.n || 0)) || 1;
    el.innerHTML = series.map(s => {
      const h = Math.max(2, Math.round((+s.n / max) * 180));
      const lbl = labelForBucket(s.bucket, bucket);
      return `<div class="bar-col">
        <div class="bar" style="height:${h}px">
          <span class="bar-tooltip">${esc(lbl)} · ${s.n}</span>
        </div>
        <div class="bar-label">${esc(lbl)}</div>
      </div>`;
    }).join('');
  }

  function renderAgentUsage(rows) {
    const el = document.getElementById('agentUsageChart');
    rows = rows || [];
    if (rows.length === 0) {
      el.innerHTML = '<div class="empty">No agent activity in window</div>';
      return;
    }
    const max = Math.max(...rows.map(r => +r.n || 0)) || 1;
    el.innerHTML = rows.map(r => {
      const h = Math.max(2, Math.round((+r.n / max) * 180));
      return `<div class="bar-col">
        <div class="bar agent" style="height:${h}px">
          <span class="bar-tooltip">${esc(r.agent_id)} · ${r.n}</span>
        </div>
        <div class="bar-label" title="${esc(r.agent_id)}">${esc(r.agent_id)}</div>
      </div>`;
    }).join('');
  }

  function renderConvoTable() {
    const tbody = document.getElementById('convoTbody');
    const search = (document.getElementById('convoSearch').value || '').toLowerCase().trim();
    const rows = (state.sessions || []).filter(s => {
      if (!search) return true;
      return [s.session_id, s.agent_id, s.status].some(v =>
        v && String(v).toLowerCase().includes(search));
    });
    document.getElementById('convoCount').textContent =
      rows.length + ' session' + (rows.length === 1 ? '' : 's');
    if (rows.length === 0) {
      tbody.innerHTML = '<tr><td colspan="8" class="empty">No sessions match.</td></tr>';
      return;
    }
    tbody.innerHTML = rows.map(s => {
      const cls = s.status === 'completed' ? 'ok' :
                  s.status === 'failed'    ? 'err' :
                  s.status === 'active'    ? 'info' : '';
      const ts = s.started_at ? new Date(s.started_at).toLocaleString() : '—';
      const tokens = ((+s.input_tokens || 0) + (+s.output_tokens || 0));
      const active = s.session_id === state.activeSid ? 'active' : '';
      return `<tr class="row ${active}" data-sid="${esc(s.session_id)}">
        <td class="mono" title="${esc(s.session_id)}">${esc(String(s.session_id).slice(0, 8))}…</td>
        <td>${esc(s.agent_id)}</td>
        <td><span class="badge ${cls}">${esc(s.status)}</span></td>
        <td>${esc(ts)}</td>
        <td class="num">${s.n_events}</td>
        <td class="num">${s.llm_count || 0}</td>
        <td class="num">${s.tool_count || 0}</td>
        <td class="num">${fmt(tokens)}</td>
      </tr>`;
    }).join('');
    tbody.querySelectorAll('tr.row').forEach(tr => {
      tr.addEventListener('click', () => openDrawer(tr.dataset.sid));
    });
  }

  // ── Drawer (drill-down) ────────────────────────────────────────
  async function openDrawer(sid) {
    state.activeSid = sid;
    document.getElementById('drawer').classList.add('open');
    document.getElementById('drawerSid').textContent = sid;
    document.getElementById('drawerBody').innerHTML = '<div class="empty">Loading…</div>';
    try {
      const r = await fetch('/api/dashboard/session/' + encodeURIComponent(sid));
      if (!r.ok) {
        document.getElementById('drawerBody').innerHTML =
          '<div class="empty">Failed to load (' + r.status + ')</div>';
        return;
      }
      const d = await r.json();
      renderDrawer(d);
    } catch (e) {
      document.getElementById('drawerBody').innerHTML =
        '<div class="empty">Error: ' + esc(String(e)) + '</div>';
    }
  }
  function closeDrawer() {
    document.getElementById('drawer').classList.remove('open');
  }

  function fmtJson(v) {
    try { return JSON.stringify(v, null, 2); } catch (_) { return String(v); }
  }

  function renderDrawer(d) {
    const s = d.session;
    const evs = d.events || [];

    const totals = evs.reduce((a, e) => {
      a.in  += +e.input_tokens  || 0;
      a.out += +e.output_tokens || 0;
      a.lat += +e.llm_latency_ms || 0;
      return a;
    }, { in: 0, out: 0, lat: 0 });

    const iconMap = { dispatch: '📥', llm: '🤖', tool: '🔧', api_call: '📡', hitl: '👤', state: '📊', error: '❌' };
    const badgeMap = { dispatch: 'info', llm: 'ok', tool: 'warn', api_call: 'info', error: 'err' };

    function extractResponse(e) {
      const om = e.output_message;
      if (om) {
        if (typeof om.content === 'string' && om.content) return om.content;
        if (Array.isArray(om.content))
          return om.content.map(c => (typeof c === 'string' ? c : (c.text || ''))).join('');
      }
      const dd = e.domain_data || {};
      return dd.response_preview || dd.response || '';
    }
    function extractQuery(e) {
      const im = e.input_messages;
      if (Array.isArray(im) && im.length > 0) {
        const last = im[im.length - 1];
        if (last && last.content)
          return typeof last.content === 'string' ? last.content : JSON.stringify(last.content);
      }
      return (e.domain_data || {}).query || '';
    }

    function asObj(v) {
      // The server now decodes JSONB columns, but be defensive in case a
      // future writer ships a stringified blob (or the row came from an
      // older event_store path).
      if (v && typeof v === 'string') {
        try { return JSON.parse(v); } catch (err) { return {}; }
      }
      return v && typeof v === 'object' ? v : {};
    }

    function renderEvent(e, idx) {
      const icon = iconMap[e.event_type] || '•';
      const bc   = badgeMap[e.event_type] || '';
      const ts   = e.created_at ? new Date(e.created_at).toLocaleTimeString() : '';
      const dd   = asObj(e.domain_data);
      e.domain_data = dd;  // normalise so downstream helpers see an object
      e.input_messages = e.input_messages && typeof e.input_messages === 'string'
        ? (() => { try { return JSON.parse(e.input_messages); } catch { return e.input_messages; } })()
        : e.input_messages;
      e.output_message = e.output_message && typeof e.output_message === 'string'
        ? (() => { try { return JSON.parse(e.output_message); } catch { return e.output_message; } })()
        : e.output_message;
      let body = '';

      if (e.event_type === 'dispatch') {
        body = `<div class="ev-body">
          <div class="ev-label">User Input</div>
          <div class="ev-text">${esc(extractQuery(e) || '(no query)')}</div>
        </div>`;
      } else if (e.event_type === 'llm') {
        const resp = extractResponse(e);
        const model = e.model_name || e.model_provider || '';
        const tok = (e.input_tokens || e.output_tokens)
          ? `${e.input_tokens || 0}↑ ${e.output_tokens || 0}↓ tok`
            + (e.llm_latency_ms ? ` · ${e.llm_latency_ms}ms` : '') : '';
        body = `<div class="ev-body">
          <div class="ev-label">Response</div>
          <div class="ev-text">${esc(resp || '(no response text stored)')}</div>
          ${tok ? `<div class="ev-label" style="margin-top:.4rem">${esc(model)} · ${esc(tok)}</div>` : ''}
        </div>`;
      } else if (e.event_type === 'tool') {
        const toolName = dd.tool_name || dd.tool || 'unknown';
        const inp = dd.input, out = dd.output;
        let inHtml = '', outHtml = '';
        if (inp !== null && inp !== undefined) {
          inHtml = `<div class="ev-label">Input</div>
            <pre class="ev-pre">${esc(typeof inp === 'string' ? inp : fmtJson(inp))}</pre>`;
        }
        if (out !== null && out !== undefined) {
          outHtml = `<div class="ev-label" style="margin-top:.4rem">Output</div>
            <pre class="ev-pre">${esc(typeof out === 'string' ? out : fmtJson(out))}</pre>`;
        }
        body = `<div class="ev-body">
          <div class="ev-label">Tool: <strong>${esc(toolName)}</strong>${
            e.tool_latency_ms ? ' · ' + e.tool_latency_ms + 'ms' : ''}</div>
          ${inHtml}${outHtml}
        </div>`;
      } else if (e.event_type === 'api_call') {
        const service  = dd.service  || 'unknown';
        const endpoint = dd.endpoint || dd.url || '';
        const method   = (dd.method || 'GET').toUpperCase();
        const status   = dd.status_code != null ? String(dd.status_code) : '';
        const latency  = e.tool_latency_ms || dd.latency_ms;
        const errored  = dd.errored === true || !!dd.error;
        const statusCls = !status ? '' : (status[0] === '2' ? 'ok' : (status[0] === '4' || status[0] === '5' ? 'err' : 'warn'));

        const meta = [];
        if (status)  meta.push(`<span class="badge ${statusCls}">${esc(status)}</span>`);
        if (latency != null) meta.push(`<span style="color:var(--ld-text-subtle)">${esc(String(latency))}ms</span>`);
        if (dd.response_bytes != null) meta.push(`<span style="color:var(--ld-text-subtle)">${esc(String(dd.response_bytes))}B</span>`);

        let previewHtml = '';
        const req = dd.request_preview;
        const res = dd.response_preview;
        if (req !== undefined && req !== null) {
          previewHtml += `<div class="ev-label" style="margin-top:.4rem">Request</div>
            <pre class="ev-pre">${esc(typeof req === 'string' ? req : fmtJson(req))}</pre>`;
        }
        if (res !== undefined && res !== null) {
          previewHtml += `<div class="ev-label" style="margin-top:.4rem">Response</div>
            <pre class="ev-pre">${esc(typeof res === 'string' ? res : fmtJson(res))}</pre>`;
        }
        const errHtml = errored && dd.error
          ? `<div class="ev-text" style="color:var(--ld-negative); margin-top:.3rem">${esc(String(dd.error))}</div>`
          : '';

        body = `<div class="ev-body">
          <div class="ev-label">
            <span class="badge info">${esc(method)}</span>
            <strong>${esc(service)}</strong>
            <span style="color:var(--ld-text-2); font-family:var(--ld-font-mono); word-break:break-all">${esc(endpoint)}</span>
          </div>
          ${meta.length ? `<div class="ev-label" style="margin-top:.3rem; display:flex; gap:.4rem; align-items:center">${meta.join('')}</div>` : ''}
          ${errHtml}${previewHtml}
        </div>`;
      } else if (e.event_type === 'state') {
        const node = dd.node_name || '';
        const outcome = dd.outcome || '';
        const outCls = outcome === 'success' ? 'ok' : outcome === 'error' ? 'err' : '';
        body = `<div class="ev-body">
          <div class="ev-label">Node: <strong>${esc(node || '?')}</strong>
            <span class="badge ${outCls}">${esc(outcome)}</span></div>
        </div>`;
      } else if (e.event_type === 'hitl') {
        const decision = dd.decision || '';
        const by = dd.decided_by || '';
        const reason = dd.reason || dd.resume_value || '';
        const dCls = decision === 'approved' ? 'ok' : decision === 'denied' ? 'err' : '';
        body = `<div class="ev-body">
          ${decision ? `<div class="ev-label">Decision:
            <span class="badge ${dCls}">${esc(decision)}</span></div>` : ''}
          ${by ? `<div class="ev-label">decided by: ${esc(by)}</div>` : ''}
          ${reason ? `<div class="ev-text" style="margin-top:.3rem">${esc(String(reason))}</div>` : ''}
        </div>`;
      } else if (e.event_type === 'error') {
        const err = dd.error || dd.error_message || '';
        body = `<div class="ev-body">
          <div class="ev-text" style="color:var(--ld-negative)">${esc(String(err || '(error)'))}</div>
        </div>`;
      } else {
        const raw = Object.keys(dd).length ? fmtJson(dd) : '';
        body = raw ? `<div class="ev-body"><pre class="ev-pre">${esc(raw)}</pre></div>` : '';
      }

      const hasPayload = e.input_messages || e.output_message
        || Object.keys(dd).length > 0 || e.llm_metadata;
      const raw = hasPayload ? `<details class="ev-raw"><summary>Raw payload</summary>
        <pre>${esc(fmtJson({
          input_messages: e.input_messages, output_message: e.output_message,
          domain_data: e.domain_data, llm_metadata: e.llm_metadata
        }))}</pre></details>` : '';

      return `<div class="ev-card ev-${esc(e.event_type)}">
        <div class="ev-hdr">
          <span>${icon}</span>
          <span class="badge ${bc}">${esc(e.event_type)}</span>
          <span style="color:var(--ld-text-subtle)">#${idx + 1}</span>
          <span style="margin-left:auto; color:var(--ld-text-subtle); font-family:var(--ld-font-mono);">${esc(ts)}</span>
        </div>
        ${body}${raw}
      </div>`;
    }

    function renderApiCallGroup(group, startIdx) {
      // Collapse a run of consecutive api_call events into one expandable
      // card.  The header summarises count / total latency / errors /
      // distinct services so users see the shape at a glance and only
      // expand when they need the per-call detail.
      const count = group.length;
      let totalMs = 0;
      let errCount = 0;
      const services = new Set();
      for (const e of group) {
        const dd = asObj(e.domain_data);
        const lat = e.tool_latency_ms || dd.latency_ms || 0;
        if (typeof lat === 'number') totalMs += lat;
        if (dd.errored === true || dd.error) errCount += 1;
        if (dd.service) services.add(String(dd.service));
        else if (dd.host)    services.add(String(dd.host));
      }
      const svcList = Array.from(services).slice(0, 4).join(', ')
        + (services.size > 4 ? ` +${services.size - 4} more` : '');
      const errBadge = errCount > 0
        ? `<span class="badge err">${errCount} failed</span>` : '';
      const ts = group[0].created_at
        ? new Date(group[0].created_at).toLocaleTimeString() : '';

      const inner = group.map((e, j) => renderEvent(e, startIdx + j)).join('');

      return `<div class="ev-card ev-api_call-group">
        <details>
          <summary class="ev-hdr" style="cursor:pointer; list-style:none;">
            <span>📡</span>
            <span class="badge info">${count} api calls</span>
            <span style="color:var(--ld-text-2)">${esc(svcList || '\u2014')}</span>
            <span style="color:var(--ld-text-subtle)">· ${totalMs}ms total</span>
            ${errBadge}
            <span style="margin-left:auto; color:var(--ld-text-subtle); font-family:var(--ld-font-mono);">${esc(ts)}</span>
          </summary>
          <div style="padding-left:1rem; border-left:2px solid var(--ld-separator); margin-top:.5rem;">
            ${inner}
          </div>
        </details>
      </div>`;
    }

    function renderTimeline(events) {
      // Single pass: emit each event normally, except runs of 2+ adjacent
      // api_call events which collapse into one group card.
      const out = [];
      let i = 0;
      while (i < events.length) {
        const e = events[i];
        if (e.event_type === 'api_call') {
          let j = i;
          while (j < events.length && events[j].event_type === 'api_call') j += 1;
          const run = events.slice(i, j);
          if (run.length >= 2) {
            out.push(renderApiCallGroup(run, i));
          } else {
            out.push(renderEvent(run[0], i));
          }
          i = j;
        } else {
          out.push(renderEvent(e, i));
          i += 1;
        }
      }
      return out.join('');
    }

    const evHtml = evs.length === 0
      ? '<div class="empty">No events recorded.</div>'
      : renderTimeline(evs);

    document.getElementById('drawerBody').innerHTML = `
      <div class="panel">
        <h3>Session metadata</h3>
        <table class="kv">
          <tr><th>Agent</th><td>${esc(s.agent_id)}</td></tr>
          <tr><th>Tenant</th><td>${esc(s.tenant_id)}</td></tr>
          <tr><th>Status</th><td><span class="badge">${esc(s.status)}</span></td></tr>
          <tr><th>Trace ID</th><td class="mono">${s.trace_id ? esc(s.trace_id) : '—'}</td></tr>
          <tr><th>Started</th><td>${s.started_at ? new Date(s.started_at).toLocaleString() : '—'}</td></tr>
          <tr><th>Ended</th><td>${s.ended_at ? new Date(s.ended_at).toLocaleString() : '—'}</td></tr>
        </table>
      </div>
      <div class="panel">
        <h3>Token totals</h3>
        <table class="kv">
          <tr><th>Input</th><td>${totals.in.toLocaleString()}</td></tr>
          <tr><th>Output</th><td>${totals.out.toLocaleString()}</td></tr>
          <tr><th>LLM latency</th><td>${totals.lat.toLocaleString()} ms</td></tr>
        </table>
      </div>
      <div class="panel">
        <h3>Pipeline Timeline (${evs.length} events)</h3>
        <div class="timeline">${evHtml}</div>
      </div>
    `;
  }

  // ── Utilities ──────────────────────────────────────────────────
  function esc(v) {
    return String(v == null ? '' : v).replace(/[&<>"']/g, c =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }
  function windowLabel(h) {
    if (h <= 2)   return 'Last 2 hours';
    if (h <= 8)   return 'Last 8 hours';
    if (h <= 72)  return 'Last 3 days';
    if (h <= 168) return 'Last 7 days';
    if (h <= 360) return 'Last 15 days';
    return 'Last 90 days';
  }
  function labelForBucket(iso, bucket) {
    if (!iso) return '';
    const d = new Date(iso);
    if (bucket === 'hour') {
      return d.getHours().toString().padStart(2, '0') + ':00';
    }
    return d.toLocaleDateString(undefined, { weekday: 'short' });
  }

  // ── Keyboard shortcuts ─────────────────────────────────────────
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeDrawer();
    if (e.key === 'r' && !e.metaKey && !e.ctrlKey
        && document.activeElement.tagName !== 'INPUT') refreshAll();
  });

  // ── Init ───────────────────────────────────────────────────────
  state.hours = parseInt(document.getElementById('hoursFilter').value, 10);
  refreshAll();
</script>
</body>
</html>
"""


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page() -> HTMLResponse:
    """Serve the single-page observability dashboard."""
    return HTMLResponse(content=_DASHBOARD_HTML)
