# GIF Tote Validation — Autonomous Incident Resolution System

**Project:** GIF Tote Validation Agent  
**Pack ID:** `gif_tote_validation`  
**Version:** 1.0.0  
**Last Updated:** April 16, 2026  
**Team:** MerchantOps - Item Setup/Maintenance

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Solution Architecture](#3-solution-architecture)
4. [Pre-Triage Gate](#4-pre-triage-gate)
5. [Agent Pipeline](#5-agent-pipeline)
6. [Tool Layer — Diagnostic & Action Tools](#6-tool-layer--diagnostic--action-tools)
7. [Decision Matrix Engine](#7-decision-matrix-engine)
8. [Integrations](#8-integrations)
9. [API Endpoints](#9-api-endpoints)
10. [Data Model & Persistence](#10-data-model--persistence)
11. [Evidence & Audit Trail](#11-evidence--audit-trail)
12. [Self-Service Retrieval (Chatbot)](#12-self-service-retrieval-chatbot)
13. [Deployment & Infrastructure](#13-deployment--infrastructure)
14. [Phased Rollout Plan](#14-phased-rollout-plan)
15. [Alignment & Gap Analysis](#15-alignment--gap-analysis)

---

## 1. Executive Summary

The GIF Tote Validation Agent is an AI-powered incident automation system that autonomously resolves **GIF (Global Integrated Fulfilment) tote dimension mismatch** incidents in ServiceNow. Today, when a store reports that an item "does not fit in the tote," a MerchantOps associate manually:

1. Opens the ServiceNow ticket and extracts the UPC/WIN and store number
2. Looks up the GTIN via Uber Keys
3. Queries GIF API for the item's recorded dimensions
4. Checks IQS for Gold status (determines who owns the dimension data)
5. Pulls supplier dimensions from Uber API for comparison
6. Runs a mental calculation against tote constraints (10.5 x 13.0 x 20.5 IN, 34.55 LB)
7. Determines the correct resolution path (route, email merchant, update SSOT, escalate)
8. Executes the fix, writes closure notes, and closes the ticket

**This agent automates the entire workflow end-to-end:**

- **Ingests** incidents from ServiceNow (webhook, polling, or API call)
- **Pre-triages** each incident against assignment group, keyword, and category filters — skipping non-GIF-tote tickets at zero LLM cost
- **Runs** a 5-stage LangGraph topology (triage → evidence → decision → approval/action → closure) where every stage except the diagnostic LLM call is deterministic Python
- **Executes** 6 diagnostic checks across 5 external systems in a strict dependency chain
- **Maps** diagnostic outcomes to 5 runbook cards using a deterministic decision matrix tool (not LLM-based)
- **Compiles** findings and recommends actions for human-in-the-loop approval via Concord
- **Generates** standardized closure notes with issue/fix tags and Slack Summary block
- **Tracks** every step in a PostgreSQL audit trail with business-level evidence extraction
- **Notifies** via Slack threads with structured diagnostic summaries per incident

The system is built on the **Agent Factory** runtime — a config-driven, multi-agent platform where all domain logic lives in YAML/JSON configuration (the "SOP Pack"). Zero domain-specific Python code is needed; new incident types can be onboarded by adding a new pack.

### Key Metrics

| Metric | Manual | Automated |
|--------|--------|-----------|
| Time per ticket | 10-20 minutes | < 2 minutes |
| Systems accessed | 5 (manual lookups) | 5 (API calls) |
| Decision consistency | Variable (human judgment) | 100% deterministic |
| Audit trail | Manual notes | Full evidence chain |
| Cost per non-matching ticket | Full associate time | Zero (pre-triage skip) |

---

## 2. Problem Statement

| Dimension | Current State | Target State |
|-----------|---------------|--------------|
| Ticket pickup | Manual, from ServiceNow dashboard | Automatic: webhook trigger or cron poller |
| Item identification | Manual UPC/WIN lookup, GTIN resolution | Automated Uber Keys API (SI_TO_GTIN, WUPC_TO_GTIN) |
| Dimension retrieval | Manual GIF API query via Postman | Automated GIF API + IQS + Uber API calls |
| Gold status check | Manual IQS lookup to determine dimension owner | Automated IQS API with count_filter processor |
| Tote fit validation | Mental math against tote constraints | Automated sorted-dimension comparison with unit conversion |
| Decision routing | Associate reads playbook, picks action | Deterministic rule engine (5 runbook cards) |
| Merchant outreach | Manual email composition | Automated HTML email via SMTP relay |
| SSOT updates | Manual Slack post to #ssot-gif | Automated Slack post (planned) |
| Closure notes | Associate writes from template | Auto-generated from diagnostic observations |
| Non-GIF tickets | Associate opens ticket, realizes it's wrong team | Pre-triage gate skips at zero cost |
| Visibility | None — no dashboard or analytics | Real-time dashboard with stats, runs, audit trail |

### Incident Volume Context

The MerchantOps - Item Setup/Maintenance team handles GIF tote dimension incidents where stores report items that don't physically fit in the standard GIF tote. These incidents follow predictable patterns:

- **~70%** are genuine oversized items needing dimension correction
- **~20%** are items that actually fit (dimension data is correct, store error)
- **~10%** require escalation (missing data, API failures, edge cases)

The pre-triage gate eliminates processing of non-GIF-tote tickets entirely, and the deterministic decision engine ensures consistent routing for the 90% that can be automated.

---

## 3. Solution Architecture

### High-Level Architecture

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
│  /webhooks/         /webhooks/          /a2a/incident/    /a2a/invoke    │
│  servicenow         slack/events        process           (chat)        │
└──────────┬──────────────────┬──────────────────┬──────────────┬─────────┘
           │                  │                  │              │
           │     ┌────────────┘                  │              │
           │     │                               │              │
           │     ▼                               ▼              │
           │  Retrieval Pipeline           ┌────────────┐       │
           │  (chatbot / self-service)     │ PRE-TRIAGE │       │
           │                               │   GATE     │       │
           │                               └─────┬──────┘       │
           │                              pass ┌──┴──┐ skip     │
           │                                   ▼     ▼          │
           │                           ┌───────────┐ Log &      │
           │                           │ INCIDENT  │ Return     │
           ▼                           │ PIPELINE  │            ▼
    ┌──────────────┐                   └─────┬─────┘     ┌────────────┐
    │ Incident     │                         │           │ Retrieval  │
    │ Pipeline     │                         │           │ Pipeline   │
    │ (autonomous) │                         │           │ (chatbot)  │
    └──────────────┘                         │           └────────────┘
                                             ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                    5-AGENT INCIDENT PIPELINE                              │
│  TriageAgent → DiagnosticAgent → DecisionAgent → ActionAgent → Closure   │
│  (LLM-only)    (6 tool calls)    (rule engine)   (actions)     (notes)   │
└──────────────────────────────────────────────────────────────────────────┘
                                             │
                                             ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                    TOOL LAYER (Async API Clients)                         │
│  Diagnostic: SNOW | UberKeys | GIF API | IQS | Uber API | Tote Logic    │
│  Action: SNOW Update | iSAM | Email | Slack | Decision Matrix | RAG     │
└──────────────────────────────────────────────────────────────────────────┘
                                             │
                                             ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                    PERSISTENCE (PostgreSQL)                               │
│  incident_log  |  audit_trail  |  conversation_state  |  sessions        │
└──────────────────────────────────────────────────────────────────────────┘
```

### Technology Stack

| Layer | Technology |
|-------|-----------|
| Runtime | Python 3.12, FastAPI, Uvicorn |
| Agent Framework | LangGraph 0.6 (StateGraph + Postgres checkpointer) + LangChain 0.3 (`AgentExecutor`, `create_tool_calling_agent`) |
| LLM | Azure OpenAI via WMT LLM Gateway (`gpt-4.1-mini`) |
| Decision Engine | Deterministic YAML rules + RAG fallback |
| Database | PostgreSQL (Azure Flexible Server) |
| Tracing | OpenTelemetry → Walmart TraceStore (OTLP) |
| Config | Dynaconf (`secrets.toml`, env-based) |
| Secrets | Akeyless (prod) / `secrets.toml` (dev) |
| Deployment | KITT (Docker, dev/stage/prod) |
| ServiceNow | REST Table API via signed proxy |
| Slack | slack-bolt / slack-sdk (Events API) |
| Email | SMTP relay (`smtp-gw1.wal-mart.com:25`) |

### Design Principles

1. **Config-driven, zero domain code** — All GIF tote logic lives in `pack.yaml`, `tools.yaml`, `policy.yaml`, and Jinja2 prompt templates (`.j2`). The Agent Factory runtime is completely generic.
2. **Fail-closed pre-triage** — Non-matching incidents are logged and skipped at zero LLM cost. If the SNOW fetch fails, the incident is skipped (not processed).
3. **One-turn-per-agent** — Each agent in the pipeline speaks exactly once. `max_turns: 40` hard caps total pipeline steps (accounts for tool call/result turns consumed by DiagnosticAgent and ActionAgent — DiagnosticAgent alone needs ~14 turns for 6 tools × 2 + text). A custom `selector_func` enforces strict sequential agent ordering.
4. **Deterministic decisions** — The rule engine maps observation codes to runbook cards without LLM interpretation. RAG fallback only fires when no rule matches.
5. **Full audit trail** — Every tool call, result, agent message, and decision is captured as structured evidence in PostgreSQL.
6. **Graceful degradation** — PostgreSQL is optional (in-memory fallback), tool failures are recorded and pipeline continues, approval gates degrade to escalation on timeout.

---

## 4. Pre-Triage Gate

The pre-triage gate is a **fast, LLM-free validation layer** that runs BEFORE the agent pipeline is initialized. Its purpose is to prevent non-GIF-tote incidents from consuming LLM tokens.

### How It Works

```
Incident Number (e.g., INC52148837)
        │
        ▼
┌───────────────────────┐
│  SNOW Fetch            │  ← Uses DIAG-SNOW-01 tool directly
│  (via ToolExecutor)    │     (no LLM, just API call)
└───────────┬───────────┘
            │
     ┌──────▼───────┐
     │ SNOW Response │
     │ Parse Fields  │  ← Handles nested data/raw/raw_data + incident_ prefix
     └──────┬───────┘
            │
   ┌────────▼────────────────────────────┐
   │  CHECK 1: Assignment Group           │
   │  Is assignment_group in allowed list?│
   │  Allowed: "MerchantOps - Item Setup/ │
   │           Maintenance", "GIF"        │
   └────────┬──────────────────┬─────────┘
         YES│               NO │→ SKIP (log with SNOW value + accepted values)
            │
   ┌────────▼────────────────────────────┐
   │  CHECK 2: Keywords                   │
   │  Does short_description contain any  │
   │  of: dimension, tote, GIF, GTIN,    │
   │  incorrect, does not fit?            │
   └────────┬──────────────────┬─────────┘
         YES│               NO │→ SKIP
            │
   ┌────────▼────────────────────────────┐
   │  CHECK 3: Category                   │
   │  Is category in allowed list?        │
   │  Allowed: GIF, Software, Application │
   └────────┬──────────────────┬─────────┘
         YES│               NO │→ SKIP
            │
            ▼
    PASS → Run full pipeline
```

### Key Design Decisions

- **Fail-closed**: If SNOW fetch fails or the tool can't be resolved, the incident is SKIPPED (not processed). This prevents burning LLM tokens on broken upstream dependencies.
- **Enriched skip reasons**: Skip messages include both the SNOW actual value and the accepted values list, e.g.: `"assignment_group 'network ops' not in allowed list. SNOW value: 'network ops'. Accepted: ['MerchantOps - Item Setup/Maintenance', 'GIF']"`
- **Audit metadata**: Skipped incidents are logged to `incident_log` with `status='skipped'` and carry `snow_fields` metadata showing what SNOW returned.
- **Field resolution**: SNOW responses nest fields under `data`/`raw`/`raw_data` with `incident_`-prefixed keys. The `_get()` helper tries all variants: `incident_<field>`, `<field>`, `<field>_name`.

### Configuration (pack.yaml)

```yaml
pre_triage:
  enabled: true
  snow_tool: DIAG-SNOW-01
  assignment_groups:
    - "MerchantOps - Item Setup/Maintenance"
    - "GIF"
  keywords:
    - "dimension"
    - "tote"
    - "GIF"
    - "GTIN"
    - "incorrect"
    - "does not fit"
  categories:
    - "GIF"
    - "Software"
    - "Application"
```

---

## 5. Agent Pipeline

The incident pipeline is a compiled **LangGraph `StateGraph`** with explicit edges between deterministic Python nodes.  Only the `evidence` node invokes the LLM — and it does so through a fresh `langchain.agents.AgentExecutor` built from `pack.yaml` by `LangChainAgentBuilder`.  The remaining stages (triage, decision, approval, action, closure) are zero-token deterministic helpers.  Topology and node ordering are driven by `pack.yaml` and compiled by `agent_factory/graph/factory.py` rather than emerging from an LLM-selected speaker order — so the pipeline is strictly sequential, easy to inspect, and resumable from any super-step via the Postgres checkpointer.

### Pipeline Agents

| Step | Agent | Role | Tools | Output |
|------|-------|------|-------|--------|
| 1 | **TriageAgent** | Extract incident parameters, classify symptom | None (LLM-only) | `{incident_number, upc, win, store, symptom, confidence}` |
| 2 | **DiagnosticAgent** | Run diagnostic checks across 5 systems | DIAG-SNOW-01, DIAG-UBERKEYS-01, DIAG-API-01, DIAG-API-02, DIAG-API-03, DIAG-LOGIC-01 | Observation report with outcome codes |
| 3 | **DecisionAgent** | Map observations to runbook card | DIAG-DECISION-MATRIX, DIAG-RAG-FALLBACK | `{runbook_card, confidence, reasoning}` |
| 4 | **ActionAgent** | Compile findings and recommend actions (observation mode) | QRY-ISAM-01 | `{findings, recommended_actions}` |
| 5 | **ClosureAgent** | Generate closure summary with findings and recommendations (observation mode — does not close ticket) | None (LLM-only) | Standardized closure block with PENDING_REVIEW status |

### Pipeline Flow

```
Incident Text (from ServiceNow)
        │
        ▼
  ┌─────────────┐     Output: {INC#, UPC, WIN, Store, Symptom}
  │ TriageAgent │───────────────────────────────────────────────────┐
  └─────────────┘                                                    │
        │                                                            │
        ▼                                                            │
  ┌──────────────┐    Output: DIAGNOSTIC OBSERVATIONS report         │
  │ Diagnostic   │    DIAG-SNOW-01: INCIDENT_MATCHED                 │
  │ Agent        │    DIAG-UBERKEYS-01: GTIN_FOUND                   │
  │ (6 tools)    │    DIAG-API-01: DATA_FOUND (dimensions)           │
  │              │    DIAG-API-02: GOLD / NOT_GOLD                   │
  │              │    DIAG-API-03: DATA_FOUND (supplier dims)        │
  │              │    DIAG-LOGIC-01: FITS_TOTE / OVERSIZED           │
  └──────────────┘───────────────────────────────────────────────────┤
        │                                                            │
        ▼                                                            │
  ┌──────────────┐    Output: {runbook_card, confidence}             │
  │ Decision     │    RBK-GIF-01 through RBK-GIF-05                  │
  │ Agent        │───────────────────────────────────────────────────┤
  └──────────────┘                                                   │
        │                                                            │
        ▼                                                            │
  ┌──────────────┐    Output: {actions_taken, api_results}           │
  │ Action       │    Ticket routing, email, SSOT post               │
  │ Agent        │───────────────────────────────────────────────────┤
  └──────────────┘                                                   │
        │                                                            │
        ▼                                                            │
  ┌──────────────┐    Output: {closure_notes, tags}                  │
  │ Closure      │───────────────────────────────────────────────────┘
  │ Agent        │          All outputs → team_state → DB
  └──────────────┘
        │
        ▼
  Findings posted to Slack (PENDING_REVIEW) — team reviews and acts
```

### Diagnostic Dependency Chain

The DiagnosticAgent's tool calls form a strict dependency chain. If a step fails, all dependent steps are SKIPPED:

```
DIAG-SNOW-01  (no deps — always runs first)
    ↓ requires: UPC or WIN + Store Number extracted
DIAG-UBERKEYS-01  (depends on SNOW)
    ↓ requires: resolved GTIN
DIAG-API-01  (depends on GTIN from UBERKEYS)
    ↓ GIF API dimensions
DIAG-API-02  (depends on GTIN from UBERKEYS)
    ↓ IQS Gold status
DIAG-API-03  (depends on GTIN + API-02 = NOT_GOLD; SKIP if GOLD)
    ↓ Uber supplier dimensions (only for non-Gold items)
DIAG-LOGIC-01  (depends on dimensions from API-01 or API-03)
    ↓ Tote fit result
```

**Rules:**
- Each tool is called AT MOST ONCE (except UBERKEYS which gets one WIN try + one UPC try)
- Failed steps are marked SKIPPED, not retried
- The agent produces ONE observation report and stops

### Selector Prompt (Orchestration)

The selector prompt enforces strict sequential ordering:

```
PIPELINE ORDER (strictly sequential — never go backward):
  1. TriageAgent → extracts incident parameters. Goes FIRST and only once.
  2. DiagnosticAgent → runs tool calls. Goes SECOND and only once.
  3. DecisionAgent → maps observations to runbook. Goes THIRD and only once.
  4. ActionAgent → compiles findings and recommends actions. Goes FOURTH and only once.
  5. ClosureAgent → generates closure summary (PENDING_REVIEW). Goes FIFTH (LAST).

RULES:
  - NEVER select an agent that has already produced output
  - Each agent gets exactly ONE turn
  - After ClosureAgent speaks, the pipeline MUST end
```

---

## 6. Tool Layer — Diagnostic & Action Tools

All tools are defined declaratively in `tools.yaml`. The Agent Factory's `ToolExecutor` handles HTTP calls, ServiceNow operations, auth resolution, response extraction, and outcome derivation generically — no Python code needed per tool.

### Tool Types Used

| Type | Description | Auth Resolution |
|------|-------------|-----------------|
| `servicenow` | ServiceNow REST Table API operations (get, search, update) | RSA-SHA256 signed headers via proxy |
| `http_api` | Generic HTTP API calls (GET/POST) with configurable headers | `{{KEY}}` placeholders resolved from `secrets.toml` |
| `threshold_check` | Numeric threshold comparison with unit conversion (tote fit) | N/A (local) |
| `decision_matrix` | Deterministic first-match rule engine for runbook routing | N/A (local) |
| `python_function` | Local Python function invocation (import path in config) | N/A (local) |

### Diagnostic Tools (Read-Only)

| Tool ID | Type | External System | Purpose | Outcomes |
|---------|------|----------------|---------|----------|
| DIAG-SNOW-01 | servicenow | ServiceNow Proxy | Fetch incident, extract form data | INCIDENT_MATCHED, INCIDENT_NOT_MATCHED, PARSE_FAILURE |
| DIAG-UBERKEYS-01 | http_api | Uber Keys API | Resolve GTIN from UPC or WIN | GTIN_FOUND, GTIN_NOT_FOUND |
| DIAG-API-01 | http_api | GIF API (IQS GraphQL) | Item dimensions (H/W/D/Weight) | DATA_FOUND, DATA_NOT_FOUND, AUTH_ERROR |
| DIAG-API-02 | http_api | IQS Catalog API | Gold status (dimension owner) | GOLD, NOT_GOLD, AUTH_ERROR |
| DIAG-API-03 | http_api | Uber API | Supplier dimensions | DATA_FOUND, DATA_NOT_FOUND, AUTH_ERROR |
| DIAG-LOGIC-01 | threshold_check | Local | Tote fit check (sorted-dimension comparison) | FITS_TOTE, OVERSIZED |

### Decision Tools

| Tool ID | Type | Purpose | Outcomes |
|---------|------|---------|----------|
| DIAG-DECISION-MATRIX | decision_matrix | Deterministic rule engine | Matched rule + runbook card |
| DIAG-RAG-FALLBACK | python_function | RAG-based fallback when no rule matches | Suggested runbook + reasoning |

### Action Tools (Write Operations)

| Tool ID | Type | External System | Purpose | Risk |
|---------|------|----------------|---------|------|
| QRY-SNOW-01 | servicenow | ServiceNow | Poll for GIF tote incidents | Low |
| QRY-SNOW-02 | servicenow | ServiceNow | Update incident (work notes, routing, close) | **Medium** |
| QRY-GIF-01 | http_api | GIF API | Query dimensions (ActionAgent) | Low |
| QRY-IQS-01 | http_api | IQS API | Query Gold status (ActionAgent) | Low |
| QRY-UBER01 | http_api | Uber API | Query supplier dimensions (ActionAgent) | Low |
| QRY-ISAM-01 | python_function | iSAM (MOCK) | Merchant email lookup / dimension update | Low |
| ACT-EMAIL-01 | python_function | SMTP Relay | Send merchant outreach email (params: `incident_number`, `gtin`, `merchant_email`, `merchant_name`, `gold_dims`, `supplier_dims`, `item_id`, `item_description`, `store_report`) | **Medium** |

### Response Processors

Each tool's response is processed by a configurable processor:

| Processor | Logic |
|-----------|-------|
| `passthrough` | Return raw response as-is |
| `field_presence` | Check if specified fields exist in response → DATA_FOUND / DATA_NOT_FOUND |
| `count_filter` | Count items in an array matching a filter value → GOLD / NOT_GOLD |

### Retry Policy

All HTTP API tools share a common retry configuration:
- **Max attempts:** 3
- **Backoff:** 1.0s × 2.0 multiplier (1s, 2s, 4s)
- **Retryable codes:** 429, 502, 503, 504

### Tote Fit Engine

The `DIAG-LOGIC-01` tool uses a **sorted-dimension comparison** algorithm:

1. Convert dimensions to inches (CM→IN, MM→IN) and weight to pounds (KG→LB, G→LB, OZ→LB)
2. Sort item dimensions [smallest, medium, largest]
3. Sort tote dimensions [10.5, 13.0, 20.5] (already sorted)
4. Compare each: `item[i] <= tote[i]` for all three dimensions
5. Compare weight: `item_weight <= 34.55 LB`
6. Result: `FITS_TOTE` if all pass, `OVERSIZED` with details of which dimension(s) exceeded

---

## 7. Decision Matrix Engine

The DecisionAgent uses a **deterministic rule engine** (not LLM-based) to map diagnostic outcomes to runbook cards. This ensures 100% reproducibility and auditability.

### Runbook Cards

| Card | Name | Condition | Automated Action | Approval |
|------|------|-----------|-----------------|----------|
| **RBK-GIF-01** | Auto-Route to Picking | FITS_TOTE | Route ticket to `OPS - eComFulfillment - Picking` | No |
| **MERCHANT_OUTREACH** | Merchant Dimension Verification | OVERSIZED + no merchant response yet | Email merchant via iSAM lookup + ACT-EMAIL-01, set ticket to Pending | No |
| **RBK-GIF-02** | Route (Merchant Confirmed) | OVERSIZED + merchant says dims correct | Route ticket to GIF Picking Team | No |
| **RBK-GIF-03** | SSOT Update (Gold) | OVERSIZED + needs update + GOLD | Post to `#ssot-gif` Slack channel | No |
| **RBK-GIF-04** | iSAM Update (Supplier) | OVERSIZED + needs update + NOT_GOLD | Update dimensions via iSAM API | **Yes** |
| **RBK-GIF-05** | Manual Escalation | No rule match / API errors / missing data | Escalate to MerchantOps L2 | No |

### Decision Flow

```
Diagnostic Observations
        │
        ▼
┌───────────────────┐
│ Critical errors?   │──YES──→ RBK-GIF-05 (Escalate)
│ (API_ERROR, etc.)  │
└───────┬───────────┘
        │ NO
        ▼
┌───────────────────┐
│ DIAG-LOGIC-01     │
│ = FITS_TOTE?      │──YES──→ RBK-GIF-01 (Auto-Route)
└───────┬───────────┘
        │ NO (OVERSIZED)
        ▼
┌───────────────────┐
│ merchant_response  │
│ present?           │──NO──→ MERCHANT_OUTREACH (Email merchant, set Pending)
└───────┬───────────┘
        │ YES
        ▼
┌───────────────────┐
│ Merchant Response  │
│ = DIMS_CORRECT?    │──YES──→ RBK-GIF-02 (Route)
└───────┬───────────┘
        │ NO (NEEDS_UPDATE)
        ▼
┌───────────────────┐
│ DIAG-API-02       │
│ = GOLD?           │──YES──→ RBK-GIF-03 (SSOT)
└───────┬───────────┘
        │ NO (NOT_GOLD)
        ▼
    RBK-GIF-04 (iSAM Update)
```

### Rule Evaluation

Rules are evaluated **in order** — first match wins:

```python
RULES = [
    # RULE-1: Item fits tote — auto-route
    {"conditions": {"DIAG-LOGIC-01": "FITS_TOTE"},                                               → "RBK-GIF-01"},
    # RULE-2: Oversized, first encounter (no merchant response yet) — email merchant
    {"conditions": {"DIAG-LOGIC-01": "OVERSIZED"}, "requires_absent": ["merchant_response"],     → "MERCHANT_OUTREACH"},
    # RULE-3: Oversized, merchant confirmed dims correct — route
    {"conditions": {"DIAG-LOGIC-01": "OVERSIZED", "merchant_response": "DIMENSIONS_CORRECT"},    → "RBK-GIF-02"},
    # RULE-4: Oversized, needs update, Gold item — SSOT post
    {"conditions": {"DIAG-LOGIC-01": "OVERSIZED", "merchant_response": "DIMENSIONS_NEED_UPDATE",
                    "DIAG-API-02": "GOLD"},                                                       → "RBK-GIF-03"},
    # RULE-5: Oversized, needs update, non-Gold — iSAM update
    {"conditions": {"DIAG-LOGIC-01": "OVERSIZED", "merchant_response": "DIMENSIONS_NEED_UPDATE",
                    "DIAG-API-02": "NOT_GOLD"},                                                   → "RBK-GIF-04"},
]
FALLBACK → "RBK-GIF-05"  # No match = escalate
```

> **`requires_absent`** — a rule constraint introduced for RULE-2. The rule only matches when the listed keys are NOT present in observations. This handles first-encounter OVERSIZED incidents where no merchant response exists yet.

### Confidence Levels

| Level | Meaning |
|-------|---------|
| `high` | Rule matched with all conditions satisfied, or critical error detected |
| `medium` | Fallback triggered (no rule matched, but no errors) |
| `low` | Observations couldn't be parsed |

---

## 8. Integrations

### External Systems Map

```
┌──────────────────────────────────────────────────────────────────┐
│                    GIF TOTE VALIDATION AGENT                      │
│                                                                    │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌──────────────┐ │
│  │ Triage    │  │ Diagnostic│  │ Decision  │  │ Action       │ │
│  │ Agent     │  │ Agent     │  │ Agent     │  │ Agent        │ │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘  └──────┬───────┘ │
└────────┼──────────────┼──────────────┼────────────────┼──────────┘
         │              │              │                │
         │    ┌─────────┼──────────────┼────────────────┤
         │    │         │              │                │
         ▼    ▼         ▼              ▼                ▼
┌─────────────────┐ ┌────────┐ ┌──────────┐ ┌──────────────────┐
│   ServiceNow    │ │  Uber  │ │ Decision │ │  External APIs   │
│   Proxy         │ │  Keys  │ │ Matrix   │ │                  │
│   (RSA signed)  │ │  API   │ │ (local)  │ │ ┌──────────────┐ │
│                 │ │        │ │          │ │ │ GIF API      │ │
│ • Get incident  │ │ • UPC  │ │ • Rules  │ │ │ (IQS GraphQL)│ │
│ • Search        │ │   →GTIN│ │ • RAG    │ │ └──────────────┘ │
│ • Update        │ │ • WIN  │ │   fallbk │ │ ┌──────────────┐ │
│ • Close         │ │   →GTIN│ │          │ │ │ IQS Catalog  │ │
└─────────────────┘ └────────┘ └──────────┘ │ │ API          │ │
                                             │ └──────────────┘ │
┌─────────────────┐ ┌────────────────────┐  │ ┌──────────────┐ │
│   SMTP Relay    │ │   Slack            │  │ │ Uber API     │ │
│   (smtp-gw1)    │ │   (#ssot-gif)      │  │ │ (Supplier)   │ │
│                 │ │                    │  │ └──────────────┘ │
│ • Merchant      │ │ • SSOT dimension   │  │ ┌──────────────┐ │
│   outreach      │ │   update requests  │  │ │ iSAM         │ │
│   emails        │ │                    │  │ │ (MOCK)       │ │
└─────────────────┘ └────────────────────┘  │ └──────────────┘ │
                                             └──────────────────┘
```

### Integration Details

| System | Protocol | Auth | Endpoint Pattern | Used By |
|--------|----------|------|-----------------|---------|
| **ServiceNow Proxy** | HTTPS REST | RSA-SHA256 signed headers | `servicenow_proxy` connection | DIAG-SNOW-01, QRY-SNOW-01/02 |
| **Uber Keys** | HTTPS REST | WM_CONSUMER.ID header | `{{UBER_KEYS_BASE_URL}}?key=&type=` | DIAG-UBERKEYS-01 |
| **GIF API** | HTTPS POST (GraphQL) | WM_CONSUMER.ID + SVC headers | `{{GIF_API_URL}}` | DIAG-API-01, QRY-GIF-01 |
| **IQS Catalog** | HTTPS GET | WM_CONSUMER.ID + LIMO subscription | `{{IQS_API_URL}}?id=&type=GTIN` | DIAG-API-02, QRY-IQS-01 |
| **Uber API** | HTTPS GET | WM_CONSUMER.ID + SVC headers | `{{UBER_API_URL}}?id=&type=GTIN&rt=TI` | DIAG-API-03, QRY-UBER01 |
| **iSAM** | Python mock | N/A (mock) | Local function call | QRY-ISAM-01 |
| **SMTP Relay** | SMTP port 25 | Anonymous (internal relay) | `smtp-gw1.wal-mart.com:25` | ACT-EMAIL-01 |
| **Slack** | HTTPS (slack-sdk) | Bot token | `#ssot-gif` channel | Planned |
| **WMT LLM Gateway** | HTTPS REST | Sandbox JWT / RSA | `wmtllmgateway.stage.walmart.com` | All agents (gpt-4.1-mini) |

### Auth Resolution

All credentials are resolved from `secrets.toml` at runtime via Dynaconf. The `{{KEY}}` placeholders in `tools.yaml` headers and URLs are replaced by `ToolExecutor` before each API call. Credentials never appear in LLM context or audit logs.

---

## 9. API Endpoints

### Endpoint Summary

| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| POST | `/a2a/invoke` | Synchronous chat (retrieval pipeline) | Optional headers |
| POST | `/a2a/invoke-stream` | Streaming chat with SSE events | Optional headers |
| POST | `/a2a/work-item/process` | Process incident by number (pre-triage + pipeline) | Optional headers |
| POST | `/a2a/approval/complete` | Concord approval callback (execute approved actions) | None (internal) |
| POST | `/webhooks/slack/events` | Slack Events API handler | Slack verification |
| GET | `/.well-known/agents.json` | A2A agent card (discovery) | None |
| GET | `/api/factory/health` | Pack health status | None |
| GET | `/api/factory/tools` | Tool availability report | None |
| GET | `/api/pack/info` | Loaded pack metadata | None |
| GET | `/healthz` | Kubernetes liveness probe | None |
| GET | `/readyz` | Kubernetes readiness probe | None |
| GET | `/api/dashboard/stats` | Dashboard summary statistics | None |
| GET | `/api/dashboard/incidents` | List incidents (filterable) | None |
| GET | `/api/dashboard/incidents/{id}` | Incident detail + audit trail + runs | None |
| GET | `/api/dashboard/audit` | Query audit trail events | None |
| GET | `/api/dashboard/trends` | Daily bucketed incident counts + token usage | None |
| GET | `/api/dashboard/performance` | MTTR, SLA compliance, runbook distribution | None |

### Key Endpoint: Process Incident

```bash
POST /a2a/work-item/process
Content-Type: application/json

{
  "incident_number": "INC52148837"
}
```

**Response (processed):**
```json
{
  "incident_number": "INC52148837",
  "status": "processed",
  "skip_reason": null,
  "response": "Pipeline completed. Runbook RBK-GIF-01 applied...",
  "session_id": "abc123",
  "agent_name": "GIF Tote Validation Agent",
  "time_taken": 45.2
}
```

**Response (skipped):**
```json
{
  "incident_number": "INC52552230",
  "status": "skipped",
  "skip_reason": "assignment_group 'network ops' not in allowed list. SNOW value: 'network ops'. Accepted: ['MerchantOps - Item Setup/Maintenance', 'GIF']",
  "response": "Incident skipped by pre-triage gate...",
  "session_id": "def456",
  "agent_name": "GIF Tote Validation Agent",
  "time_taken": 1.2
}
```

### Incident Detail (Dashboard)

The `/api/dashboard/incidents/{id}` endpoint returns incidents grouped by **runs**:

```json
{
  "incident": { "incident_number": "INC52148837", "status": "resolved", ... },
  "runs": [
    {
      "run_number": 1,
      "status": "skipped",
      "events": [...],
      "started_at": "2026-04-07T10:00:00Z",
      "ended_at": "2026-04-07T10:00:01Z",
      "duration_ms": 1200
    },
    {
      "run_number": 2,
      "status": "resolved",
      "events": [...],
      "started_at": "2026-04-07T14:30:00Z",
      "ended_at": "2026-04-07T14:31:15Z",
      "duration_ms": 75000
    }
  ],
  "audit_trail": [...]
}
```

---

## 10. Data Model & Persistence

### Why PostgreSQL (Not OpenObserve)

The incident log, audit trail, and conversation state are stored in **PostgreSQL** — not in an observability platform like OpenObserve. This is a deliberate architectural choice:

| Concern | PostgreSQL (State Store) | OpenObserve (Observability) |
|---------|--------------------------|----------------------------|
| **Purpose** | Source of truth for incident status, audit records, session state | Log search, traces, dashboards |
| **Consistency** | ACID transactions, strong consistency | Eventually consistent |
| **Access pattern** | Point reads (`WHERE incident_number = $1`), updates | Full-text search, aggregations |
| **Mutations** | Yes — status updates, approval flags, token counts | Append-only (no updates) |
| **Schema** | Strict (INT, TIMESTAMPTZ, JSONB) | Schema-on-read |
| **Lifecycle** | Hot data (active incidents, recent history) | Cold data (long-term retention) |
| **Dashboard** | Real-time status, run grouping, stats | Historical trends, log correlation |

**Bottom line:** State data needs ACID guarantees and point-update semantics. Observability data is append-only and eventually consistent. Using OpenObserve for state management would require building a custom mutation layer on top of an append-only store — adding complexity without benefit.

Both systems complement each other: PostgreSQL for state, OpenTelemetry → OpenObserve for traces and logs.

### Tables

#### `gif_tote_validation_agent_incident_log`

Primary table — one row per incident, updated as the pipeline progresses.

| Column | Type | Description |
|--------|------|-------------|
| `incident_number` | TEXT PK | ServiceNow INC number |
| `sys_id` | TEXT | ServiceNow sys_id |
| `session_id` | TEXT | Pipeline session ID |
| `store_number` | INT | Store that reported the issue |
| `department` | INT | Department number |
| `category` | INT | SNOW category code |
| `short_description` | TEXT | Original incident description |
| `symptom` | TEXT | Classified symptom |
| `source_channel` | VARCHAR | How incident arrived (a2a, snow, slack) |
| `status` | VARCHAR | processing → decided → pending_review / escalated / resolved / skipped / failed |
| `mep_results` | JSONB | Full diagnostic observation data |
| `runbook_card` | TEXT | Selected runbook (RBK-GIF-01 through 05) |
| `card_name` | TEXT | Human-readable card name |
| `decision_confidence` | TEXT | high / medium / low |
| `requires_approval` | BOOL | Whether approval gate was triggered |
| `approval_status` | VARCHAR | pending / approved / rejected / timeout |
| `approved_by` | TEXT | Who approved |
| `approved_at` | TIMESTAMPTZ | When approved |
| `actions_taken` | JSONB | List of actions executed |
| `issue_tag` | TEXT | Issue classification tag |
| `fix_tag` | TEXT | Fix classification tag |
| `closure_notes` | TEXT | Generated closure notes |
| `error_data` | JSONB | Error details (for failed/skipped) |
| `processing_time_ms` | INT | Total pipeline duration |
| `prompt_tokens` | INT | LLM prompt tokens consumed |
| `completion_tokens` | INT | LLM completion tokens consumed |
| `total_tokens` | INT | Total LLM tokens consumed |
| `run_number` | INT | Increments on re-processing |
| `created_at` | TIMESTAMPTZ | First seen |
| `updated_at` | TIMESTAMPTZ | Last updated |
| `resolved_at` | TIMESTAMPTZ | When resolved/escalated |

#### `audit_trail`

Append-only event log — multiple rows per incident.

| Column | Type | Description |
|--------|------|-------------|
| `event_id` | TEXT PK | Unique event ID |
| `incident_number` | TEXT | FK to incident_log |
| `session_id` | TEXT | Pipeline session |
| `event_type` | TEXT | pipeline_start, pre_triage_skip, tool_call, tool_result, decision, action, pipeline_end |
| `status` | TEXT | success, error, skipped |
| `agent` | TEXT | Which agent produced the event |
| `tool` | TEXT | Tool ID (for tool events) |
| `detail` | JSONB | Event-specific payload |
| `duration_ms` | INT | Step duration |
| `created_at` | TIMESTAMPTZ | Event timestamp |

#### `sessions` / `messages`

Conversation state for the retrieval (chatbot) pipeline.

| Table | Key Columns |
|-------|-------------|
| `sessions` | session_id, user_id, pack_id, last_outcome, turn_count |
| `messages` | message_id, session_id, role, content, token_count |

### Schema Migrations

| Migration | Purpose |
|-----------|---------|
| `001_initial.sql` | Create sessions and messages tables |
| `002_add_columns.sql` | Add outcome tracking to sessions |
| `003_add_token_columns.sql` | Add LLM token tracking to incident_log |
| `004_add_run_number.sql` | Add run_number for re-processing tracking |

---

## 11. Evidence & Audit Trail

### Evidence Extraction

After every pipeline run, the `extract_evidence()` function consumes the LangChain `AgentExecutor` output directly — the `(AgentAction, observation)` tuples on `intermediate_steps` plus the agent's final `output` text — and emits a structured audit trail.  Both the chat path (`agent_factory/runtime/chat.py`) and the LangGraph evidence node (`agent_factory/nodes/evidence.py`) pass the same shape in, so the evidence schema is identical across both paths:

```
LangChain executor result
  ├── intermediate_steps: list[(AgentAction, observation)]
  └── output:              str (the agent's final text)
        │
        ▼
  ┌─────────────────────────┐
  │ For each (action, obs)  │  Walk the tuple list in order
  │ pair:                   │
  │  • emit "tool_call"     │  action.tool, action.tool_input,
  │                         │  call_id from action.message_log[*]
  │                         │  .tool_calls (falling back to call_N)
  │  • emit "tool_result"   │  observation text + derived status/outcome
  └────────────┬────────────┘
               │
  ┌────────────▼────────────┐
  │ Final output → "agent_  │  upgraded to "decision" when the
  │ message" entry          │  text parses as JSON with a
  │                         │  runbook_card payload
  └─────────────────────────┘
```

### Tool Result Status Derivation

Tool results are not blindly marked "success." The `_derive_tool_status()` function parses the result JSON:

```python
# Error outcomes that indicate failure
_ERROR_OUTCOMES = {
    "not_found", "auth_error", "bad_request", "rate_limited",
    "upstream_error", "upstream_unavailable", "method_not_allowed",
    "snow_error", "api_error", "incident_not_found", "incident_not_matched",
    "parse_failure", "email_failed", "update_failed", "gtin_not_found",
    "email_not_found",
}
# NOTE: "data_not_found" is intentionally EXCLUDED — it means "no data
# available" (e.g., supplier dims not in Uber API), which is an expected
# condition for optional data sources, NOT a pipeline failure.

# HTTP error codes
_ERROR_HTTP_CODES = {"400", "401", "403", "404", "405", "429", "500", "502", "503", "504"}
```

### Pipeline Health Summary

The `summarise_pipeline_health()` function aggregates evidence into a health report:

```json
{
  "tool_calls": 6,
  "tool_successes": 4,
  "tool_failures": 2,
  "failed_tools": [
    {"tool": "DIAG-API-01", "outcome": "AUTH_ERROR"},
    {"tool": "DIAG-API-03", "outcome": "DATA_NOT_FOUND"}
  ],
  "has_failures": true,
  "pipeline_status": "partial"
}
```

Pipeline status values:
- `success` — all tools succeeded
- `partial` — some tools failed, some succeeded
- `failed` — all tools failed
- `no_tools` — no tools were called

This feeds into the incident resolution status. The **ClosureAgent's stated status takes priority** over pipeline health:

1. If ClosureAgent outputs `Status: PENDING_REVIEW` → status = `"pending_review"` (observation mode default)
2. If ClosureAgent outputs `Status: ESCALATED` → status = `"escalated"`
3. Fallback (no closure status extracted):
   - `tool_failures == 0` → status = `"resolved"`
   - `tool_successes > 0 && tool_failures > 0` → status = `"resolved_partial"`
   - `tool_failures > 0 && tool_successes == 0` → status = `"escalated"`

> **Note:** In observation mode, the ClosureAgent always outputs `Status: PENDING_REVIEW` — the team reviews findings and acts manually.

---

## 12. Self-Service Retrieval (Chatbot)

The retrieval pipeline provides interactive access via Slack, Teams, or the REST API.

### Retrieval Pipeline

| Agent | Role | Tools |
|-------|------|-------|
| **RetrievalAgent** | Answers questions, checks status, executes self-service actions | QRY-SNOW-01, QRY-SNOW-02, QRY-GIF-01, QRY-IQS-01, QRY-UBER01 |

Driven by `runtime.chat.run_chat` / `run_chat_stream`, which builds a per-request `AgentExecutor` (`max_iterations: 10`) with a `chat_history` `MessagesPlaceholder` for multi-turn memory.

### Capabilities

- **Status check**: "What's the status of INC52148837?"
- **Dimension lookup**: "What are the dimensions for GTIN 00012345678901?"
- **Gold status**: "Is this item Gold?"
- **Incident search**: "Show me recent GIF tote incidents for store 4567"

### Channels

| Channel | Endpoint | Processing |
|---------|----------|-----------|
| REST API (sync) | `POST /a2a/invoke` | Synchronous response |
| REST API (stream) | `POST /a2a/invoke-stream` | SSE streaming |
| Slack | `POST /webhooks/slack/events` | Background task + Slack reply |

---

## 13. Deployment & Infrastructure

### KITT Deployment

```yaml
# kitt.yml (simplified)
application:
  name: gif-tote-validation-agent
  runtime: python3.12
  port: 8000

resources:
  cpu: "500m"
  memory: "1Gi"

environments:
  dev:
    replicas: 1
    env:
      - AGENT_FACTORY_ENV: dev
  stage:
    replicas: 2
    env:
      - AGENT_FACTORY_ENV: stage
  prod:
    replicas: 3
    env:
      - AGENT_FACTORY_ENV: prod
```

### Configuration Hierarchy

```
secrets.toml (Dynaconf)
├── [default]
│   ├── AGENT_NAME
│   ├── APP_TITLE
│   └── APP_DESCRIPTION
├── [default.azure_chat]
│   ├── provider, model, deployment
│   ├── endpoint, api_version
│   └── api_key (from Akeyless in prod)
├── [default.postgresql]
│   ├── host, port, database
│   ├── user, password
│   └── min_size, max_size
├── [default.servicenow_proxy]
│   ├── base_url
│   └── private_key_path
└── [default.slack]
    └── SLACK_BOT_TOKEN
```

### Health Checks

| Endpoint | Type | Checks |
|----------|------|--------|
| `/healthz` | Liveness | PostgreSQL connection, pack registry initialized |
| `/readyz` | Readiness | PostgreSQL available (blocking dependency) |
| `/api/factory/health` | Detailed | Per-pack tool binding status, warnings |

### Policy Guardrails

From `policy.yaml`:

```yaml
approvals:
  required_for_cards: [RBK-GIF-04]  # iSAM update requires approval
  required_for_tools: []
  approval_channel: concord
  concord_entry_point: "gif-tote-approval"
  timeout_minutes: 30
  ad_group: MerchantOps-ItemSetup-Approvers

blast_radius:
  max_batch_size: 1  # One incident at a time
  limits:
    max_routing_per_hour: 20
    max_isam_updates_per_hour: 5

permitted_actions:
  - "Automated ticket routing (assignment group changes)"
  - "Work notes and comments updates on ServiceNow incidents"
  - "Merchant outreach emails via SMTP"
  - "Slack posts to #ssot-gif channel for Gold dimension updates"
  - "iSAM dimension updates (supplier dimensions only — requires approval)"

denied_actions:
  - "Deleting or closing incidents without validation"
  - "Modifying Gold dimensions directly (must go through SSOT team)"
  - "Changing incident priority or impact"
  - "Creating new incidents"

feature_flags:
  enable_rag_fallback: true
  enable_auto_close: true
  enable_merchant_outreach: true
  enable_ssot_slack_post: true
  enable_isam_direct_update: false
```

---

## 14. Phased Rollout Plan

### Phase 1: Foundation (Complete)

- [x] Agent Factory runtime with SOP Pack support
- [x] 5-agent incident pipeline (Triage → Diagnostic → Decision → Action → Closure)
- [x] Pre-triage gate with fail-closed semantics
- [x] Tools in YAML config (diagnostic + action) with 5 tool types
- [x] Deterministic decision matrix tool type (5 runbook cards)
- [x] Threshold check tool type (tote fit with unit conversion)
- [x] PostgreSQL persistence (incident_log, audit_trail, state)
- [x] Evidence extraction with tool status derivation
- [x] REST API endpoints (sync, stream, incident process)
- [x] ServiceNow webhook receiver
- [x] Slack webhook receiver
- [x] SNOW cron poller
- [x] Dashboard API (stats, incidents, audit, trends, performance)
- [x] OpenTelemetry tracing integration
- [x] Kubernetes health checks

### Phase 2: Production Hardening (In Progress)

- [x] Enriched skip reasons with SNOW values
- [x] Pipeline health tracking (success/partial/failed)
- [x] One-turn-per-agent enforcement (custom selector_func)
- [x] Diagnostic dependency chain enforcement
- [x] Jinja2 prompt templates (.j2) with sandboxed rendering
- [x] Per-agent and per-request LLM token tracking
- [x] Concord approval workflow (human-in-the-loop)
- [x] Slack thread integration (per-incident diagnostic summaries)
- [x] Safety net: deterministic tote fit check when LLM skips DIAG-LOGIC-01
- [x] Closure status extraction (PENDING_MERCHANT, ROUTED, ESCALATED)
- [ ] Real iSAM API integration (replacing mock)
- [ ] Slack #ssot-gif tool for Gold dimension updates
- [ ] Merchant reply loop (email → SNOW → pipeline re-entry)
- [ ] SonarQube quality gate pass

### Phase 3: Scale & Optimize

- [ ] Batch incident processing (configurable batch_size)
- [ ] MS Teams bot integration
- [ ] Email ingress channel
- [ ] RAG knowledge base for edge case decisions
- [ ] Weekly digest email with resolution statistics
- [ ] Dashboard UI (static HTML in `/static/`)

### Phase 4: Advanced

- [ ] Multi-pack support (additional incident types)
- [ ] A2A agent federation (call external agents)
- [ ] ML-based pre-triage (learn from skip patterns)
- [ ] Automated SOP pack generation from playbook documents

---

## 15. Alignment & Gap Analysis

### SOP vs Implementation Alignment

| Area | Status | Notes |
|------|--------|-------|
| Incident ingestion (A2A) | Aligned | `POST /a2a/work-item/process` + background processing |
| Incident ingestion (cron poller) | Aligned | `cron/snow_poller.py` |
| Pre-triage gate | Aligned | Fail-closed, enriched skip reasons |
| TriageAgent extraction | Aligned | LLM-only, one-turn |
| DiagnosticAgent — SNOW fetch | Aligned | DIAG-SNOW-01 |
| DiagnosticAgent — GTIN resolution | Aligned | DIAG-UBERKEYS-01 (WIN + UPC fallback) |
| DiagnosticAgent — GIF API | Aligned | DIAG-API-01 (IQS GraphQL) |
| DiagnosticAgent — IQS Gold check | Aligned | DIAG-API-02 (count_filter) |
| DiagnosticAgent — Uber supplier dims | Aligned | DIAG-API-03 |
| DiagnosticAgent — Tote fit logic | Aligned | DIAG-LOGIC-01 (sorted-dimension) |
| DecisionAgent — Rule engine | Aligned | 5 rules + fallback via decision_matrix tool type, deterministic |
| DecisionAgent — RAG fallback | Aligned | DIAG-RAG-FALLBACK tool |
| ActionAgent — Ticket routing | Aligned | QRY-SNOW-02 |
| ActionAgent — Merchant email | Aligned | ACT-EMAIL-01 (SMTP relay) |
| ActionAgent — SSOT Slack post | **Partial** | Slack infrastructure ready, tool not yet wired |
| ActionAgent — iSAM update | **Partial** | Mock only (QRY-ISAM-01 returns fixed data) |
| Merchant reply loop | **Gap** | No automated re-entry after merchant email reply |
| Approval gate | Aligned | Concord workflow integrated — human-in-the-loop approval with dynamic action forms |
| ClosureAgent | Aligned | Standardized notes with tags |
| Evidence/audit trail | Aligned | Full tool status derivation, pipeline health |
| Dashboard API | Aligned | Stats, incidents, audit, run grouping |
| Token tracking | Aligned | prompt_tokens, completion_tokens, total_tokens (per-request + per-agent breakdown) |

### Priority Gaps

| Priority | Gap | Impact | Mitigation |
|----------|-----|--------|-----------|
| P1 | Merchant reply loop | Cannot complete RBK-GIF-02/03/04 flows that depend on merchant confirmation | Currently falls through to MERCHANT_OUTREACH (email + set Pending) |
| P2 | Slack #ssot-gif tool | Cannot post Gold dimension update requests automatically | Manual post by associate |
| P2 | iSAM real API | Cannot update supplier dimensions programmatically | Mock returns fixed email; real updates done manually |
