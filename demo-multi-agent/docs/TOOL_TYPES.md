# Tool Types Reference

The Agent Factory supports 15 declarative tool types. This document provides detailed configuration reference for each.

## Common Fields (All Tool Types)

```yaml
- id: TOOL-ID               # Unique identifier (DIAG-*, QRY-*, ACT-*)
  type: http_api             # Tool type (see below)
  description: "..."         # Human-readable description (shown to LLM)
  params:                    # Parameters the LLM provides
    - name: param_name
      type: str              # str | int | float | bool
      required: true
      default: null
      description: "..."
  response:                  # Response processing config
    processor: passthrough   # See Response Processors section
    outcome_rules: [...]
    error_outcomes: {...}
  risk: low                  # low | medium | high
  requires_approval: false
  timeout_seconds: 30
```

## 1. http_api

REST API calls with full auth, response extraction, and outcome derivation.

```yaml
- id: DIAG-CHECK-API
  type: http_api
  method: GET                           # GET | POST | PUT | PATCH | DELETE
  url_template: "{{API_URL}}/endpoint/{{id}}"
  headers:
    X-Custom-Header: "{{CUSTOM_VALUE}}"
  query_params:
    page: "1"
    limit: "100"
  body_template:                        # For POST/PUT/PATCH
    key: "{{value}}"
  auth:
    type: bearer                        # none | bearer | api_key | basic | soa
    token_config_key: API_TOKEN
```

`{{KEY}}` placeholders are resolved from params first, then from `agent_factory/infrastructure/secrets.toml`.

## 2. sql_query

Parameterized SQL queries with dialect support.

```yaml
- id: QRY-GET-RECORDS
  type: sql_query
  connection: postgresql               # Config section in secrets.toml
  dialect: postgresql_async            # postgresql_async | postgresql | mssql
  query_template: >
    SELECT * FROM orders
    WHERE customer_id = '{{customer_id}}'
    AND status = '{{status}}'
    LIMIT 100
```

## 3. bigquery_query

Google BigQuery queries.

```yaml
- id: QRY-BQ-METRICS
  type: bigquery_query
  project: my-gcp-project
  dataset: analytics
  query_template: >
    SELECT date, metric_value
    FROM `{{project}}.{{dataset}}.daily_metrics`
    WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL {{days}} DAY)
```

## 4. graphql

GraphQL queries/mutations over HTTP.

```yaml
- id: QRY-GRAPHQL-USERS
  type: graphql
  graphql_endpoint: "{{GRAPHQL_URL}}/graphql"
  graphql_query: |
    query GetUser($userId: ID!) {
      user(id: $userId) {
        name
        email
        status
      }
    }
  graphql_variables:
    userId: "{{user_id}}"
  auth:
    type: bearer
    token_config_key: GRAPHQL_TOKEN
```

## 5. a2a (Agent-to-Agent)

Call another agent via the A2A protocol with trace propagation.

```yaml
- id: ACT-CALL-EXTERNAL-AGENT
  type: a2a
  target_agent_url: "{{EXTERNAL_AGENT_URL}}/a2a/invoke"
  a2a_payload_template:
    query: "{{query}}"
    agent_name: "external-agent"
  a2a_stream: false
  a2a_session_field: session_id
  auth:
    type: bearer
    token_config_key: EXTERNAL_AGENT_TOKEN
```

## 6. jira

JIRA REST API operations.

```yaml
# Search
- id: QRY-JIRA-SEARCH
  type: jira
  jira_connection: jira
  jira_operation: search
  jira_jql_template: "project = {{project}} AND status = Open"

# Create
- id: ACT-JIRA-CREATE
  type: jira
  jira_connection: jira
  jira_operation: create
  jira_project: MYPROJ
  jira_issue_type: Bug
  jira_fields_template:
    summary: "{{summary}}"
    description: "{{description}}"

# Transition
- id: ACT-JIRA-CLOSE
  type: jira
  jira_connection: jira
  jira_operation: transition
  jira_issue_key_param: ticket_id
  jira_transition_name: "Done"

# Add comment
- id: ACT-JIRA-COMMENT
  type: jira
  jira_connection: jira
  jira_operation: add_comment
  jira_issue_key_param: ticket_id
```

## 7. kafka

Kafka produce/consume with mTLS and SASL support.

```yaml
# Produce
- id: ACT-KAFKA-PRODUCE
  type: kafka
  kafka_connection: kafka
  kafka_operation: produce
  kafka_topic_template: "events.{{domain}}.actions"
  kafka_key_template: "{{incident_id}}"
  kafka_value_template:
    type: "action_taken"
    incident: "{{incident_id}}"
    action: "{{action_name}}"

# Consume
- id: QRY-KAFKA-CONSUME
  type: kafka
  kafka_connection: kafka
  kafka_operation: consume
  kafka_topic_template: "events.{{domain}}.results"
  kafka_consumer_group: "my-agent-consumer"
  kafka_max_messages: 10
```

## 8. elasticsearch

Elasticsearch/OpenSearch query DSL.

```yaml
- id: QRY-ES-SEARCH
  type: elasticsearch
  es_connection: elasticsearch
  es_index_template: "logs-{{date}}"
  es_query_template:
    query:
      bool:
        must:
          - match:
              service: "{{service_name}}"
          - range:
              "@timestamp":
                gte: "now-1h"
  es_size: 50
  es_sort:
    - "@timestamp": "desc"
  es_source_fields: ["message", "level", "service"]
```

## 9. cassandra

CQL queries against Cassandra/ScyllaDB.

```yaml
- id: QRY-CASSANDRA-LOOKUP
  type: cassandra
  cassandra_connection: cassandra
  keyspace: my_keyspace
  cql_template: >
    SELECT * FROM events
    WHERE partition_key = '{{key}}'
    AND event_time > '{{since}}'
    LIMIT 100
```

## 10. redis

Redis command execution.

```yaml
- id: QRY-REDIS-GET
  type: redis
  redis_connection: redis
  redis_command: GET
  redis_key_template: "cache:{{entity_type}}:{{entity_id}}"

- id: QRY-REDIS-HASH
  type: redis
  redis_connection: redis
  redis_command: HGETALL
  redis_key_template: "config:{{service_name}}"
```

Supported commands: GET, SET, HGETALL, HGET, LRANGE, SMEMBERS, SISMEMBER, EXISTS, DEL, TTL, INCR, EXPIRE.

## 11. batch

Run another tool in parallel for multiple parameter sets.

```yaml
- id: ACT-BATCH-RESTART
  type: batch
  batch_tool_id: ACT-RESTART-SERVICE    # Tool to run for each item
  max_concurrency: 5
  description: Restart multiple services in parallel
```

The LLM passes `items` as a JSON array of param dicts.

## 12. python_function

Escape hatch — imports and calls a Python function. Use **only** when the
behaviour you need isn't yet covered by a declarative tool type or by a
generic factory integration. Anything that ships as a `python_function` is
opaque to the SOP normalizer and the policy/observability layers, so prefer
declarative types or factory integrations whenever possible.

```yaml
- id: ACT-CUSTOM-LOGIC
  type: python_function
  import: packs.my_domain.custom_tools:run_custom_action
  description: Custom domain-specific action
  params:
    - { name: incident_number, type: str, required: true }
    - { name: payload,         type: dict, required: true }
```

### Import path

Either form works:

- `"module.path:function_name"` (preferred — unambiguous)
- `"module.path.function_name"` (legacy — last dot is treated as the split)

Resolution happens once at `ToolExecutor` construction via
`agent_factory.tools.executor.resolve_python_function`. A missing module
logs a warning and disables the tool; a missing attribute logs an error.

### Function contract

The executor wrapper (`_debug_pyfn_wrapper` in
`agent_factory/tools/executor.py`) supports **both sync and async**
callables — it inspects with `asyncio.iscoroutinefunction` and awaits only
when needed. Your function MUST:

1. **Accept keyword arguments** matching the `params` declared in
   `tools.yaml`. The LLM/runtime calls it as `fn(**tool_input)`.
2. **Return a JSON-serialisable value** — typically a `dict[str, Any]`.
   The return value flows straight into the response-processor pipeline
   (`response.processor`, `outcome_rules`, etc.) just like any other tool.
3. **Raise on failure** rather than returning ad-hoc error sentinels —
   the executor logs the exception with the tool ID and the error
   propagates through the standard error-outcome path.
4. **Be deterministic and side-effect-aware** — `risk` / `requires_approval`
   in `tools.yaml` still gate the tool, but the body of the function is
   not introspected, so honour the declared risk level.

Example pack-side function:

```python
# packs/my_domain/custom_tools.py
from agent_factory.integrations.email import send_email

def run_custom_action(incident_number: str, payload: dict) -> dict:
    result = send_email(
        to_address=payload["to"],
        subject=payload["subject"],
        body_html=payload["html"],
    )
    return {
        "incident_number": incident_number,
        "sent": result["success"],
        "error": result.get("error"),
    }
```

### Prefer factory integrations

Before writing a `python_function` shim, check
`agent_factory/integrations/` — common plumbing (SMTP, Concord HITL, iSAM
mock lookup, …) already lives there and exposes pack-agnostic helpers.
A typical pack tool is then a 3-line wrapper that injects pack-specific
values (e.g. a fixed merchant email, a Concord entry-point name) and
delegates to the factory function — keeping the pack's Python surface
under the ≤200-LOC budget.

## 13. threshold_check

Compare numeric values against configurable thresholds with unit conversion.

```yaml
- id: DIAG-LOGIC-01
  type: threshold_check
  description: Validate item dimensions against tote constraints
  thresholds:
    - "height=10.5"
    - "width=13.0"
    - "depth=20.5"
  weight_threshold: 34.55
  weight_param: "weight"
  dim_uom_param: "dim_uom"
  weight_uom_param: "weight_uom"
  dim_conversions:
    CM: 0.3937
    MM: 0.03937
  weight_conversions:
    KG: 2.205
    G: 0.002205
    OZ: 0.0625
  exceeds_outcome: "OVERSIZED"
  within_outcome: "FITS_TOTE"
```

Sorts item dimensions smallest-to-largest and compares pairwise against sorted thresholds. Unit conversions are applied automatically.

## 14. decision_matrix

Deterministic first-match rule engine for mapping observation codes to runbook cards.

```yaml
- id: DIAG-DECISION-MATRIX
  type: decision_matrix
  description: Map diagnostic observations to runbook
  decision_rules:
    - id: "RULE-1"
      conditions:
        DIAG-LOGIC-01: "FITS_TOTE"
      runbook: "RBK-01"
      description: "Item fits → auto-route"
    - id: "RULE-2"
      conditions:
        DIAG-LOGIC-01: "OVERSIZED"
      requires_absent: ["merchant_response"]
      runbook: "RBK-02"
      description: "Oversized, no merchant response → outreach"
  decision_fallback:
    runbook: "RBK-99"
    description: "No rule matched → escalate"
  decision_error_codes:
    - "API_ERROR"
    - "PARSE_FAILURE"
```

Rules are evaluated in order — first match wins. `requires_absent` constrains a rule to only match when the listed keys are NOT present in observations. Error codes trigger immediate escalation before rule evaluation.

## 15. servicenow

ServiceNow REST Table API operations with RSA-SHA256 signed proxy authentication.

```yaml
- id: DIAG-SNOW-01
  type: servicenow
  snow_connection: "servicenow_proxy"
  snow_operation: "get_by_number"       # get_by_number | search | update
  snow_number_param: "incident_number"
  params:
    - name: incident_number
      type: str
      required: true
  response:
    processor: passthrough
    outcome_rules:
      - when: "incident_number"
        outcome: "INCIDENT_MATCHED"
      - when: ""
        outcome: "INCIDENT_NOT_MATCHED"
    error_outcomes:
      "404": "INCIDENT_NOT_FOUND"
      "500": "SNOW_ERROR"
```

Supported operations: `get_by_number` (fetch single incident), `search` (encoded query), `update` (patch fields by sys_id).

## Response Processors

| Processor | Description | Config |
|-----------|-------------|--------|
| `passthrough` | Return raw response | — |
| `field_presence` | Check fields exist | `presence_fields: [field1, field2]` |
| `count_filter` | Count matching records | `array_path`, `filter_field`, `filter_values` |
| `priority_match` | Find highest-priority status | `priority_field`, `priority_order: [high, med, low]` |
| `any_match` | Check if any record matches | `filter_field`, `filter_values` |
| `first_field` | Extract field from first row | `extract_field: field_name` |

### Outcome Rules

```yaml
outcome_rules:
  - when: "count > 0"        # Numeric comparison
    outcome: HAS_RECORDS
  - when: "field_name"        # Truthy check
    outcome: FIELD_EXISTS
  - when: "status IN [active, pending]"  # Membership
    outcome: STATUS_VALID
  - when: ""                  # Default/fallback
    outcome: NO_MATCH
```
