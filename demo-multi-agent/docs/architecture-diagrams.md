# GIF Tote Validation Agent — Architecture Diagrams (ASCII)

Text-based diagrams for all key flows. These render in any Markdown viewer, terminal, or PR diff.

---

## 1. High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         INGRESS CHANNELS                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │  ServiceNow   │  │  Slack Bot   │  │  REST API    │  │ SNOW Cron  │  │
│  │  Webhook      │  │  (Events)    │  │  (A2A)       │  │ Poller     │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └─────┬──────┘  │
└─────────┼──────────────────┼──────────────────┼────────────────┼─────────┘
          ▼                  ▼                  ▼                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                    CHANNEL GATEWAY LAYER (FastAPI)                        │
│                                                                          │
│  POST /webhooks/     POST /webhooks/    POST /a2a/         POST /a2a/   │
│  servicenow          slack/events       incident/process    invoke       │
│  (background task)   (background task)  (sync response)    (chat sync)  │
└──────────┬──────────────────┬──────────────────┬──────────────┬─────────┘
           │                  │                  │              │
           │                  │                  │              │
           ▼                  │                  ▼              ▼
    ┌──────────────┐          │          ┌──────────────┐ ┌────────────┐
    │ LangGraph    │          │          │ LangGraph    │ │ LangChain  │
    │ topology     │          │          │ topology     │ │ run_chat   │
    │ .run_incident│          │          │ .run_incident│ │            │
    └──────┬───────┘          │          └──────┬───────┘ └──────┬─────┘
           │                  │                 │                │
           ▼                  │                 ▼                ▼
    ┌──────────────┐          │          ┌──────────────┐ ┌────────────┐
    │  PRE-TRIAGE  │          │          │  PRE-TRIAGE  │ │  Retrieval │
    │  node        │          │          │  node        │ │  Executor  │
    └──┬───────┬───┘          │          └──┬───────┬───┘ │ (LangChain)│
    pass│    skip│             │          pass│    skip│    └────────────┘
       ▼       ▼              │             ▼       ▼
  ┌────────┐ ┌─────┐         │        ┌────────┐ ┌─────┐
  │Pipeline│ │ Log │         │        │Pipeline│ │ Log │
  │  Run   │ │Skip │         │        │  Run   │ │Skip │
  └────────┘ └─────┘         │        └────────┘ └─────┘
       │                     │             │
       ▼                     ▼             ▼
┌──────────────────────────────────────────────────────────────────────────┐
│           5-STAGE INCIDENT TOPOLOGY (LangGraph StateGraph)               │
│                                                                          │
│  ┌─────────┐ ┌────────────┐ ┌──────────┐ ┌────────┐ ┌─────────┐       │
│  │ Triage  │→│ Evidence   │→│ Decision │→│ Action │→│ Closure │       │
│  │ node    │ │ node (LLM) │ │ node     │ │ node   │ │ node    │       │
│  │(rules) │ │(6 tools)   │ │(rules)   │ │(7 tools)│ │(template)│      │
│  └─────────┘ └────────────┘ └──────────┘ └────────┘ └─────────┘       │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                       TOOL LAYER (ToolExecutor)                           │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ Diagnostic: SNOW │ UberKeys │ GIF API │ IQS │ Uber │ ToteFit   │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ Action: SNOW Update │ iSAM │ Email │ DecisionMatrix │ RAG       │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                       PERSISTENCE (PostgreSQL)                            │
│                                                                          │
│  ┌──────────────┐  ┌────────────┐  ┌──────────────┐  ┌───────────┐    │
│  │ incident_log │  │audit_trail │  │ conv_state   │  │ sessions  │    │
│  │ (1 row/inc)  │  │ (events)   │  │ (messages)   │  │           │    │
│  └──────────────┘  └────────────┘  └──────────────┘  └───────────┘    │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Pre-Triage Gate Flow

```
             Incident Number (INC52148837)
                        │
                        ▼
            ┌───────────────────────┐
            │  Resolve DIAG-SNOW-01 │
            │  tool via ToolExecutor │
            └───────────┬───────────┘
                        │
                  ┌─────▼──────┐
                  │ Tool found? │
                  └──┬──────┬──┘
                  NO │    YES│
                     ▼      ▼
              ┌─────────┐ ┌─────────────────┐
              │ SKIP    │ │ Call tool_fn(    │
              │(fail-   │ │  incident_number)│
              │ closed) │ └────────┬────────┘
              └─────────┘          │
                             ┌─────▼──────┐
                             │ Parse JSON │
                             │ response   │
                             └─────┬──────┘
                                   │
                        ┌──────────▼──────────┐
                        │ Unwrap nested data:  │
                        │ raw = result.get(    │
                        │   "data") or         │
                        │   result.get("raw")  │
                        │   or result          │
                        └──────────┬──────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │ _get(field) helper:          │
                    │   try incident_<field>       │
                    │   try <field>                │
                    │   try <field>_name           │
                    │   → lowercase string         │
                    └──────────────┬──────────────┘
                                   │
              ┌────────────────────▼────────────────────┐
              │  CHECK 1: assignment_group               │
              │  _get("assignment_group") in             │
              │  [allowed groups] (case-insensitive)     │
              └─────┬──────────────────────────┬────────┘
                 PASS│                       FAIL│
                    │                            ▼
                    │                    ┌──────────────┐
                    │                    │ SKIP         │
                    │                    │ "SNOW value: │
                    │                    │  '...'.      │
                    │                    │  Accepted:   │
                    │                    │  [...]"      │
                    │                    └──────────────┘
                    ▼
              ┌─────────────────────────────────────────┐
              │  CHECK 2: keywords in short_description  │
              │  any(kw in short_desc for kw in keywords)│
              └─────┬──────────────────────────┬────────┘
                 PASS│                       FAIL│→ SKIP
                    ▼
              ┌─────────────────────────────────────────┐
              │  CHECK 3: category                       │
              │  _get("category") in [allowed cats]      │
              └─────┬──────────────────────────┬────────┘
                 PASS│                       FAIL│→ SKIP
                    ▼
              ┌─────────────┐
              │ PASS →      │
              │ Run pipeline│
              └─────────────┘
```

---

## 3. Diagnostic Dependency Chain

```
┌──────────────────────────────────────────────────────┐
│  DIAG-SNOW-01: Fetch Incident from ServiceNow        │
│  Tool: servicenow / get_by_number                     │
│  Depends on: Nothing (always runs first)              │
│  Outcomes: INCIDENT_MATCHED | INCIDENT_NOT_MATCHED    │
└───────────────────────┬──────────────────────────────┘
                        │
              ┌─────────▼─────────┐
              │ UPC or WIN found? │
              └──┬────────────┬───┘
              NO │         YES│
                 ▼            ▼
          ┌──────────┐  ┌──────────────────────────────────────────┐
          │ STOP     │  │  DIAG-UBERKEYS-01: Resolve GTIN          │
          │ Report   │  │  Strategy: SI_TO_GTIN first (WIN)         │
          │ missing  │  │           WUPC_TO_GTIN fallback (UPC)     │
          │ IDs      │  │  Outcomes: GTIN_FOUND | GTIN_NOT_FOUND    │
          └──────────┘  └───────────────────┬──────────────────────┘
                                            │
                              ┌──────────────▼──────────────┐
                              │ GTIN resolved?               │
                              └──┬───────────────────────┬──┘
                              NO │                    YES│
                                 ▼                      ▼
                          ┌──────────┐      ┌──────────────────────┐
                          │ SKIP ALL │      │  Run API tools with   │
                          │ API steps│      │  resolved GTIN        │
                          │ → handoff│      └──────────┬───────────┘
                          └──────────┘                 │
                                         ┌─────────────┐
                                         ▼             ▼
                                  ┌────────────┐ ┌────────────┐
                                  │DIAG-API-01 │ │DIAG-API-02 │
                                  │GIF API     │ │IQS API     │
                                  │(dimensions)│ │(Gold check)│
                                  │DATA_FOUND  │ │GOLD        │
                                  │DATA_NOT_   │ │NOT_GOLD    │
                                  │FOUND       │ │AUTH_ERROR  │
                                  └──────┬─────┘ └──────┬─────┘
                                         │              │
                                         │    ┌─────────▼─────────┐
                                         │    │ Gold status?       │
                                         │    └──┬─────────────┬──┘
                                         │   GOLD│         NOT_GOLD│
                                         │      ▼               ▼
                                         │ ┌──────────┐  ┌────────────┐
                                         │ │ SKIP     │  │DIAG-API-03 │
                                         │ │ API-03   │  │Uber API    │
                                         │ │ (Gold =  │  │(supplier   │
                                         │ │  SSOT)   │  │ dimensions)│
                                         │ └──────────┘  │DATA_FOUND  │
                                         │               │DATA_NOT_   │
                                         │               │FOUND       │
                                         │               └──────┬─────┘
                                         │                      │
                              ┌──────────▼──────────────────────▼────────┐
                              │ Dimensions available (from API-01 or API-03)?│
                              └──┬────────────────────────────────────────┬──┘
                              NO │                                     YES│
                                 ▼                                       ▼
                          ┌──────────┐                           ┌────────────┐
                          │ SKIP     │                           │DIAG-LOGIC-01│
                          │ LOGIC-01 │                           │Tote Fit    │
                          └──────────┘                           │Check       │
                                                                 │            │
                                                                 │FITS_TOTE   │
                                                                 │OVERSIZED   │
                                                                 └────────────┘
                                                                       │
                                                                       ▼
                                                            ┌──────────────────┐
                                                            │ OBSERVATION      │
                                                            │ REPORT           │
                                                            │ → DecisionAgent  │
                                                            └──────────────────┘
```

---

## 4. Decision Matrix Flow

```
                 Diagnostic Observations
                          │
                          ▼
                ┌─────────────────────┐
                │  Critical errors?    │
                │  (API_ERROR,         │
                │   PARSE_FAILURE,     │
                │   SNOW_ERROR,        │
                │   INCIDENT_NOT_FOUND)│
                └──────┬──────────┬───┘
                    YES│       NO │
                       ▼          ▼
              ┌──────────────┐  ┌─────────────────┐
              │ RBK-GIF-05   │  │ DIAG-LOGIC-01   │
              │ Escalate     │  │ result?          │
              │ (high conf.) │  └──┬───────────┬───┘
              └──────────────┘  FIT│       OVER│
                                   ▼           ▼
                          ┌────────────┐ ┌──────────────────┐
                          │RBK-GIF-01  │ │ merchant_response │
                          │Auto-Route  │ │ present?          │
                          │to Picking  │ └──┬────────────┬──┘
                          └────────────┘  NO│        YES│
                                            ▼           ▼
                               ┌────────────────┐ ┌──────────────────┐
                               │MERCHANT_       │ │ Merchant         │
                               │OUTREACH        │ │ Response?        │
                               │Email merchant, │ └──┬────────────┬──┘
                               │set Pending     │ CORRECT│   UPDATE│
                               └────────────────┘       ▼         ▼
                                              ┌────────────┐ ┌──────────────┐
                                              │RBK-GIF-02  │ │ DIAG-API-02  │
                                              │Route to    │ │ Gold status? │
                                              │GIF Picking │ └──┬────────┬──┘
                                              └────────────┘ GOLD│  NOT_ │
                                                                 │  GOLD │
                                                                 ▼       ▼
                                                        ┌──────────┐ ┌──────────┐
                                                        │RBK-GIF-03│ │RBK-GIF-04│
                                                        │SSOT Post │ │iSAM      │
                                                        │(#ssot-   │ │Update    │
                                                        │gif Slack)│ │(approval │
                                                        └──────────┘ │required) │
                                                                     └──────────┘

                     No rule matched?
                          │
                          ▼
                 ┌──────────────┐
                 │ RBK-GIF-05   │
                 │ Escalate     │
                 │ (medium conf)│
                 └──────────────┘

Rule Evaluation Order (first match wins):
  RULE-1: FITS_TOTE                              → RBK-GIF-01
  RULE-2: OVERSIZED + no merchant_response       → MERCHANT_OUTREACH
  RULE-3: OVERSIZED + DIMS_CORRECT               → RBK-GIF-02
  RULE-4: OVERSIZED + DIMS_NEED_UPDATE + GOLD    → RBK-GIF-03
  RULE-5: OVERSIZED + DIMS_NEED_UPDATE + NOT_GOLD→ RBK-GIF-04
  FALLBACK:                                       → RBK-GIF-05

Note: "data_not_found" (e.g., DIAG-API-03) is NOT an error —
it is an expected condition for optional data sources.
```

---

## 5. Evidence & Audit Trail Flow

```
     TaskResult-shape input
     (shim adapters from chat path or
      LangGraph evidence node)
                │
                ▼
  ┌──────────────────────────────┐
  │  PASS 1: Build call_id map   │
  │                               │
  │  For each msg with            │
  │  FunctionCall content:        │
  │    call_id_to_tool[item.id]   │
  │      = item.name              │
  └──────────────┬───────────────┘
                 │
                 ▼
  ┌──────────────────────────────┐
  │  PASS 2: Classify messages    │
  │                               │
  │  String content:              │
  │    → "agent_message"          │
  │    → "decision" (if contains  │
  │       runbook_card JSON)      │
  │                               │
  │  List[FunctionCall]:          │
  │    → "tool_call" per item     │
  │      {tool, args, call_id}    │
  │                               │
  │  List[FunctionExecResult]:    │
  │    → "tool_result" per item   │
  │      {tool, result_preview,   │
  │       status, outcome}        │
  └──────────────┬───────────────┘
                 │
                 ▼
  ┌──────────────────────────────┐
  │  _derive_tool_status()       │
  │                               │
  │  Parse result JSON:           │
  │  • outcome in ERROR_OUTCOMES  │
  │    → status="error"           │
  │  • HTTP code in error field   │
  │    → status="error"           │
  │  • Otherwise                  │
  │    → status="success"         │
  └──────────────┬───────────────┘
                 │
                 ▼
  ┌──────────────────────────────┐
  │  summarise_pipeline_health() │
  │                               │
  │  Count: tool_calls,           │
  │         tool_successes,       │
  │         tool_failures         │
  │                               │
  │  → "success" | "partial"     │
  │    | "failed" | "no_tools"   │
  └──────────────┬───────────────┘
                 │
                 ▼
  ┌──────────────────────────────┐
  │  Store to PostgreSQL          │
  │                               │
  │  incident_log:                │
  │    status, mep_results,       │
  │    runbook_card, tokens        │
  │                               │
  │  audit_trail:                  │
  │    One event per evidence     │
  │    entry (tool_call,          │
  │    tool_result, decision...)  │
  └──────────────────────────────┘
```

---

## 6. Data Model (Entity Relationships)

```
┌──────────────────────────────────────┐
│          incident_log                 │
│  (one row per incident)              │
├──────────────────────────────────────┤
│ PK incident_number  TEXT             │
│    sys_id            TEXT             │
│    session_id        TEXT             │
│    store_number      INT              │
│    department        INT              │
│    category          INT              │
│    short_description TEXT             │
│    symptom           TEXT             │
│    source_channel    VARCHAR          │
│    status            VARCHAR          │──── processing → decided
│    mep_results       JSONB            │     → resolved / escalated
│    runbook_card      TEXT             │     / skipped / failed
│    card_name         TEXT             │
│    decision_confidence TEXT           │
│    requires_approval BOOL             │
│    approval_status   VARCHAR          │
│    approved_by       TEXT             │
│    approved_at       TIMESTAMPTZ      │
│    actions_taken     JSONB            │
│    issue_tag         TEXT             │
│    fix_tag           TEXT             │
│    closure_notes     TEXT             │
│    error_data        JSONB            │
│    processing_time_ms INT             │
│    prompt_tokens     INT              │
│    completion_tokens INT              │
│    total_tokens      INT              │
│    run_number        INT              │
│    created_at        TIMESTAMPTZ      │
│    updated_at        TIMESTAMPTZ      │
│    resolved_at       TIMESTAMPTZ      │
└──────────────┬───────────────────────┘
               │ 1:N
               ▼
┌──────────────────────────────────────┐
│          audit_trail                  │
│  (multiple events per incident)      │
├──────────────────────────────────────┤
│ PK event_id          TEXT            │
│    incident_number   TEXT  FK        │
│    session_id        TEXT            │
│    event_type        TEXT            │──── pipeline_start,
│    status            TEXT            │     pre_triage_skip,
│    agent             TEXT            │     tool_call, tool_result,
│    tool              TEXT            │     decision, action,
│    detail            JSONB           │     pipeline_end
│    duration_ms       INT             │
│    created_at        TIMESTAMPTZ     │
└──────────────────────────────────────┘

┌──────────────────────────────────────┐
│          sessions                     │
│  (chat/retrieval sessions)           │
├──────────────────────────────────────┤
│ PK session_id    TEXT                │
│    user_id       TEXT                │
│    pack_id       TEXT                │
│    last_outcome  TEXT                │
│    turn_count    INT                 │
│    created_at    TIMESTAMPTZ         │
│    updated_at    TIMESTAMPTZ         │
└──────────────┬───────────────────────┘
               │ 1:N
               ▼
┌──────────────────────────────────────┐
│          messages                     │
│  (conversation history)              │
├──────────────────────────────────────┤
│ PK message_id    TEXT                │
│    session_id    TEXT  FK            │
│    role          TEXT                │
│    content       TEXT                │
│    token_count   INT                 │
│    created_at    TIMESTAMPTZ         │
└──────────────────────────────────────┘
```

---

## 7. API Endpoint Map

```
FastAPI Application (app.py)
│
├── A2A Endpoints (Retrieval / Chat)
│   ├── POST /a2a/invoke              → Sync chat response
│   └── POST /a2a/invoke-stream       → SSE streaming chat
│
├── A2A Endpoints (Incident Pipeline)
│   └── POST /a2a/work-item/process    → Pre-triage + full pipeline
│
├── Webhook Endpoints
│   └── POST /webhooks/slack/events   → Slack Events API → background task
│
├── Discovery
│   └── GET  /.well-known/agents.json → A2A agent card
│
├── Factory Management
│   ├── GET  /api/factory/health      → Pack health status
│   └── GET  /api/factory/tools       → Tool availability report
│
├── Dashboard API
│   ├── GET  /api/dashboard/stats     → Summary statistics (N days)
│   ├── GET  /api/dashboard/incidents → List incidents (filterable)
│   ├── GET  /api/dashboard/incidents/{id} → Detail + audit + runs
│   └── GET  /api/dashboard/audit     → Query audit events
│
├── Health Checks (Kubernetes)
│   ├── GET  /healthz                 → Liveness probe
│   └── GET  /readyz                  → Readiness probe
│
└── Static UI (optional, dev only)
    └── GET  /ui/*                    → Dashboard HTML/JS/CSS
```

---

## 8. Tote Fit Engine Logic

```
   Input: height, width, depth, weight, dim_uom, weight_uom
                     │
                     ▼
          ┌────────────────────┐
          │ Convert UOM        │
          │ CM → IN (÷ 2.54)  │
          │ MM → IN (÷ 25.4)  │
          │ KG → LB (× 2.205) │
          │ G  → LB (÷ 453.6) │
          │ OZ → LB (÷ 16)    │
          └─────────┬──────────┘
                    │
                    ▼
          ┌────────────────────┐
          │ Sort item dims     │
          │ [small, med, large]│
          │                    │
          │ e.g., [5.2, 8.1,  │
          │        12.3]       │
          └─────────┬──────────┘
                    │
                    ▼
          ┌────────────────────┐
          │ Tote constraints   │
          │ [10.5, 13.0, 20.5] │
          │ Weight: 34.55 LB   │
          └─────────┬──────────┘
                    │
                    ▼
          ┌────────────────────┐
          │ Compare sorted:    │
          │                    │
          │ item[0] ≤ 10.5?   │──NO──→ OVERSIZED (height)
          │ item[1] ≤ 13.0?   │──NO──→ OVERSIZED (width)
          │ item[2] ≤ 20.5?   │──NO──→ OVERSIZED (depth)
          │ weight  ≤ 34.55?  │──NO──→ OVERSIZED (weight)
          │                    │
          │ All pass?          │──YES─→ FITS_TOTE
          └────────────────────┘
```
