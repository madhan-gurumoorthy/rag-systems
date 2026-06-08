# Architecture Overview

## Design Philosophy

The Agent Factory implements a **"SOP Pack → Deployable Agent"** pattern:

1. **One pack = one domain agent** — Each SOP Pack contains all the config needed to handle a specific domain's incidents
2. **Zero domain-specific code** — The factory runtime is generic; all domain knowledge lives in YAML/JSON config
3. **Config-driven tool execution** — 15 tool types execute declaratively from YAML specs
4. **Pluggable decision engine** — YAML rules, decision matrix, or custom Python modules
5. **LangGraph topology, LangChain executor** — incident handling is a compiled LangGraph; per-agent reasoning runs on a LangChain `AgentExecutor` built fresh per request

## System Layers

```
┌──────────────────────────────────────────────────────────────┐
│  Channels: Slack, Teams, ServiceNow, A2A, REST API           │
└──────────────────────┬───────────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────────┐
│  app.py (FastAPI Gateway)                                     │
│  - /a2a/invoke, /a2a/invoke-stream      → runtime.chat        │
│  - /a2a/work-item/process                → LangGraph topology  │
│  - /a2a/approval/complete (Concord callback)                  │
│  - /webhooks/slack/events                                     │
│  - /healthz, /readyz, /api/factory/*, /api/dashboard/*       │
│  - /api/pack/info                                             │
└──────────────────────┬───────────────────────────────────────┘
                       │
            ┌──────────┴──────────────┐
            │                         │
┌───────────▼──────────┐   ┌──────────▼──────────────────────┐
│  runtime.chat         │   │  agent_factory.graph.factory     │
│  (chat path)          │   │  (incident path)                 │
│  - run_chat           │   │  Compiled LangGraph topology:    │
│  - run_chat_stream    │   │    triage → diagnostic → ...     │
│  - get_pipeline_agent │   │  Each node calls into either:    │
│    _names             │   │    • deterministic helpers, or   │
│                       │   │    • LangChainAgentBuilder for   │
│                       │   │      LLM-driven reasoning        │
└───────────┬──────────┘   └──────────┬──────────────────────┘
            │                         │
┌───────────▼─────────────────────────▼────────────────────────┐
│  LangChainAgentBuilder                                        │
│  - Reads pack.yaml pipeline config                            │
│  - Resolves the agent spec for the requested pipeline/role    │
│  - Resolves prompts from packs/<id>/prompts/ (.j2 Jinja2)    │
│  - Wraps ToolExecutor callables as LangChain StructuredTools  │
│  - Builds model client (Azure OpenAI / stub)                  │
│  - Returns a fresh langchain.agents.AgentExecutor             │
└──────────┬─────────────────────────┬─────────────────────────┘
           │                         │
┌──────────▼──────────┐   ┌─────────▼──────────┐
│  PackRegistry        │   │  ToolExecutor       │
│  - Loads packs       │   │  - 15 tool types    │
│  - Default pack      │   │  - Auth resolution  │
│  - Health reporting   │   │  - Response proc.   │
└──────────┬──────────┘   │  - Outcome rules    │
           │              └─────────┬───────────┘
┌──────────▼──────────────────────▼────────────────────────────┐
│  packs/<pack_id>/                                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│  │pack.yaml │ │tools.yaml│ │sop-ir.json│ │policy.yaml│       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘        │
│  ┌──────────────┐ ┌───────────────────────────────┐          │
│  │eval_cases.json│ │prompts/ (triage, diag, etc.) │          │
│  └──────────────┘ ┌───────────────────────────────┐          │
│  ┌──────────┐    │ nodes/ (LangGraph node fns)    │          │
│  │ graph.py │    └───────────────────────────────┘          │
│  └──────────┘                                                │
└──────────────────────────────────────────────────────────────┘
```

## Request Flow: Work Item Pipeline (LangGraph)

```
1. Caller POSTs WorkItemRequest → app.py /a2a/work-item/process
2. app.py → _run_incident_via_langgraph(pack_id, external_ref, session_id, ...)
3. Compiled LangGraph topology runs:
   a. triage node       — pre-triage gate (SNOW fetch + group/keyword/category check)
                          If skipped → log + audit_trail, route to end (zero LLM cost)
   b. evidence node     — LangChainAgentBuilder.build_single_executor(...) for the
                          diagnostic agent; AgentExecutor iterates tool-call loop,
                          collects observations
   c. decision node     — match observations → runbook card (decision_matrix +
                          optional RAG fallback)
   d. approval node     — if approval required, raise GraphInterrupt; Concord
                          approval form created; graph pauses until callback
   e. action node       — compile findings, run permitted actions
   f. closure node      — produce resolution summary with Slack Summary block
4. Safety net: if DIAG-LOGIC-01 was skipped, run tote fit check deterministically
5. LangGraph checkpointer (Postgres) persists state at every super-step
6. Slack thread updated with diagnostic summary + final status
7. If pending_review → graph stays paused; Concord callback resumes via
   /a2a/approval/complete → _handle_approval_via_langgraph
8. Response returned to caller
```

## Request Flow: Chat Pipeline (LangChain)

```
1. POST /a2a/invoke (or /a2a/invoke-stream, or Slack event)
2. app.py → runtime.chat.run_chat(query, session_id)
3. runtime.chat:
   a. Resolves pack via pack_registry
   b. LangChainAgentBuilder.build_pipeline_executor("retrieval")
      - Reads packs/<id>/pack.yaml → pipelines.retrieval (single RetrievalAgent)
      - Resolves prompt, wraps tools, builds AzureChatOpenAI model client
      - Returns AgentExecutor (max_iterations from pipeline.max_turns or 10)
   c. AgentExecutor.ainvoke({input: query, chat_history: []})
      - LLM iterates tool calls until it produces a final answer
      - Token usage captured via BaseCallbackHandler
   d. Intermediate steps adapted to TaskResult-shape shims for the
      duck-typed extract_evidence() — same evidence schema as incident path
4. Result returned: (content, team_state) where team_state carries
   _token_usage and (when non-empty) _evidence
5. App.py persists user + assistant messages to postgres_state_manager
```

## Tool Execution Flow

```
1. LLM decides to call a tool (e.g., DIAG-CHECK-API)
2. LangChain AgentExecutor invokes the StructuredTool, which calls the
   underlying coroutine produced by ToolExecutor.get_tools_for_agent()
3. ToolExecutor.execute_http_api():
   a. Render URL template with params + config values
   b. Resolve auth headers (bearer token from secrets.toml)
   c. Make HTTP request via httpx
   d. Parse response JSON
   e. Apply response processor (field_presence)
   f. Evaluate outcome_rules → observation code
   g. Return structured result to the LLM
```

## Key Design Decisions

### Why YAML Config Instead of Python Code?

- **Faster iteration**: Change a URL or query without touching Python
- **Lower barrier**: Teams can build agents without Python expertise
- **Portable**: Pack files can be generated by the SOP Normalizer
- **Auditable**: All agent behavior is visible in config files
- **Safe**: No arbitrary code execution (except python_function escape hatch)

### Why LangGraph + LangChain?

- **LangGraph** gives us an explicit, inspectable topology — nodes, edges,
  conditional routing, and a Postgres checkpointer that persists state at
  every super-step.  HITL pauses (Concord approval) are first-class via
  `GraphInterrupt`.
- **LangChain `AgentExecutor`** is the per-agent tool-call loop.
  `create_tool_calling_agent` generates the JSON-schema tool definitions
  automatically from our `ToolExecutor` callables (no per-tool adapter
  required), and `astream_events(version="v2")` powers the streaming chat
  endpoint with token-level granularity.
- **One framework end-to-end** — both the incident topology and the chat
  surface use the same model client, tool wrappers, and evidence extractor,
  so observability and security guarantees are uniform across paths.
- **Active development** — both projects are heavily invested in by the
  LangChain team and have a large ecosystem (callbacks, evaluators,
  integrations).

### Why Dynaconf for Secrets?

- TOML format is human-readable
- Environment-based overrides (dev/stage/prod)
- Nested sections for organizing credentials by system
- No code changes needed to add new credentials

## State Management

### Chat path
Per-message persistence to PostgreSQL via `storage/state_store.py`:

- Each message (user + assistant) is stored with `session_id`
- Token usage and evidence land in the `state` column
- Stateless per request — multi-turn memory is the caller's responsibility
  (planned: rehydrate `chat_history` from `postgres_state_manager.get_session_messages()`
  before invoking `runtime.chat.run_chat`)
- Optional — agent degrades gracefully without PostgreSQL

### Incident path
LangGraph checkpointer (`langgraph-checkpoint-postgres`) persists the
entire graph state at every super-step.  This is what makes the HITL
approval flow durable: the graph pauses on `GraphInterrupt`, the Concord
callback later resumes from the exact checkpoint.

## Observability

- **OpenTelemetry**: Distributed tracing for all operations
- **Structured Logging**: JSON-formatted logs with session/trace correlation
- **API Timing**: Request duration tracking for all endpoints
- **Pack Health**: `/api/factory/health` shows tool binding status
- **Token Tracking**: Per-request and per-agent LLM token usage (prompt + completion),
  captured via a LangChain `BaseCallbackHandler` shared by both paths
- **Pipeline Health**: Tool success/failure counts, partial/failed status derivation
- **Slack Threads**: Per-incident diagnostic summaries and status updates
- **Dashboard API**: Stats, trends, performance metrics, audit trail queries
