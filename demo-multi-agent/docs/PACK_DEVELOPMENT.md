# Pack Development Guide

This guide walks you through building an SOP Pack from scratch.

## Prerequisites

- A forked copy of the agent-factory repository
- An SOP document describing your domain's incident resolution process
- Access to the APIs/databases your agent will interact with

## Step 1: Create the Pack Directory

```bash
mkdir -p packs/my_domain/prompts
touch packs/my_domain/__init__.py
```

## Step 2: Define pack.yaml

The pack configuration is the heart of your agent. It defines:

- **Identity**: Pack ID, name, version, owner
- **Model**: LLM provider and settings
- **Pipelines**: Which agents run, in what order, with which tools
- **Bot Commands**: Self-service commands for Slack/Teams

```yaml
id: my_domain
name: My Domain Incident Handler
version: 1.0.0
owner_team: MY-AD-GROUP
default: true

model:
  provider: azure_openai
  model: gpt-4o
  max_tokens: 4096
  temperature: 0.1

pipelines:
  incident:
    type: selector           # LLM picks next agent
    max_turns: 25
    termination_agent: ClosureAgent
    agents:
      - name: TriageAgent
        role: Classify and prioritize the incident
        prompt_file: triage.j2
        tools: []
      - name: DiagnosticAgent
        role: Run diagnostic checks
        prompt_file: diagnostic.j2
        tools: [DIAG-CHECK-API, DIAG-CHECK-DB]
      - name: DecisionAgent
        role: Select the appropriate runbook
        prompt_file: decision.j2
        tools: []
      - name: ActionAgent
        role: Execute runbook actions
        prompt_file: action.j2
        tools: [ACT-FIX-ISSUE, ACT-UPDATE-TICKET]
      - name: ClosureAgent
        role: Summarize and close
        prompt_file: closure.j2
        tools: []

  retrieval:
    type: round_robin        # Agents take turns
    max_turns: 10
    termination_agent: RetrievalAgent
    agents:
      - name: RetrievalAgent
        role: Answer questions from knowledge base
        prompt_file: retrieval.j2
        tools: [QRY-KNOWLEDGE-BASE]
```

### Pipeline Types

| Type | Behavior | Best For |
|------|----------|----------|
| `selector` | LLM chooses next agent dynamically | Complex workflows with conditional routing |
| `round_robin` | Agents take turns in order | Simple sequential flows |

## Step 3: Define tools.yaml

Each tool is declared with its type, parameters, auth, and response processing:

```yaml
tools:
  - id: DIAG-CHECK-API
    type: http_api
    description: Check API health
    method: GET
    url_template: "{{API_BASE_URL}}/healthz"
    auth:
      type: bearer
      token_config_key: API_AUTH_TOKEN
    params:
      - name: service_name
        type: str
        required: true
    response:
      processor: field_presence
      presence_fields: [status]
      outcome_rules:
        - when: "status"
          outcome: API_HEALTHY
        - when: ""
          outcome: API_UNREACHABLE
    risk: low
    timeout_seconds: 15
```

### Tool Naming Convention

- `DIAG-*` — Diagnostic checks (read-only)
- `QRY-*` — Query/lookup tools (read-only)
- `ACT-*` — Action tools (write operations, may need approval)

### Auth Types

| Type | Description | Required Config |
|------|-------------|-----------------|
| `none` | No authentication | — |
| `bearer` | Bearer token | `token_config_key` |
| `api_key` | Custom API key header | `token_config_key`, `header_name` |
| `basic` | HTTP Basic auth | `username_config_key`, `password_config_key` |
| `soa` | Walmart SOA signatures | — (auto-resolved) |

## Step 4: Define sop-ir.json

The SOP Intermediate Representation maps diagnostics → decision rules → runbooks:

```json
{
  "metadata": {
    "title": "My Domain SOP",
    "owner_team": "MY-AD-GROUP",
    "version": "1.0.0",
    "systems": ["api-service", "database"],
    "tags": ["my-domain"]
  },
  "diagnostics": [
    {
      "id": "DIAG-CHECK-API",
      "purpose": "Verify API is healthy",
      "outputs": {
        "observation_codes": ["API_HEALTHY", "API_UNREACHABLE"]
      }
    }
  ],
  "decision_rules": [
    {
      "when": { "all": ["API_UNREACHABLE"] },
      "then_runbook": "RUNBOOK-RESTART"
    }
  ],
  "runbooks": [
    {
      "id": "RUNBOOK-RESTART",
      "name": "Restart Service",
      "card_id": "A1",
      "actions": [
        { "id": "ACT-FIX-ISSUE", "tool_id": "ACT-FIX-ISSUE" }
      ]
    }
  ],
  "guardrails": {
    "approvals": { "required_for_tools": ["ACT-FIX-ISSUE"] },
    "blast_radius": { "max_batch_size": 1 }
  }
}
```

### Decision Rule Conditions

| Format | Meaning |
|--------|---------|
| `{"all": ["OBS_A", "OBS_B"]}` | ALL observations must be present |
| `{"any": ["OBS_A", "OBS_B"]}` | ANY observation matches |
| `{"all": ["OBS_A"], "any": ["OBS_B", "OBS_C"]}` | A AND (B OR C) |

## Step 5: Define policy.yaml

```yaml
approvals:
  required_for_cards: [A1]
  required_for_tools: [ACT-FIX-ISSUE]
  approval_channel: slack
  timeout_minutes: 30
  ad_group: MY-APPROVERS-GROUP

blast_radius:
  max_batch_size: 1
  limits:
    max_actions_per_hour: 5

feature_flags:
  enable_auto_fix: false
  dry_run_mode: true           # Start with dry_run to test safely
```

## Step 6: Write Prompts

Create one `.j2` (Jinja2) file per agent in `packs/my_domain/prompts/`:

- `triage.j2` — Incident classification
- `diagnostic.j2` — Running checks with tools
- `decision.j2` — Matching observations to runbooks
- `action.j2` — Executing fixes
- `closure.j2` — Summary generation
- `retrieval.j2` — Knowledge base Q&A

Prompts use Jinja2 templating with a sandboxed environment. Static pack context variables (tool IDs, agent names, observation codes) are injected automatically. Plain-text files (`.txt`, `.md`, `.prompt`) are also supported and pass through the renderer unchanged.

Each prompt should reference the specific tools and observation codes from your pack.

## Step 7: Add Eval Cases

```json
[
  {
    "id": "EVAL-001",
    "description": "API down should trigger restart",
    "input": "ServiceNow Incident: INC001\nShort Description: API 503",
    "expected_runbook": "RUNBOOK-RESTART",
    "expected_observations": ["API_UNREACHABLE"]
  }
]
```

## Step 8: Configure & Run

```bash
# Copy secrets template
cp agent_factory/infrastructure/secrets.toml.template agent_factory/infrastructure/secrets.toml

# Add your credentials
vi agent_factory/infrastructure/secrets.toml

# Set your pack as default
export DEFAULT_PACK_ID=my_domain

# Search for CHANGE_ME markers
grep -rn "CHANGE_ME" packs/my_domain/

# Start the agent
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

## Auto-Generate Packs

Use the **SOP Normalizer** to auto-generate pack files from an SOP document:
1. Normalize your SOP
2. Select "Factory Pack" mode
3. Download the ZIP
4. Extract into `packs/my_domain/`
5. Review and customize
