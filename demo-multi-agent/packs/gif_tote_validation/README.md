# GIF Tote Validation Agent

> Autonomous incident resolution for GIF Tote dimension validation — polls ServiceNow, validates item dimensions against tote constraints, routes or fixes tickets, and closes them without human intervention.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Request → Response Flow](#3-request--response-flow)
4. [Local Setup](#4-local-setup)
5. [Running the Agent](#5-running-the-agent)
6. [Running the Cron Poller](#6-running-the-cron-poller)
7. [Demo (curl)](#7-demo-curl)
8. [SOP Pack Structure](#8-sop-pack-structure)
9. [Decision Rules & Runbooks](#9-decision-rules--runbooks)
10. [Tools Reference](#10-tools-reference)
11. [Pre-Triage Gate](#11-pre-triage-gate)
12. [Deterministic vs LLM Execution](#12-deterministic-vs-llm-execution)
13. [Approval Workflow (Concord)](#13-approval-workflow-concord)
14. [Storage & Audit Trail](#14-storage--audit-trail)
15. [Configuration Reference](#15-configuration-reference)
16. [API Endpoints](#16-api-endpoints)
17. [Troubleshooting](#17-troubleshooting)
18. [Incident Detection & Trigger Patterns](#18-incident-detection--trigger-patterns)
19. [Error Handling & Edge Cases](#19-error-handling--edge-cases)
20. [Repository Map](#20-repository-map)
21. [Glossary](#21-glossary)

---

## 1. Overview

### 1.1 Problem Statement

GIF (Global Integrated Fulfilment) Tote-related incidents in ServiceNow are resolved **entirely manually** today. When a store associate reports a tote fit issue, the manual workflow involves:

| Step | Manual Action | Tool | Time |
|------|--------------|------|------|
| 1 | Analyst picks up incident from SNOW queue | ServiceNow | ~5 min |
| 2 | Read ticket, extract UPC/WIN/Store from form fields | ServiceNow | ~5 min |
| 3 | Search item in iSAM, retrieve GTIN | iSAM | ~5 min |
| 4 | Enter GTIN + Store in GIF to get dimensions | GIF / OIF | ~10 min |
| 5 | Manually compare item dims vs tote (10.5x13x20.5 IN, 34.55 LB) | Manual calc | ~5 min |
| 6a | If fits: Route ticket to GIF Picking Team | ServiceNow | ~5 min |
| 6b | If oversized: Contact merchant via email | iSAM + Email | ~15 min |
| 7 | Wait for merchant/SSOT response | Email/Slack | Hours–Days |
| 8 | Update ticket, inform requester, resolve | ServiceNow | ~5 min |
| | **Total manual effort per incident** | | **~60–90 min + wait** |

> **Key pain points:** No programmatic dimension validation (human error), no automated routing (multi-click manual), merchant outreach is ad-hoc, SSOT Slack requests are untracked, no audit trail, and SLA pressure with auto-close after 7 days.

### 1.2 Solution: Fully Autonomous Automation

This agent automates the **entire lifecycle** — from detection to resolution — with zero human intervention for standard cases:

```
ServiceNow INC → EMS Template Detection → Form Parsing → API Validation → Decision Engine → Auto-Route / Communicate → Resolve
```

```
ServiceNow Incident
        │
   Cron Poller (every 5 min)
        │
        ▼
   TriageAgent → DiagnosticAgent → DecisionAgent → ActionAgent → ClosureAgent
        │              │                │               │             │
   Extract params  GIF/IQS/Uber    Match to         Route/fix     Close
   from incident   API calls +     runbook card     ticket        ticket
                   tote fit check  (RBK-GIF-01-05)
```

### 1.3 Design Principles

| Principle | Description |
|-----------|-------------|
| **Zero-Touch for Standard Cases** | Item fits tote → auto-route to GIF Picking; no human needed |
| **Human-in-the-Loop for Exceptions** | Merchant outreach awaits response; SSOT updates require confirmation |
| **Idempotent Processing** | Re-processing same incident produces same result; no duplicate actions |
| **Full Audit Trail** | Every automated action logged with timestamps in SNOW work notes |
| **Graceful Degradation** | API failures → escalate to manual with full context attached |
| **Config-Driven** | All domain logic in SOP Pack YAML/JSON; minimal Python |

**Built on:** [Agent Factory](https://gecgithub01.walmart.com/MERCHSPACE/agent-factory) — a config-driven multi-agent runtime. All domain logic lives in the SOP Pack (`packs/gif_tote_validation/`) with minimal Python.

---

## 2. Architecture

### Components

| Component | Description | Location |
|-----------|-------------|----------|
| **FastAPI Server** | A2A endpoints, webhooks, health checks, approval callback, dashboard API | `app.py` |
| **LangGraph Topology** | Compiled `StateGraph` (triage → evidence → decision → approval → action → closure) with a Postgres checkpointer; HITL pauses via `GraphInterrupt` | `agent_factory/graph/factory.py` + `agent_factory/nodes/` |
| **LangChain Chat Surface** | `run_chat` / `run_chat_stream` — drives the `retrieval` pipeline through a `langchain.agents.AgentExecutor` | `agent_factory/runtime/chat.py` |
| **LangChain Agent Builder** | Builds a fresh `AgentExecutor` per request from pack.yaml; resolves prompts, wraps `ToolExecutor` callables as `StructuredTool`s, builds the Azure OpenAI model client | `agent_factory/runtime/builder.py` |
| **Pack Registry** | In-memory singleton holding loaded packs | `agent_factory/registry.py` (canonical: `agent_factory/pack/registry.py`) |
| **Pack Loader** | Validates and loads `pack.yaml` + `tools.yaml` + `sop-ir.json` + `policy.yaml` + `prompts/` | `agent_factory/pack_loader.py` (canonical: `agent_factory/pack/loader.py`) |
| **Tool Executor** | Resolves & runs every tool type (HTTP, SNOW, SQL, decision_matrix, threshold_check, …) declared in `tools.yaml` | `agent_factory/tools/executor.py` |
| **Evidence Extractor** | Duck-typed walker that produces a structured business audit trail — fed by shim adapters from both the chat path and the LangGraph evidence node | `agent_factory/evidence_extractor.py` |
| **SOP Pack** | YAML/JSON/Jinja2 bundle defining the entire agent behavior | `packs/gif_tote_validation/` |
| **Cron Poller** | Standalone SNOW poller that dispatches incident numbers to `/a2a/work-item/process` | `cron/snow_poller.py` |
| **Storage Stores** | `incident_store`, `audit_store`, `slack_thread_store`, `state_store` — all share one Postgres pool | `storage/*.py` |
| **Concord Client** | Approval workflow integration (Walmart Concord) | `agent_factory/integrations/concord.py` |
| **LLM Handler** | Walmart LLM Gateway auth (sandbox JWT / prod RSA) | `llm/azure_handler.py` |

### Hybrid Execution Model — LLM Where It Counts

The incident pipeline uses **only ONE LLM call** (the `DiagnosticAgent`). Triage, decision, action, and closure are all **deterministic** and config-driven — saving ≈80 % of tokens vs. a naive multi-agent flow:

```
┌──────────┐   ┌───────────────┐   ┌──────────┐   ┌─────────┐   ┌──────────┐
│ Triage   │──▶│ Diagnostic    │──▶│ Decision │──▶│ Action  │──▶│ Closure  │
│ [DET]    │   │ [LLM + Tools] │   │ [DET]    │   │ [DET]   │   │ [DET]    │
│ regex    │   │ LangChain     │   │ rule     │   │ post-   │   │ Jinja2   │
│ extract  │   │ AgentExecutor │   │ matrix   │   │ verdict │   │ template │
└──────────┘   └───────────────┘   └──────────┘   └─────────┘   └──────────┘
   ZERO         ★ ONLY LLM ★          ZERO          ZERO          ZERO
   tokens                              tokens        tokens        tokens
```

The `retrieval` pipeline (chat queries) uses a single **`RetrievalAgent`** that drives all read-only query tools through one LLM session.

### External Systems

| System | Purpose | Auth |
|--------|---------|------|
| **Walmart LLM Gateway** | LLM inference (gpt-4.1-mini) | Sandbox JWT (stage) / RSA (prod) |
| **ServiceNow Proxy** | Incident read/update | RSA-SHA256 signed Service Registry headers |
| **GIF API** (IQS GraphQL) | Item dimensions from GIF system | WM_CONSUMER.ID headers |
| **IQS Catalog API** | Gold status & product info | WM_CONSUMER.ID headers |
| **Uber API** | Supplier dimensions (non-Gold items) | WM_CONSUMER.ID headers |
| **PostgreSQL** | Conversation state, incident_log, audit_trail, slack_threads | Direct connection (optional) |
| **SMTP** (`smtp-gw1.wal-mart.com`) | Merchant outreach emails | Anonymous (no auth) |
| **Concord** | Human approval workflow (Slack-driven) | OAuth token |
| **Slack** | Real-time incident progress notifications | Bot token (`SLACK_BOT_TOKEN`) |

---

## 3. Request → Response Flow

This section traces the **complete lifecycle** of every supported request — from the moment it lands at FastAPI to the moment a response is returned (and side-effects like Slack messages, approval requests, and audit rows are written).

### 3.1 The Three Top-Level Flows

| Flow | Trigger | Pipeline | LLM Calls | Deterministic Steps |
|------|---------|----------|-----------|---------------------|
| **Chat (retrieval)** | `POST /a2a/invoke` or `/a2a/invoke-stream` | `retrieval` (1 agent, round-robin) | 1 (RetrievalAgent + tools) | State load/save, evidence extraction |
| **Incident** | `POST /a2a/work-item/process`, SNOW webhook, or cron | `incident` (5 agents on paper, but only DiagnosticAgent runs the LLM) | 1 (DiagnosticAgent + tools) | Pre-triage, triage, decision, action, closure, safety nets, status mapping |
| **Approval callback** | `POST /a2a/approval/complete` | `run_approved_actions()` (no agent) | 0 | Tool execution per approved action, Slack updates |

### 3.2 Master Sequence Diagram — Incident Flow

```
 Cron / SNOW Webhook                                                Slack
   │   POST /a2a/work-item/process                                     ▲
   │   { "incident_number": "INC52148837" }                           │
   ▼                                                                  │
┌─────────────────────────── FastAPI app.py ────────────────────────┐ │
│ 1. Generate session_id, message_id                                │ │
│ 2. set_full_context(user_id, session_id, …)                       │ │
│ 3. postgres_state_manager.insert_message(msg_type="user")         │ │
│ 4. _run_incident_via_langgraph(pack_id, inc_num, session_id, …)   │ │
│ 5. → packs/<pack_id>/graph.py (compiled LangGraph + Postgres      │ │
│       checkpointer)                                               │ │
└────────────────────────────────────┬──────────────────────────────┘ │
                                     │                                │
                                     ▼                                │
┌──────────────── LangGraph: run_incident_by_number ─────────────────┐│
│ A. _pre_triage(inc_num)                                            ││
│    ├─ ToolExecutor.get_callable("DIAG-SNOW-01")                    ││
│    ├─ tool_fn(incident_number=inc_num)  ─────────► ServiceNow ─────┐│
│    ├─ Validate assignment_group / keywords / category              ││
│    └─ if FAIL → mark_skipped, log "pre_triage_skip", return        ││
│       if PASS → continue                                           ││
│                                                                    ├┼──► slack_notifier.start_thread()
│ B. Build incident_text from SNOW data                              ││
│ C. self.run_incident(incident_text, snow_data)                     ││
└────────────────────────────────────┬───────────────────────────────┘│
                                     │                                │
                                     ▼                                │
┌──────────────────── LangGraph incident topology ───────────────────┐│
│                                                                    ││
│  ┌──────────────────────────────────────────────────────────┐      ││
│  │ NODE 1: triage  [ZERO TOKENS]                            │      ││
│  │   regex extract: INC#, store_number, UPC, symptom        │      ││
│  │   classify symptom from short_description keywords       │      ││
│  └──────────────────────────────────────────────────────────┘      ││
│                                                                    ├┼──► incident_store.create_incident()
│                                                                    ├┼──► audit_store.log_event("pipeline_start")
│  ┌──────────────────────────────────────────────────────────┐      ││
│  │ NODE 2: evidence  ★ ONLY LLM CALL ★                      │      ││
│  │                                                          │      ││
│  │   builder = LangChainAgentBuilder(pack)                  │      ││
│  │   executor = builder.build_single_executor(              │      ││
│  │       "incident", "diagnostic")                          │      ││
│  │                                                          │      ││
│  │   ┌──── LangChainAgentBuilder._assemble_executor ────┐   │      ││
│  │   │ a. _resolve_prompt(pack, agent_spec)             │   │      ││
│  │   │    → render_prompt("diagnostic.j2",              │   │      ││
│  │   │      build_pack_context(pack))                   │   │      ││
│  │   │ b. _wrap_tools_for_langchain(agent_spec.tools)   │   │      ││
│  │   │    → StructuredTool.from_function(coroutine=…)   │   │      ││
│  │   │      for each ToolExecutor callable              │   │      ││
│  │   │      ([DIAG-SNOW-01, DIAG-UBERKEYS-01,           │   │      ││
│  │   │       DIAG-API-01..03, DIAG-LOGIC-01])           │   │      ││
│  │   │ c. _build_model_client()                         │   │      ││
│  │   │    → AzureChatOpenAI w/ fresh SOA headers        │   │      ││
│  │   │      (per request — see §3.6)                    │   │      ││
│  │   │ d. create_tool_calling_agent(model, tools,       │   │      ││
│  │   │      ChatPromptTemplate.from_messages([          │   │      ││
│  │   │        ("system", rendered_prompt),              │   │      ││
│  │   │        ("human", "{input}"),                     │   │      ││
│  │   │        MessagesPlaceholder("agent_scratchpad")]))│   │      ││
│  │   │ e. AgentExecutor(agent, tools,                   │   │      ││
│  │   │      max_iterations=25,                          │   │      ││
│  │   │      return_intermediate_steps=True)             │   │      ││
│  │   └──────────────────────────────────────────────────┘   │      ││
│  │                                                          │      ││
│  │   result = await executor.ainvoke(                       │      ││
│  │       {"input": enriched_task, "chat_history": []},      │      ││
│  │       config={"callbacks": [token_usage_callback]})      │      ││
│  │                                                          │      ││
│  │   ┌──── INSIDE AgentExecutor.ainvoke ───────────┐        │      ││
│  │   │ ① LLM emits AIMessage(tool_calls=[…])       │        │      ││
│  │   │ ② StructuredTool coroutine invoked          │        │      ││
│  │   │   - render URL/body/headers from {{vars}}   │        │      ││
│  │   │   - resolve auth (bearer/api_key/SOA/…)     │        │      ││
│  │   │   - httpx.request(...) w/ retry+backoff     │  ──────┼──────┼┼──► GIF / IQS / Uber / SNOW
│  │   │   - response_processor → outcome code       │        │      ││
│  │   │   - return JSON to LLM as ToolMessage       │        │      ││
│  │   │ ③ LLM observes ToolMessage(content=…)       │        │      ││
│  │   │ ④ Repeat ① for next tool, or…               │        │      ││
│  │   │ ⑤ LLM emits final AIMessage(content=…)      │        │      ││
│  │   │   → AgentExecutor returns {output,          │        │      ││
│  │   │     intermediate_steps}                     │        │      ││
│  │   └─────────────────────────────────────────────┘        │      ││
│  └──────────────────────────────────────────────────────────┘      ││
│                                                                    ├┼──► slack_notifier "🔧 Running diagnostics…"
│  ┌──────────────────────────────────────────────────────────┐      ││
│  │ STEP 3: extract_evidence(result, pack_id)  [ZERO TOKENS] │      ││
│  │   walk result.messages → produce structured list:        │      ││
│  │   [{type: tool_call, tool, args}, …                      │      ││
│  │    {type: tool_result, tool, outcome, status,            │      ││
│  │     result_preview}, …                                   │      ││
│  │    {type: agent_message, agent, content_preview}]        │      ││
│  │   summarise_pipeline_health() → success|partial|failed   │      ││
│  └──────────────────────────────────────────────────────────┘      ││
│                                                                    ││
│  ┌──────────────────────────────────────────────────────────┐      ││
│  │ STEP 4: _run_safety_checks()  [ZERO TOKENS]              │      ││
│  │   if dim data present but tote-fit not run               │      ││
│  │     → run DIAG-LOGIC-01 deterministically                │      ││
│  │     → append synthetic tool_result to evidence           │      ││
│  └──────────────────────────────────────────────────────────┘      ││
│                                                                    ││
│  ┌──────────────────────────────────────────────────────────┐      ││
│  │ STEP 5: _deterministic_decision(evidence, pack)          │      ││
│  │   build observations: {tool_id: outcome, …}              │      ││
│  │   find decision_matrix tool spec in pack.tools_manifest  │      ││
│  │   first-match: rule.conditions vs observations           │      ││
│  │   → {matched_rule, runbook, description, confidence}     │      ││
│  └──────────────────────────────────────────────────────────┘      ││
│                                                                    ├┼──► incident_store.update_decision()
│  ┌──────────────────────────────────────────────────────────┐      ││
│  │ STEP 6: _deterministic_action_closure()  [ZERO TOKENS]   │      ││
│  │   a. _extract_fields_from_evidence(evidence, pack)       │      ││
│  │      → fields: {gtin, height, …, verdict, …}             │      ││
│  │   b. determine verdict (verdict_field → inference rules) │      ││
│  │   c. post_verdict_actions: e.g. iSAM merchant lookup     │  ────┼┼──► iSAM (QRY-ISAM-01)
│  │   d. Jinja2 render closure_<verdict>.j2                  │      ││
│  └──────────────────────────────────────────────────────────┘      ││
│                                                                    ││
│  ┌──────────────────────────────────────────────────────────┐      ││
│  │ STEP 7: status mapping + safety-net override             │      ││
│  │   _extract_closure_status() → "pending_review", etc.     │      ││
│  │   apply safety_net_overrides (e.g. OVERSIZED forces      │      ││
│  │     pending_review even if LLM said resolved)            │      ││
│  │   pipeline_status (success/partial/failed) → final       │      ││
│  └──────────────────────────────────────────────────────────┘      ││
│                                                                    ├┼──► incident_store.update_resolution()
│                                                                    ├┼──► audit_store.log_event("pipeline_end")
│                                                                    ├┼──► slack_notifier "✅ Final Status …"
│  ┌──────────────────────────────────────────────────────────┐      ││
│  │ STEP 8: Concord approval (if pending_review)             │      ││
│  │   import packs.gif_tote_validation.concord_client        │  ────┼┼──► Concord
│  │   findings_extractors → build findings dict              │      ││
│  │   start_approval_process(callback=/a2a/approval/complete)│      ││
│  └──────────────────────────────────────────────────────────┘      ├┼──► slack_notifier "📋 Review in Concord"
│                                                                    ││
│  return (closure_content, team_state)                              ││
└────────────────────────────────────┬───────────────────────────────┘│
                                     │                                │
                                     ▼                                │
┌─────────────────────────── FastAPI app.py ────────────────────────┐│
│ 6. postgres_state_manager.insert_message(msg_type="assistant")    ││
│ 7. JSONResponse({                                                 ││
│      incident_number, status, response, session_id,               ││
│      time_taken, agent_name                                       ││
│    })                                                             ││
└────────────────────────────────────┬──────────────────────────────┘│
                                     │                                │
                                     ▼                                │
                              Caller (cron/curl)                      │
                                                                      │
       (later — human reviews in Concord)                             │
                                     │                                │
                                     ▼                                │
                       POST /a2a/approval/complete                    │
                                     │                                │
                                     ▼                                │
                runtime.run_approved_actions(actions)                 │
                ├─ for each action in pack.config.approved_actions:   │
                │    QRY-SNOW-02 (work_notes / state / group / …)     │
                │    ACT-EMAIL-01 (merchant outreach)                 │
                └─ slack_notifier ───────────────────────────────────►┘
```

### 3.3 Chat / Retrieval Flow (`/a2a/invoke`)

```
POST /a2a/invoke { "query": "…" }
    │
    ▼
app.py invoke()
    ├─ insert user message (Postgres)
    └─ runtime.chat.run_chat(query, session_id)
            │
            ▼
        LangChainAgentBuilder(pack).build_pipeline_executor("retrieval")
            ├─ resolve RetrievalAgent (prompt = retrieval.j2)
            ├─ wrap tools = [QRY-SNOW-01, QRY-SNOW-02, QRY-GIF-01,
            │                QRY-IQS-01, QRY-UBER01] as StructuredTools
            ├─ build AzureChatOpenAI model client (fresh SOA per request)
            └─ create_tool_calling_agent → AgentExecutor
                (with `chat_history` MessagesPlaceholder for multi-turn)
            │
            ▼
        executor.ainvoke({input: query, chat_history: prior_msgs})
                                              ← LLM call with tool access
            │
            ▼
        extract_evidence(intermediate_steps, final_output, ...)
        team_state["_token_usage"], ["_evidence"]
            │
            ▼
        return (content, team_state)
    │
    ▼
insert assistant message (Postgres)
JSONResponse({ response, session_id, message_id, time_taken })
```

### 3.4 Streaming Variant (`/a2a/invoke-stream`)

Same flow as 3.3 but `runtime.chat.run_chat_stream(...)` is iterated.  The async iterator yields incremental string chunks (sourced from LangChain's `astream_events(version="v2")` `on_chat_model_stream` events) and a terminating `("done", team_state)` sentinel.  Each yielded value is converted into an SSE event:

| Yielded value | SSE event | Payload |
|---------------|-----------|---------|
| `str` chunk | `chunk` | `{"content": "<delta>"}` |
| Initial event | `log` | `{"message": "Starting…", "trace_id"}` |
| Periodic | `progress` | `{"progress": 25}` |
| `("done", team_state)` | `done` | `{"user_id", "session_id", "agent_name"}` |
| Exception | `error` | `{"error", "error_type", "trace_id"}` |

### 3.5 Approval Callback Flow (`/a2a/approval/complete`)

```
Concord ──► POST /a2a/approval/complete
            { incident_number, approved, approver,
              selected_actions: "send_email,add_work_notes,set_pending",
              notes, concord_process_id }
                │
                ▼
       audit_store.log_event("approval_callback", status=approved/rejected)
                │
        ┌───────┴───────┐
       reject          approve
        │               │
        │               ▼
        │       runtime.run_approved_actions(inc_num, actions, approver, notes)
        │           │
        │           ▼
        │       for each action_id with True in actions:
        │           pack.config.approved_actions.<action_id>:
        │             - tool: QRY-SNOW-02 / ACT-EMAIL-01 / …
        │             - params: { state, assignment_group, … } (static)
        │             - closure_fields: [gtin, merchant_email, …]
        │           ↓
        │       ToolExecutor.get_callable(tool_id)(params + closure_fields)
        │           ↓
        │       Slack post (success/failure per action)
        ▼
slack_notifier.reply("✅ Actions completed" / "❌ Failed")
JSONResponse({ status: "executed"|"rejected", actions_executed, response })
```

### 3.6 SOA-Signed LLM Auth — Why Fresh Per Request

The Walmart LLM Gateway in **production** uses RSA-SHA256 signed Service Registry headers. These headers contain a timestamp that is rejected after ≈60 seconds. To prevent `401 Signature expired`:

* **Each `AgentExecutor` instance** is **fresh per request** — both `runtime.chat.run_chat` (chat path) and the LangGraph evidence node call `LangChainAgentBuilder(pack).build_*_executor(...)` inline, never caching.
* **`LangChainAgentBuilder._build_model_client()`** is called every time an executor is built — so SOA headers are regenerated on every request.
* The model client is **NEVER cached** across requests.

In sandbox mode (`SANDBOX_GENAIAPI_KEY`), the JWT lifetime is much longer; refreshing per-request is harmless.

### 3.7 Tool Execution Internals (Inside the AgentExecutor Loop)

When the `DiagnosticAgent` calls `DIAG-API-01` (GIF API), here's what `ToolExecutor` does:

```
LLM emits FunctionCall(name="diag_api_01", arguments='{"gtin":"00681…","store_id":"5260"}')
    │
    ▼
ToolExecutor wrapper (built by _build_typed_wrapper)
    │
    ├─ logger.info("[DEBUG] Tool invoked: DIAG-API-01 type=http_api")
    │
    ▼
ToolExecutor.execute_http_api("DIAG-API-01", params)
    │
    ├─ enriched_params = _enrich_params_from_config(params, spec)
    │     # injects {{GIF_API_URL}}, {{GIF_CONSUMER_ID}}, _request_id, …
    │
    ├─ url     = _render_template(spec.url_template, enriched_params)
    ├─ headers = {k: _render_template(v, …) for k,v in spec.headers.items()}
    ├─ body    = json.loads(_render_template(json.dumps(spec.body_template), …))
    │
    ├─ auth_headers = _resolve_auth_headers(spec.auth, enriched_params)
    │     # bearer / api_key / basic / soa → reads secrets.toml at call time
    │
    ├─ _retry_http(coro_factory, spec.retry, "DIAG-API-01")
    │     # exponential backoff: max_attempts × backoff_seconds × backoff_multiplier
    │     # retryable_status_codes: [429, 502, 503, 504]
    │
    ▼  ──────────────────────────────► GIF / IQS / Uber API
    │
    ├─ response_processor (field_presence | count_filter | passthrough | …)
    │     applies extract_fields → flat dict
    │     applies outcome_rules → "DATA_FOUND" | "DATA_NOT_FOUND" | …
    │     applies error_outcomes on HTTP error codes
    │
    └─ json.dumps(result) → returned to LLM as the tool result
```

Tool types supported by the executor:
`http_api`, `servicenow`, `python_function`, `sql_query`, `bigquery_query`,
`graphql`, `cassandra`, `redis`, `jira`, `kafka`, `elasticsearch`, `a2a`,
`batch`, `decision_matrix`, `threshold_check`.

### 3.8 What Lives in `team_state` After Each Run

```python
team_state = {
    # Injected by the chat path (langchain_chat) / LangGraph nodes:
    "_token_usage":     {"prompt_tokens", "completion_tokens", "total_tokens"},
    "_agent_tokens":    {"DiagnosticAgent": {"prompt_tokens", "completion_tokens", "total_tokens"}},
    "_evidence":        [{"type": "tool_call"|"tool_result"|"agent_message"|"decision", …}],
    "_pipeline_health": {"pipeline_status", "tool_calls", "tool_failures", "failed_tools"},
    "_decision":        {"matched_rule", "runbook", "description", "confidence", "observations_used"},
    "_closure_content": "<rendered Jinja2 string>",

    # Pre-triage skip path only:
    "_skipped":   True,
    "reason":    "<skip reason>",
    "_retryable": True,    # set when LLM gateway timed out
    "_error":     "llm_timeout",
}
```

The `_evidence` list is the durable business audit trail — it survives into `incident_store.actions_taken` and `audit_store` events.

---

## 4. Local Setup

### Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.12+ | Required |
| pip | latest | For dependency installation |
| Git | any | For cloning |

### Installation

```bash
# 1. Clone the monorepo (this pack lives at packs/gif_tote_validation/)
git clone https://gecgithub01.walmart.com/item-ops/matbot-multi-agents.git
cd matbot-multi-agents

# 2. Create a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Verify the pack loads
python3 -c "
import sys; sys.path.insert(0, '.')
from agent_factory.pack_loader import load_pack
pack = load_pack('gif_tote_validation', packs_root='packs')
print(f'Pack: {pack.pack_id} | Tools: {len(pack.tools_manifest.tools)} | Valid: {pack.validation.valid}')
print(f'Warnings: {len(pack.validation.warnings)} | Errors: {len(pack.validation.errors)}')
"
# Expected: Pack: gif_tote_validation | Tools: 13 | Valid: True | Warnings: 0 | Errors: 0
```

### Secrets Configuration

The file `agent_factory/infrastructure/secrets.toml` contains all credentials. It is **gitignored** — you must create it locally.

Key sections to configure:

| Section | Purpose | Status |
|---------|---------|--------|
| `[default]` | Agent identity | Pre-configured |
| `[default.azure_chat]` | Walmart LLM Gateway (sandbox JWT) | Pre-configured for stage |
| `[default.postgresql]` | Conversation state DB | Pre-configured (optional) |
| `[default.servicenow_proxy]` | SNOW proxy with RSA signing | Needs `pem_path` and `ca_cert_path` |
| `[default.gif_api]` | GIF API (IQS GraphQL) | Pre-configured |
| `[default.iqs_api]` | IQS Catalog API | Pre-configured |
| `[default.uber_api]` | Uber supplier dims API | Pre-configured |
| `[default.smtp]` | Email relay (anonymous) | Pre-configured (`smtp-gw1.wal-mart.com:25`) |
| `[default.slack]` | Slack #ssot-gif channel | Needs bot token |
| `[default.cron_poller]` | Cron config | Pre-configured (`localhost:8000`) |

**Minimum for demo (LLM only — no live SNOW/API calls):**

```toml
[default]
AGENT_NAME = "gif_tote_validation_agent"

[default.azure_chat]
LIGHTRAG_MODEL = "gpt-4.1-mini"
LIGHTRAG_API_VERSION = "2024-10-21"
LIGHTRAG_AZURE_ENDPOINT = "https://wmtllmgateway.stage.walmart.com/wmtllmgateway"
SANDBOX_GENAIAPI_KEY = "<your-sandbox-jwt>"
```

**For live SNOW operations, also set:**

```toml
[default.servicenow_proxy]
base_url = "https://sm.prod.us.walmart.net/api/wms"
consumer_id = "<your-consumer-id>"
auth_token = "Basic <base64>"
key_version = "1"
pem_path = "/path/to/servicereg_private_prod.pem"
ca_cert_path = "/path/to/ca-bundle.crt"
```

---

## 5. Running the Agent

### Development (with hot-reload)

```bash
./run_dev.sh
```

This runs:
```bash
ENV_FOR_DYNACONF=development \
DYNACONF_AGENT_NAME=gif_tote_validation_agent \
DEFAULT_PACK_ID=gif_tote_validation \
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

### Verify it's running

```bash
# Health check
curl http://localhost:8000/healthz

# Pack health (tool binding stats)
curl http://localhost:8000/api/factory/health

# Tool availability
curl http://localhost:8000/api/factory/tools

# Agent discovery card
curl http://localhost:8000/.well-known/agents.json
```

---

## 6. Running the Cron Poller

The cron poller is a **standalone process** that polls ServiceNow for GIF tote incidents and dispatches them to the agent.

### Single poll cycle

```bash
python cron/snow_poller.py
```

### Continuous mode (every 5 minutes)

```bash
python cron/snow_poller.py --continuous --interval 300
```

### Custom interval

```bash
# Poll every 60 seconds (for testing)
python cron/snow_poller.py --continuous --interval 60
```

### How it works

1. Queries SNOW for incidents in `MerchantOps - Item Setup/Maintenance` with:
   - `short_descriptionLIKEincorrect dimensions` (modified by analysts)
   - `short_descriptionLIKEEMS GIF 2.0` (original EMS templates)
2. Filters for GIF tote-related incidents using EMS pattern matching
3. Deduplicates using a local ledger (`cron/processed_incidents.json`)
4. Builds a structured JSON payload with extracted UPC, GTIN, store, etc.
5. POSTs to `http://localhost:8000/a2a/work-item/process` with payload `{"incident_number": "INC..."}`

### Deduplication

Processed incidents are tracked in `cron/processed_incidents.json`. To reprocess:

```bash
# Clear the ledger
rm cron/processed_incidents.json

# Or remove a specific incident
python3 -c "
import json
ledger = json.load(open('cron/processed_incidents.json'))
del ledger['INC52148837']
json.dump(ledger, open('cron/processed_incidents.json', 'w'), indent=2)
"
```

---

## 7. Demo (curl)

You can send a payload directly to the agent without the cron poller. This is useful for demos and testing.

### Process an incident by number (real SNOW lookup)

The recommended endpoint for both production and demos. The agent fetches the incident from ServiceNow, runs pre-triage, then the full pipeline:

```bash
curl -s -X POST http://localhost:8000/a2a/work-item/process \
  -H "Content-Type: application/json" \
  -H "X-User-ID: demo-user" \
  -H "X-Session-ID: demo-001" \
  -d '{
    "incident_number": "INC52148837"
  }' | python3 -m json.tool
```

> Requires `[default.servicenow_proxy]` to be configured (PEM, CA cert, consumer ID). The cron poller uses this exact endpoint.

### Streaming chat (Server-Sent Events)

```bash
curl -N -X POST http://localhost:8000/a2a/invoke-stream \
  -H "Content-Type: application/json" \
  -H "X-User-ID: demo-user" \
  -d '{
    "query": "Show me the last 5 GIF tote incidents and summarise the verdicts"
  }'
```

### Retrieval (ask a question — synchronous)

```bash
curl -s -X POST http://localhost:8000/a2a/invoke \
  -H "Content-Type: application/json" \
  -H "X-User-ID: demo-user" \
  -d '{
    "query": "What are the standard GIF tote dimensions and weight limits?"
  }' | python3 -m json.tool
```

### Approval callback (called by Concord)

```bash
curl -s -X POST http://localhost:8000/a2a/approval/complete \
  -H "Content-Type: application/json" \
  -d '{
    "incident_number": "INC52148837",
    "approved": true,
    "approver": "jane.doe@walmart.com",
    "selected_actions": "send_email,add_work_notes,set_pending",
    "notes": "Approved — confirm dimensions with merchant",
    "concord_process_id": "concord-12345"
  }' | python3 -m json.tool
```

---

## 8. SOP Pack Structure

All domain logic lives in `packs/gif_tote_validation/`:

```
packs/
└── gif_tote_validation/          # SOP Pack — declarative config + minimal Python
    ├── pack.yaml                 # Pipeline definitions, agent assignments, model config
    ├── tools.yaml                # Declarative tool definitions
    ├── sop-ir.json               # Diagnostics, decision rules, runbooks
    ├── policy.yaml               # Approval gates, blast radius, feature flags
    ├── eval_cases.json           # Regression test cases
    ├── prompts/
    │   ├── triage.j2             # TriageAgent system prompt
    │   ├── diagnostic.j2         # DiagnosticAgent system prompt
    │   ├── decision.j2           # DecisionAgent system prompt (with decision table)
    │   ├── action.j2             # ActionAgent system prompt (runbook cards)
    │   ├── closure.j2            # ClosureAgent system prompt
    │   └── retrieval.j2          # RetrievalAgent system prompt
    ├── templates/                # Closure / email Jinja2 templates
    ├── state.py                  # IncidentState factory + schema
    ├── email_sender.py           # Pack-specific email helper
    └── isam_mock.py              # Mock iSAM merchant lookup (until real API)
```

> Graph topology and node logic are pack-agnostic — they live in `agent_factory/graph/factory.py` and `agent_factory/nodes/` and are driven entirely by `pack.yaml` + `sop-ir.json`.

---

## 9. Decision Rules & Runbooks

### Tote Constraints

| Dimension | Limit |
|-----------|-------|
| Height | 10.5 IN |
| Width | 13.0 IN |
| Depth | 20.5 IN |
| Max Weight | 34.55 LB |

The tote fit engine uses **sorted-dimension comparison**: both item and tote dimensions are sorted ascending and compared rank-by-rank. This finds the most permissive orientation.

### Decision Matrix

| Rule | Condition | Runbook | Action |
|------|-----------|---------|--------|
| RULE-1 | `DIAG-LOGIC-01 = FITS_TOTE` | RBK-GIF-01 | Auto-route to GIF Picking Team |
| RULE-2 | `OVERSIZED` + merchant confirms correct | RBK-GIF-02 | Route to GIF Picking Team |
| RULE-3 | `OVERSIZED` + needs update + `GOLD` | RBK-GIF-03 | Post to #ssot-gif Slack, pending |
| RULE-4 | `OVERSIZED` + needs update + `NOT_GOLD` | RBK-GIF-04 | iSAM dimension update |
| FALLBACK | Any error or no match | RBK-GIF-05 | Escalate to manual review |

### Decision Flowchart

```
  Incident arrives
       │
  ┌────▼────┐
  │Parse &  │
  │Extract  │
  └────┬────┘
       │
  ┌────▼────┐    API Error?   ┌────────────┐
  │Diagnostic│───────────────▶│ RBK-GIF-05 │
  │API Calls │                │ Escalate   │
  └────┬────┘                └────────────┘
       │
  ┌────▼────────┐
  │Tote Fit     │
  │Check        │
  └──┬──────┬───┘
     │      │
  FITS    OVERSIZED
     │      │
  RBK-01  Merchant
  Route   Outreach
            │
     ┌──────┴───────┐
  Correct?     Needs Update?
     │              │
  RBK-02      ┌─────┴────┐
  Route      Gold?    Supplier?
              │          │
           RBK-03     RBK-04
           SSOT       iSAM
```

---

## 10. Tools Reference

### Diagnostic Tools (read-only)

| Tool ID | Type | Description |
|---------|------|-------------|
| `DIAG-SNOW-01` | servicenow | Fetch incident by number from SNOW proxy |
| `DIAG-API-01` | graphql | GIF API — item dimensions (IQS GraphQL) |
| `DIAG-API-02` | http_api | IQS Catalog — Gold status check |
| `DIAG-API-03` | http_api | Uber API — supplier dimensions (non-Gold) |
| `DIAG-LOGIC-01` | python_function | Tote fit check (sorted-dimension comparison) |

### Action Tools (write operations)

| Tool ID | Type | Description | Risk |
|---------|------|-------------|------|
| `QRY-SNOW-01` | servicenow | Search/list SNOW incidents | low |
| `QRY-SNOW-02` | servicenow | Update SNOW incident (work notes, state, group) | medium |
| `QRY-GIF-01` | graphql | Query GIF API (ActionAgent) | low |
| `QRY-IQS-01` | http_api | Query IQS Catalog (ActionAgent) | low |
| `QRY-UBER01` | http_api | Query Uber API (ActionAgent) | low |
| `QRY-ISAM-01` | http_api | iSAM dimension update (feature-flagged off) | high |
| `ACT-EMAIL-01` | python_function | Merchant outreach email via SMTP (`smtp-gw1.wal-mart.com:25`) | medium |

### Decision Tools

| Tool ID | Type | Description |
|---------|------|-------------|
| `DIAG-DECISION-MATRIX` | python_function | Hybrid rules engine + RAG fallback |
| `DIAG-RAG-FALLBACK` | python_function | RAG-based decision when rules have no match |

---

## 11. Pre-Triage Gate

The **pre-triage gate** is a *fail-closed* validation step that runs **before** any LLM is involved. Its job: cheaply discard incidents that don't belong to this agent so we never waste tokens on an out-of-scope ticket.

### 11.1 Why Fail-Closed?

* **Cost** — Each LLM call burns tokens; rejecting irrelevant tickets at the door saves >95% of costs on a noisy SNOW queue.
* **Safety** — A misrouted ticket may contain unrelated PII, internal change requests, or be assigned to a team that already owns it. Touching it would be confusing.
* **Determinism** — Pre-triage is regex/string-matching only — predictable, traceable, no LLM hallucination risk.

### 11.2 Configuration (`pack.yaml` → `pre_triage`)

```yaml
pre_triage:
  enabled: true
  snow_tool: DIAG-SNOW-01            # Which tool fetches the incident
  assignment_groups:                  # Substring match (case-insensitive)
    - "MerchantOps - Item Setup/Maintenance"
    - "GIF"
  keywords:                           # ANY match in short_description / description
    - "dimension"
    - "tote"
    - "GIF"
    - "GTIN"
    - "incorrect"
    - "does not fit"
  categories:                         # ANY match (empty list = no filter)
    - "GIF"
    - "Software"
    - "Application"
  routed_groups:                      # Already-routed groups → skip with reason
    "ops - ecomfulfillment - picking": "GIF Picking Team"
    "ops - ecomfulfillment": "eComFulfillment"
  slack_notification_keywords:        # Trigger Slack thread BEFORE triage runs
    - "tote"
    - "incorrect dimensions"
    - "ems gif"
    - "gif 2.0"
```

### 11.3 The Three Validation Checks

The LangGraph `pre_triage` node (`agent_factory/nodes/pre_triage.py`) runs them in this order:

| # | Check | Pass Condition | Fail Action |
|---|-------|----------------|-------------|
| 1 | **Assignment group** | SNOW `assignment_group` substring matches any in `assignment_groups` | If group is in `routed_groups` → skip with the friendly reason; otherwise return `wrong_group` |
| 2 | **Keywords** | `short_description` OR `description` contains ANY keyword | Skip with `no_keyword_match` |
| 3 | **Category** | `category` contains ANY entry in `categories` (skipped if list empty) | Skip with `wrong_category` |

If **all three** pass → continue to the LLM pipeline. If **any** fails → call `incident_store.mark_skipped(reason)`, log an audit event `pre_triage_skip`, and return early.

### 11.4 Slack Notification Trigger

Independent of pass/fail, if `short_description` contains any `slack_notification_keywords`, a thread is opened before triage runs (`slack_notifier.start_thread`). This means even **skipped** incidents are visible to the on-call channel, so humans can spot mis-classification.

### 11.5 Skip Path Side-Effects

When pre-triage skips an incident, the following side-effects are guaranteed:

```
incident_store.mark_skipped(incident_number, reason="wrong_group", details="…")
audit_store.log_event("pre_triage_skip", incident_number, payload={"reason": "…"})
slack_notifier.reply(thread_ts, "⏭️ Skipped: <reason>")  # if thread open
```

The `team_state` returned by `_pre_triage` carries `_skipped: true` and a human-readable `reason`, which the API endpoint forwards as the response status.

---

## 12. Deterministic vs LLM Execution

This pack is deliberately **mostly deterministic**. Only one of the five named pipeline stages actually invokes an LLM. The rest are config-driven Python that runs in milliseconds with zero token cost.

### 12.1 Stage-by-Stage Map

| Stage | LLM? | Driven By | What Actually Happens |
|-------|------|-----------|----------------------|
| **Pre-triage** | ❌ | `pack.config.pre_triage` (YAML) | Regex / substring matching against SNOW fields |
| **Triage** | ❌ | `pack.config.triage_extraction` (YAML) | Regex extraction of INC#, GTIN, UPC, store, symptom |
| **Diagnostic** | ✅ | `prompts/diagnostic.j2` + `tools.yaml` (DIAG-* tools) | LangChain `AgentExecutor` calls GIF/IQS/Uber APIs and tote-fit logic in a multi-turn LLM loop |
| **Decision** | ❌ | `tools.yaml::DIAG-DECISION-MATRIX` (rules table) | First-match rule against observation map produced by Diagnostic |
| **Action** | ❌ | `pack.config.approved_actions` + `verdict_actions` | Lookup verdict → list of action IDs; defer to Concord approval (no auto-execute) |
| **Closure** | ❌ | `templates/closure_<verdict>.j2` (Jinja2) | Template render with fields extracted from evidence |

### 12.2 Token Economy

A "naive" 5-LLM-call pipeline would burn ~30–50K tokens per incident. This hybrid design typically uses **3–8K tokens per incident** — an **80%+ reduction** — because:

1. The LLM is **only asked to call tools and report**, not to make decisions or write closure text.
2. Decision logic lives in YAML and is parsed once, applied in microseconds.
3. Closure narrative is templated, ensuring brand-consistent ticket updates.

### 12.3 Why the LLM Still Helps

The Diagnostic stage benefits from the LLM because:

* **Tool sequencing isn't always linear** — sometimes Uber API is needed (non-Gold), sometimes not (Gold). The LLM picks the right next tool from outcome codes.
* **Robustness to messy inputs** — incident text from EMS forms varies wildly; the LLM tolerates layout drift better than fixed regex.
* **Self-recovery** — on a 4xx/5xx tool error the LLM can re-attempt with corrected params.

### 12.4 Where Determinism Wins

* **Decisions are auditable** — `evidence._decision.matched_rule` lets a reviewer see exactly which rule fired and why.
* **Closure text is consistent** — every "OVERSIZED" ticket gets the same wording, so SLAs and reports stay clean.
* **Safety nets** — even if the LLM hallucinates "resolved", deterministic post-checks (e.g., `OVERSIZED → pending_review`) override the verdict before it reaches SNOW.

### 12.5 The Safety-Net Override

After the LLM emits its closure JSON, `runtime._extract_closure_status()` derives a status. Then `safety_net_overrides` rules from `pack.yaml` run:

```yaml
safety_net_overrides:
  - name: "force_pending_review_for_oversized"
    when:
      tool_outcome:
        DIAG-LOGIC-01: OVERSIZED
    then:
      status: pending_review
      reason: "Item is oversized — Concord approval required even if LLM said resolved"
```

This guarantees that **no oversized item is ever auto-resolved** without Concord approval — irrespective of the LLM's verdict.

---

## 13. Approval Workflow (Concord)

For risky / high-blast-radius actions, the agent **never** mutates SNOW or sends email directly. Instead, it builds a structured "approval package" and hands off to **Concord** — Walmart's Slack-driven approval system. A human reviews findings, picks which actions to authorize, and Concord calls back the agent.

### 13.1 The End-to-End Loop

```
┌────────────┐           ┌─────────────────┐           ┌──────────┐
│ Diagnostic │  evidence │ approval node   │  package  │ Concord  │
│ + Closure  │──────────▶│ (this agent)    │──────────▶│ (Slack)  │
└────────────┘           └─────────────────┘           └────┬─────┘
       ▲                          ▲                        │
       │                          │ POST                    │
       │                          │ /a2a/approval/complete  │ approve / reject
       │                          │                        │
       │                  ┌───────┴────────┐               │
       │                  │ run_approved_  │◀──────────────┘
       │                  │ actions(...)   │
       │                  └────────────────┘
       │                          │
       │                          ▼
       └────  SNOW updates ◀── ToolExecutor (QRY-SNOW-02, ACT-EMAIL-01)
```

### 13.2 Configuration (`pack.yaml` → `approval_workflow`)

```yaml
approval_workflow:
  enabled: true
  provider: concord
  provider_module: "packs.gif_tote_validation.concord_client"
  provider_display_name: "Concord"

  findings_extractors:                # Pull values out of evidence/SNOW
    - field: gtin
      tool: diag_uberkeys_01
      path: "data[0]"
    - field: dimensions
      tool: diag_api_01
      template: "{height}×{width}×{depth} IN, {weight} LB"
    - field: dim_source
      tool: diag_api_02
      outcome_map:
        GOLD: "Golden (SSOT)"
        NOT_GOLD: "Supplier"
    - field: tote_verdict
      tool: diag_logic_01
      path: "exceeds"
      outcome_map:
        "true": "OVERSIZED"
        "false": "FITS_TOTE"
    - field: merchant_email
      tool: mock_isam_lookup
      path: "merchant_email"

  verdict_field: tote_verdict
  verdict_actions:
    OVERSIZED:
      actions: [send_email, add_work_notes, set_pending]
      previews:
        work_notes: >
          Issue Summary: Item dimensions exceed standard GIF tote limits
          ...
        email_subject: "[Action Required] Item Dimension Review — {incident_number}"
        status: "Pending — Awaiting Merchant Response"
    FITS_TOTE:
      actions: [route_to_gif_picking, add_comment]
      previews:
        ...
```

### 13.3 `findings_extractors` Field Sources

Each extractor pulls one value into the Concord approval card. Supported source forms:

| Source | Example |
|--------|---------|
| `tool` + `path` | `diag_api_02` → `product_name` from the tool's JSON |
| `tool` + `template` | `diag_api_01` → `"{height}×{width}×{depth} IN, {weight} LB"` |
| `tool` + `outcome_map` | `diag_logic_01.outcome=OVERSIZED` → "OVERSIZED" |
| `__snow__` + `path` | `incident_store_number` from SNOW data (no tool) |
| `__snow__` + `template: "parse:Item Number"` | Regex-parses a labeled value out of `incident_details` |

### 13.4 `approved_actions` Catalogue

Each action declares the tool + static params + dynamic fields it needs from closure data:

```yaml
approved_actions:
  - id: send_email
    tool: ACT-EMAIL-01
    enabled: true
    requires_external_id: false
    closure_fields: [gtin, merchant_email, product_name, dimensions]
    slack_success: "📧 Merchant email sent to {merchant_email}"
    slack_failure: "❌ Email failed: {error}"

  - id: add_work_notes
    tool: QRY-SNOW-02
    requires_external_id: true
    params: { field_name: work_notes }
    slack_success: "✅ Work notes added to incident"
    slack_failure: "❌ Work notes failed: {error}"

  - id: set_pending
    tool: QRY-SNOW-02
    requires_external_id: true
    params: { state: "Pending" }
    ...

  - id: route_to_gif_picking
    tool: QRY-SNOW-02
    requires_external_id: true
    params:
      assignment_group: "OPS - eComFulfillment - Picking"
      assigned_to: ""
    ...
```

When Concord posts back `selected_actions: "send_email,add_work_notes,set_pending"`, `run_approved_actions` filters to that list, calls each tool, and posts a Slack update per success/failure.

### 13.5 Verdict → Action Mapping

| Verdict (from `verdict_field`) | Default Actions Recommended |
|-------------------------------|------------------------------|
| `OVERSIZED` | `send_email`, `add_work_notes`, `set_pending` |
| `FITS_TOTE` | `route_to_gif_picking`, `add_comment` |
| `NEEDS_MERCHANT_INPUT` | `send_email`, `add_work_notes`, `set_pending` |
| (no verdict / error) | `escalate`, `add_work_notes` |

The reviewer in Concord can deselect actions before approving — only ticked ones execute.

### 13.6 Failure Handling

* If Concord is unreachable → status remains `pending_review` and a Slack notification surfaces the failure with a `Retry Concord` button.
* If a single action fails inside `run_approved_actions` → other approved actions still run; the failure is logged to `audit_store` and posted to Slack.
* If the approval is **rejected** → `audit_store.log_event("approval_callback", status="rejected")` is recorded; no SNOW writes happen.

---

## 14. Storage & Audit Trail

Four Postgres-backed stores live under `storage/` and share **one connection pool** (created in `app.lifespan`). All four are **optional** — if Postgres is unreachable the agent runs in pure in-memory mode (state is lost between processes).

### 14.1 The Four Stores

| Store | Module | Purpose | Key Methods |
|-------|--------|---------|-------------|
| **state_store** | `storage/state_store.py` | Conversation messages keyed by `session_id` | `insert_message`, `get_messages` |
| **incident_store** | `storage/incident_store.py` | One row per processed incident | `create_incident`, `update_decision`, `update_resolution`, `update_approval`, `mark_skipped`, `mark_failed` |
| **audit_store** | `storage/audit_store.py` | Append-only event log per incident | `log_event`, `get_events_for_incident`, `get_recent_events` |
| **slack_thread_store** | `storage/slack_thread_store.py` | Maps `incident_number` → Slack `thread_ts` so updates land in the right thread | `get_thread`, `set_thread` |

### 14.2 incident_store Lifecycle

```
create_incident      → row inserted, status="processing"
   │
   ▼
update_decision      → matched_rule, runbook, confidence written
   │
   ▼
update_resolution    → final status (resolved/pending_review/escalated/…),
                       closure_text, dimensions, verdict, time_taken
   │
   ▼ (only if pending_review)
update_approval      → approver, approved_at, selected_actions, executed_actions
                       (called from /a2a/approval/complete)
   │
   ─OR─
mark_skipped         → status="skipped", reason ("wrong_group", "no_keyword_match", …)
mark_failed          → status="failed", error_message, exception_class
```

### 14.3 audit_store Event Types

Every important state transition is appended as one row in `audit_events`. Common event types:

| Event | When | Payload Highlights |
|-------|------|-------------------|
| `pipeline_start` | Beginning of `run_incident` | `incident_text_preview`, `pack_id` |
| `pre_triage_skip` | Pre-triage rejected | `reason`, `assignment_group`, `category` |
| `tool_call` | Each LangChain tool invocation | `tool_id`, `args` (truncated) |
| `tool_result` | Each LangChain tool response | `tool_id`, `outcome`, `status`, `result_preview` |
| `decision` | After deterministic decision | `matched_rule`, `runbook`, `observations_used` |
| `closure_rendered` | Jinja2 closure done | `verdict`, `template_id` |
| `safety_net_override` | Override fired | `before_status`, `after_status`, `rule_name` |
| `approval_requested` | Concord package sent | `concord_process_id`, `actions_recommended` |
| `approval_callback` | Concord called back | `approved`, `approver`, `selected_actions` |
| `pipeline_end` | Final response built | `status`, `time_taken`, `tokens_used` |

### 14.4 Token Accounting in Postgres

Migration `003_add_token_columns.sql` adds `prompt_tokens`, `completion_tokens`, `total_tokens` to `incidents`. They are populated from `team_state["_token_usage"]` after every run, so dashboards can graph cost-per-incident by runbook or by day.

### 14.5 Run Number for Reprocessing

Migration `004_add_run_number.sql` adds `run_number` to `incidents`. Re-processing an incident does **not** delete the old row — instead, a new row with `run_number = max(run_number) + 1` is inserted. The dashboard shows the latest run by default but exposes history via `/api/dashboard/incidents/{number}`.

### 14.6 Schema Snapshot

```sql
-- incidents (full lifecycle row)
incidents (
  incident_number    text       NOT NULL,
  run_number         int        NOT NULL DEFAULT 1,
  pack_id            text       NOT NULL,
  status             text       NOT NULL,        -- processing | resolved | pending_review | escalated | skipped | failed
  matched_rule       text,
  runbook            text,                       -- RBK-GIF-01..05
  verdict            text,                       -- FITS_TOTE | OVERSIZED | …
  closure_text       text,
  reason             text,                       -- skip / fail reason
  approver           text,
  approved_at        timestamptz,
  selected_actions   text,                       -- comma-separated
  executed_actions   text,                       -- comma-separated
  prompt_tokens      int,
  completion_tokens  int,
  total_tokens       int,
  time_taken_seconds numeric,
  created_at         timestamptz DEFAULT now(),
  updated_at         timestamptz DEFAULT now(),
  PRIMARY KEY (incident_number, run_number)
);

-- audit_events (append-only)
audit_events (
  id              bigserial    PRIMARY KEY,
  incident_number text         NOT NULL,
  run_number      int          NOT NULL DEFAULT 1,
  event_type      text         NOT NULL,
  payload         jsonb,
  created_at      timestamptz  DEFAULT now()
);

-- slack_threads (incident_number → thread_ts)
slack_threads (
  incident_number text PRIMARY KEY,
  channel_id      text NOT NULL,
  thread_ts       text NOT NULL,
  created_at      timestamptz DEFAULT now()
);

-- chat_messages (state_store)
chat_messages (
  session_id    text NOT NULL,
  message_id    text NOT NULL,
  msg_type      text NOT NULL,            -- user | assistant
  content       text NOT NULL,
  agent_name    text,
  created_at    timestamptz DEFAULT now(),
  PRIMARY KEY (session_id, message_id)
);
```

### 14.7 Optional Mode (No Postgres)

Each store calls `is_available()` before any DB access; if the pool isn't bound, the call is a silent no-op. This is what lets the agent run on a laptop with no Postgres at all — useful for offline demos. **Tradeoff**: dashboards return empty, and re-processing the same incident has no dedup memory.

---

## 15. Configuration Reference

### secrets.toml sections

| Section | Keys | Description |
|---------|------|-------------|
| `[default]` | `AGENT_NAME`, `APP_TITLE`, `APP_DESCRIPTION` | Agent identity |
| `[default.azure_chat]` | `LIGHTRAG_MODEL`, `LIGHTRAG_API_VERSION`, `LIGHTRAG_AZURE_ENDPOINT`, `SANDBOX_GENAIAPI_KEY` | Walmart LLM Gateway config |
| `[default.postgresql]` | `host`, `port`, `database`, `user`, `password` | Conversation state DB (optional) |
| `[default.servicenow_proxy]` | `base_url`, `consumer_id`, `auth_token`, `key_version`, `pem_path`, `ca_cert_path` | SNOW proxy RSA auth |
| `[default.gif_api]` | `GIF_API_URL`, `GIF_CONSUMER_ID`, `GIF_SVC_NAME`, `GIF_SVC_VERSION`, `GIF_SVC_ENV` | GIF API headers |
| `[default.iqs_api]` | `IQS_API_URL`, `IQS_CONSUMER_ID`, `IQS_SVC_NAME`, `IQS_SVC_VERSION`, `IQS_SVC_ENV` | IQS Catalog headers |
| `[default.uber_api]` | `UBER_API_URL`, `UBER_CONSUMER_ID`, `UBER_SVC_NAME`, `UBER_SVC_VERSION`, `UBER_SVC_ENV` | Uber API headers |
| `[default.smtp]` | `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM_ADDRESS` | Anonymous SMTP (`smtp-gw1.wal-mart.com:25`) |
| `[default.slack]` | `SLACK_BOT_TOKEN`, `SSOT_CHANNEL_ID` | Slack #ssot-gif channel |
| `[default.cron_poller]` | `AGENT_BASE_URL`, `POLL_INTERVAL_SECONDS`, `MAX_INCIDENTS_PER_POLL` | Cron config |

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DEFAULT_PACK_ID` | `gif_tote_validation` | Pack to load on startup |
| `ENV_FOR_DYNACONF` | `development` | Dynaconf environment |
| `DYNACONF_AGENT_NAME` | `gif_tote_validation_agent` | Agent name override |

### LLM Auth Modes

| Mode | Trigger | How it works |
|------|---------|-------------|
| **Sandbox** | `SANDBOX_GENAIAPI_KEY` is set | JWT token sent as `api-key` header |
| **Production** | `LIGHTRAG_CONSUMER_ID` + `LIGHTRAG_LLM_PRIVATE_KEY` are set | RSA-SHA256 signed Service Registry headers |

The mode is auto-detected at startup. Sandbox is used for stage/demo; production for deployed environments.

---

## 16. API Endpoints

### A2A & Agent Discovery

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/a2a/invoke` | Synchronous chat (retrieval pipeline) |
| `POST` | `/a2a/invoke-stream` | Streaming chat (SSE) |
| `POST` | `/a2a/work-item/process` | Full incident pipeline by `incident_number` (used by cron + Concord) |
| `POST` | `/a2a/approval/complete` | Approval callback from Concord — runs approved actions |
| `GET` | `/.well-known/agents.json` | A2A agent discovery card |

### Webhooks

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/webhooks/slack/events` | Slack Events API webhook (URL verification + threads) |

### Health & Pack Introspection

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/healthz` | Liveness probe |
| `GET` | `/readyz` | Readiness probe |
| `GET` | `/api/factory/health` | Pack health & tool binding stats |
| `GET` | `/api/factory/tools` | Tool availability report (per-tool resolution status) |
| `GET` | `/api/pack/info` | Pack metadata (id, name, version, owner_team, runbook count) |

### Dashboard API (Postgres-backed)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/dashboard/stats` | Aggregate KPIs over last N days (success rate, avg time, totals) |
| `GET` | `/api/dashboard/incidents` | Paginated incident list w/ filtering (status, runbook, date range) |
| `GET` | `/api/dashboard/incidents/{number}` | Single incident detail + audit timeline |
| `GET` | `/api/dashboard/audit` | Recent audit events (cross-incident) |
| `GET` | `/api/dashboard/trends` | Daily counts for charts (incidents/day, status breakdown) |
| `GET` | `/api/dashboard/performance` | Performance metrics (p50, p95, p99 latency) |

### Request format (`/a2a/work-item/process`)

```json
{
  "incident_number": "INC52148837",
  "session_id": "optional-session-uuid"
}
```

Optional headers:
- `X-User-ID`: traceable identity for the caller (defaults to `unknown`).
- `X-Session-ID`: stable session for grouping messages (auto-generated if omitted; body `session_id` takes precedence).
- `X-Calling-Agent`: source-channel tag, used when one agent delegates to another.

### Request format (`/a2a/invoke`)

```json
{
  "query": "Show me the last 5 GIF tote incidents",
  "agent_name": "gif_tote_validation_agent"
}
```

### Response format (incident pipeline)

HTTP `200` on success/skip, HTTP `503` on retryable error (e.g. LLM gateway timeout).

```json
{
  "incident_number": "INC52148837",
  "status": "processed",
  "skip_reason": null,
  "error": null,
  "retryable": null,
  "response": "Incident INC52148837 resolved. Item fits the standard GIF tote — routed to GIF Picking Team.",
  "session_id": "demo-001",
  "agent_name": "gif_tote_validation_agent",
  "time_taken": 12.34
}
```

Top-level `status` values returned by the API:
- `processed` — pipeline ran to completion. Inspect the `response` text (and `team_state._evidence` on the dashboard) for the business verdict (resolved / pending_review / escalated).
- `skipped` — pre-triage gate rejected the incident. `skip_reason` carries the cause (`wrong_group`, `no_keyword_match`, `wrong_category`, or a `routed_groups` reason like `"GIF Picking Team"`).
- `pending_approval` — LangGraph paused at the HITL gate. `approval_work_item_id` is set; callers must NOT retry — Concord owns the next move.
- `error` — retryable failure (HTTP 503). `error` carries the cause (e.g. `llm_timeout`), `retryable=true`.

### Response format (approval callback)

```json
{
  "incident_number": "INC52148837",
  "status": "executed",
  "actions_executed": ["Send Email", "Add Work Notes", "Set Pending"],
  "response": "All 3 approved actions completed successfully."
}
```

`status` values: `executed` (200), `rejected` (200), `error` (500).

---

## 17. Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Pack 'gif_tote_validation' not found` | `DEFAULT_PACK_ID` not set | Run `export DEFAULT_PACK_ID=gif_tote_validation` or use `./run_dev.sh` |
| `ModuleNotFoundError: llm.azure_handler` | Missing `llm/` directory | Verify `llm/__init__.py` and `llm/azure_handler.py` exist |
| `401 Signature expired` on LLM calls | Stale SOA headers | `build_model_client()` regenerates per-request; check if client is cached |
| `SANDBOX_GENAIAPI_KEY` expired | JWT token expired | Get a new sandbox JWT from Walmart LLM Gateway portal |
| SNOW proxy connection refused | Missing PEM file | Set `pem_path` in `[default.servicenow_proxy]` to your `.pem` file |
| SNOW proxy SSL error | Missing CA bundle | Set `ca_cert_path` to your `ca-bundle.crt` |
| Cron: "ServiceNow proxy not configured" | Missing secrets | Fill `[default.servicenow_proxy]` in `secrets.toml` |
| Cron: incidents not dispatching | Agent not running | Start agent first: `./run_dev.sh`, then run cron |
| Cron: re-processing old incidents | Ledger cleared | Normal — the ledger is in `cron/processed_incidents.json` |
| `body_template` validation error | YAML string instead of dict | Use YAML dict syntax, not `\|` block string |
| `Tool 'ACT-SNOW-' not found` warning | Stale sop-ir.json | Run pack validation — all tool_ids should map to `tools.yaml` |
| PostgreSQL connection refused | DB not available | Optional — agent works without it (state won't persist) |

### Validate the pack

```bash
python3 -c "
import sys; sys.path.insert(0, '.')
from agent_factory.pack_loader import load_pack
pack = load_pack('gif_tote_validation', packs_root='packs')
print(f'Valid: {pack.validation.valid} | Warnings: {len(pack.validation.warnings)} | Errors: {len(pack.validation.errors)}')
for w in pack.validation.warnings: print(f'  WARN: {w}')
for e in pack.validation.errors: print(f'  ERR: {e}')
"
```

### Test the tote fit engine

```bash
python3 -c "
from packs.gif_tote_validation.tote_fit_engine import check_oversized
print('Fits:', check_oversized(5, 8, 12, 10))
print('Oversized:', check_oversized(15, 20, 25, 40))
"
```

### Test the decision rules

```bash
python3 -c "
import json
from packs.gif_tote_validation.decision_rules import apply_decision_matrix
print(apply_decision_matrix(json.dumps({'DIAG-LOGIC-01': 'FITS_TOTE'})))
print(apply_decision_matrix(json.dumps({'DIAG-LOGIC-01': 'OVERSIZED', 'merchant_response': 'DIMENSIONS_NEED_UPDATE', 'DIAG-API-02': 'GOLD'})))
"
```

---

## 18. Incident Detection & Trigger Patterns

### EMS Template Patterns

The cron poller identifies GIF tote incidents by matching against these EMS form template values in the **original short description** (before team modification):

| Original Short Description (EMS Template) | Issue Type | Frequency |
|---|---|---|
| `EMS GIF 2.0 Picking Tote Size Issues` | Tote size / oversized item | ~60% |
| `EMS GIF 2.0 Picking Item Details Issue` | Item details / dimension | ~15% |
| `EMS GIF 2.0 Items dropping into incorrect commodity` | Commodity routing / dimensions | ~20% |
| `EMS GIF 2.0 Picking Issues Scanning Items` | Scanning / UPC issue | ~5% |

### Post-Pickup Short Description Format

> **Critical Behavior:** The MerchOps team modifies the incident short description after pickup to a pipe-delimited tracking format. The cron poller matches against **both** the original EMS template **and** the modified format containing `incorrect dimensions`.

**Modified format:** `GIF | <Team> | <issue_classification> | <validity_status> | <region>-WCNP | <original_EMS_template>`

**Real examples:**
- `GIF|Merchantops|incorrect dimensions|Valid | R7-WCNP | EMS GIF 2.0 Picking Item Details Issue`
- `GIF|Merchantops|Incorrect dimensions|Valid | R5-WCNP | EMS GIF 2.0 Picking Tote Size Issues`
- `GIF|merchant_ops|Incorrect Dimensions|Needs Attention | R8-WCNP | EMS GIF 2.0 Items dropping into incorrect commodity`

### Incident Body Structure (`===FORM===` / `===USER===`)

```
===FORM===
CATEGORY --- GIF
ISSUE --- GIF Picking Tote Size Issue
PROBLEM --- GIF Picking
UPC Number --- 681131029735
Item Number --- 123456789
STORE NUMBER --- 5260
WHAT IS THE ISSUE --- The item dimensions are wrong causing tote fit issues
===USER===
Site: 5260
Name: John Smith
```

---

## 19. Error Handling & Edge Cases

| Scenario | Automated Handling | Fallback |
|----------|-------------------|----------|
| GIF API returns 404 | Set observation `NOT_FOUND` | → RBK-GIF-05 (escalate to manual) |
| GIF API returns 500/503 | Retry 3x with exponential backoff | → RBK-GIF-05 on exhaust |
| IQS API auth error (401/403) | Set observation `AUTH_ERROR` | → RBK-GIF-05 |
| Missing UPC/GTIN in incident | TriageAgent flags as incomplete | → RBK-GIF-05 |
| Tote fit engine receives non-numeric dims | Type conversion with fallback | → RBK-GIF-05 |
| Merchant does not respond | Ticket remains in Pending state | Auto-close by SNOW after 7 days |
| SSOT Slack post fails | Log error in work notes | → Manual SSOT request |
| iSAM API unavailable | Feature-flagged off (`enable_isam_direct_update: false`) | Manual iSAM update |
| Duplicate incident detected | Dedup ledger prevents re-processing | Skip silently |
| Decision rules: no match | RAG fallback attempted | → RBK-GIF-05 if RAG also fails |

---

## 20. Repository Map

```
matbot-multi-agents/                    # monorepo root
├── app.py                              # FastAPI entry point — all A2A endpoints + webhooks
├── run_dev.sh                          # Local dev startup (sets DEFAULT_PACK_ID)
├── requirements.txt                    # Python dependencies
├── Dockerfile                          # Container build (python:3.12-slim)
├── .gitignore                          # Secrets, pycache, IDE files excluded
│
├── agent_factory/                      # Pack-agnostic substrate
│   ├── runtime/                        # Canonical LangChain runtime namespace
│   │   ├── builder.py                  # → langchain_builder (forward shim)
│   │   ├── chat.py                     # → langchain_chat (forward shim)
│   │   └── model_client.py             # build_langchain_model_client() — AzureChatOpenAI w/ SOA auth
│   ├── pack/                           # Canonical SOP-Pack namespace (forward shims)
│   │   ├── loader.py                   # → pack_loader
│   │   ├── models.py                   # → pack_models
│   │   ├── registry.py                 # → registry
│   │   └── prompts.py                  # → prompts
│   ├── pack_models/                    # Pydantic schemas split by YAML file
│   │   ├── pack.py                     # pack.yaml schema (PackConfig, Pipelines, …)
│   │   ├── tools.py                    # tools.yaml schema (ToolSpec, ToolsManifest, …)
│   │   └── policy.py                   # policy.yaml schema (ApprovalPolicy, BlastRadius, …)
│   ├── langchain_builder.py            # LangChainAgentBuilder — AgentExecutor factory
│   ├── langchain_chat.py               # run_chat() / run_chat_stream() — chat surface
│   ├── registry.py                     # Pack registry singleton
│   ├── pack_loader.py                  # Loads & validates packs from disk
│   ├── prompts.py                      # Jinja2 prompt resolution
│   ├── evidence_extractor.py           # Duck-typed evidence extractor (shared)
│   ├── ir/                             # SOP-IR Pydantic models (shared w/ sop-normalizer)
│   ├── graph/
│   │   ├── factory.py                  # build_graph() — generic LangGraph factory
│   │   ├── builder.py                  # GraphBuilder — thin wrapper around StateGraph
│   │   ├── checkpointer.py             # Postgres checkpointer (langgraph-checkpoint-postgres)
│   │   ├── hitl.py                     # GraphInterrupt helpers
│   │   ├── event_recorder.py           # Per-super-step event emission
│   │   ├── runtime_holder.py           # Lazy-init holder for the compiled LangGraph
│   │   └── state.py                    # IncidentState TypedDict
│   ├── nodes/                          # Reusable LangGraph nodes (pack-agnostic)
│   │   ├── pre_triage.py
│   │   ├── triage.py
│   │   ├── evidence.py                 # AgentExecutor wrapper + safety nets
│   │   ├── decision.py
│   │   ├── approval_gate.py
│   │   ├── action.py
│   │   └── closure.py
│   ├── tools/
│   │   ├── executor.py                 # ToolExecutor — runs all declarative tool types
│   │   ├── rag_fallback.py             # RAG-based decision fallback
│   │   ├── response_processors.py      # Field-presence / json-path / regex / …
│   │   ├── param_enrichment.py
│   │   ├── wrapper_factory.py
│   │   ├── db_dialects.py
│   │   ├── redis_commands.py
│   │   └── handlers/                   # Per-tool-type handler modules
│   ├── integrations/                   # External system clients (flat modules)
│   │   ├── concord.py                  # Walmart Concord approval workflow
│   │   ├── email.py                    # Email via MatBot Common Services
│   │   ├── isam.py
│   │   ├── matbot_services.py          # REST client for /email/* and /slack/*
│   │   └── slack_notifier.py           # Slack incident notifier via MatBot Common Services
│   ├── decision/                       # Decision matrix + rules engine
│   ├── api/                            # FastAPI route groups
│   ├── core/                           # Back-compat shims (model client)
│   ├── infrastructure/
│   │   ├── settings.py                 # Dynaconf config loader
│   │   └── secrets.toml                # Credentials (GITIGNORED — never committed)
│   └── common/
│       ├── logging.py                  # Structured logging with context vars
│       ├── tracing.py                  # OpenTelemetry distributed tracing
│       ├── errors.py                   # Shared exception types
│       ├── access_control.py
│       └── agent_comm.py
│
├── llm/
│   ├── __init__.py
│   └── azure_handler.py                # Walmart LLM Gateway auth handler
│
├── packs/
│   └── gif_tote_validation/            # SOP Pack — declarative config + minimal Python
│       ├── pack.yaml                   # Pipeline & agent definitions
│       ├── tools.yaml                  # Declarative tool definitions
│       ├── sop-ir.json                 # Diagnostics, decision rules, runbooks
│       ├── policy.yaml                 # Approval gates, feature flags
│       ├── eval_cases.json             # Regression test cases
│       ├── prompts/                    # Per-agent Jinja2 system prompts
│       │   ├── triage.j2
│       │   ├── diagnostic.j2
│       │   ├── decision.j2
│       │   ├── action.j2
│       │   ├── closure.j2
│       │   └── retrieval.j2
│       ├── templates/                  # Closure / email Jinja2 templates
│       ├── state.py                    # IncidentState factory + schema
│       ├── email_sender.py             # Pack-specific email helper
│       └── isam_mock.py                # Mock iSAM merchant lookup
│
├── cron/
│   ├── snow_poller.py                  # Standalone SNOW poller (single or continuous)
│   └── processed_incidents.json        # Dedup ledger (GITIGNORED)
│
├── storage/                            # PostgreSQL-backed stores (shared pool)
│   ├── incident_store.py
│   ├── audit_store.py
│   ├── slack_thread_store.py
│   ├── state_store.py                  # Conversation state (chat path)
│   ├── session_store.py
│   ├── work_item_store.py
│   ├── event_store.py
│   ├── agent_registry_store.py
│   ├── analytics.py
│   └── migrations/                     # SQL migration files
│
├── .well-known/
│   └── agents.json                     # A2A agent discovery card
│
└── tests/                              # pytest suite — 931 passing (unit, integration, e2e)
```

---

## 21. Glossary

| Term | Definition |
|------|-----------|
| **GIF** | Global Integrated Fulfilment — Walmart's fulfillment system |
| **Tote** | Standard container used in fulfillment centers (10.5x13x20.5 IN, 34.55 LB max) |
| **GTIN** | Global Trade Item Number — 14-digit item identifier (UPC left-padded with zeros) |
| **UPC** | Universal Product Code — 12-digit barcode number |
| **WIN** | Walmart Item Number — internal item identifier |
| **Gold Status** | Item whose dimensions are managed by the SSOT (Single Source of Truth) team |
| **Supplier Status** | Item whose dimensions come from the supplier via Uber API |
| **SSOT** | Single Source of Truth — the team that manages authoritative item data |
| **iSAM** | Item Setup and Maintenance — Walmart's internal item management UI |
| **IQS** | Item Query Service — API for querying item catalog data |
| **EMS** | Enterprise Management System — self-service form system for store associates |
| **SOP Pack** | Directory of YAML/JSON/Jinja2 files that defines an agent's behavior |
| **SOPIR** | SOP Intermediate Representation — structured JSON of diagnostics, rules, runbooks |
| **Observation Code** | Short uppercase token emitted by a diagnostic tool (e.g., `FITS_TOTE`, `OVERSIZED`) |
| **Runbook Card** | Numbered card (RBK-GIF-01 through RBK-GIF-05) mapping to remediation actions |
| **A2A** | Agent-to-Agent — HTTP protocol for agents calling each other |
| **SoP Normalizer** | Companion service that converts raw SOP documents into Factory Packs |
| **Walmart LLM Gateway** | Internal Azure OpenAI-compatible endpoint for LLM inference |
| **Service Registry** | Walmart's RSA-SHA256 auth system for internal API calls |
