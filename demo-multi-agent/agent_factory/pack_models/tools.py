"""Pydantic models for ``tools.yaml`` — the declarative tool manifest.

Each ``ToolSpec`` defines one tool the agent can invoke: HTTP API,
SQL query, Kafka, RAG, etc.  The runtime's ``ToolExecutor`` walks the
manifest at startup to register handlers.

The split mirrors the YAML file boundary: ``tools.yaml`` here,
``pack.yaml`` in :mod:`agent_factory.pack_models.pack`,
``policy.yaml`` in :mod:`agent_factory.pack_models.policy`.

Back-compat
-----------
All symbols are re-exported from :mod:`agent_factory.pack_models`
(the package ``__init__``) so existing imports such as
``from agent_factory.pack_models import ToolSpec`` keep working
unchanged.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OutputContract(BaseModel):
    """Expected output contract for a tool."""
    observation_field: str = ""
    schema_ref: str = ""


class AuthConfig(BaseModel):
    """Authentication strategy for declarative tools (http_api, sql_query, etc.).

    Supports multiple auth types. Credentials are read from Dynaconf
    config (configs/secrets.toml) at runtime — never stored in pack YAML.

    Auth types:
      - none: No auth (public APIs)
      - bearer: Authorization: Bearer <token>
      - api_key: Custom header with API key
      - basic: HTTP Basic auth (username:password)
      - soa: Walmart SOA-signed requests (via agents.client)
    """
    type: str = "none"              # none | bearer | api_key | basic | soa
    header_name: str = ""           # custom header name (for api_key type)
    token_config_key: str = ""      # config path for token/key value
    username_config_key: str = ""   # config path for username (basic auth)
    password_config_key: str = ""   # config path for password (basic auth)
    extra_headers: dict[str, str] = Field(default_factory=dict)


class RetryConfig(BaseModel):
    """Retry and exponential-backoff strategy for HTTP-based tools.

    Applied to http_api, graphql, and a2a tool types.  Each attempt uses
    ``delay = min(backoff_seconds * backoff_multiplier^n, max_backoff_seconds)``.
    Network-level errors (timeouts, connection resets) are always retried;
    HTTP status errors are only retried when the status code is in
    ``retryable_status_codes``.

    Example tools.yaml snippet::

        retry:
          max_attempts: 3
          backoff_seconds: 1.0
          backoff_multiplier: 2.0
          max_backoff_seconds: 10.0
          retryable_status_codes: [429, 502, 503, 504]
    """
    max_attempts: int = Field(1, ge=1, le=10,
        description="Total number of attempts including the first (1 = no retry).")
    backoff_seconds: float = Field(1.0, ge=0.0,
        description="Initial delay before the first retry, in seconds.")
    backoff_multiplier: float = Field(2.0, ge=1.0,
        description="Multiplier applied to the delay after each failed attempt.")
    max_backoff_seconds: float = Field(30.0, ge=0.0,
        description="Upper cap on the computed backoff delay.")
    retryable_status_codes: list[int] = Field(
        default_factory=lambda: [429, 502, 503, 504],
        description="HTTP status codes that trigger a retry (transient server errors).",
    )


class ToolParam(BaseModel):
    """Parameter definition for a declarative tool."""
    name: str
    type: str = "str"               # str | int | float | bool
    required: bool = True
    default: Any = None
    description: str = ""


class OutcomeRule(BaseModel):
    """A single rule mapping a condition to an outcome code.

    Conditions use a simple expression language:
      - "field_name"                    → truthy check
      - "field1 OR field2"              → any truthy
      - "field1 AND field2"             → all truthy
      - "count > 1"                     → numeric comparison
      - "count == 0"                    → equality
      - "field IN [val1, val2]"         → membership
      - ""  (empty)                     → default/fallback rule
    """
    when: str = ""
    outcome: str


class ResponseConfig(BaseModel):
    """Response extraction, transformation, and outcome derivation for declarative tools.

    The factory processes responses through this pipeline:
      1. Extract raw data from the API/DB response
      2. Apply a built-in processor to derive structured observations
      3. Evaluate outcome_rules to produce an outcome code
      4. On HTTP errors, use error_outcomes instead

    Built-in processors:
      - passthrough: Return raw response data as-is
      - field_presence: Check if specified fields exist in response
      - count_filter: Count array records matching a filter, emit count-based outcomes
      - priority_match: Find highest-priority status from array records
      - any_match: Check if any record matches a condition
      - first_field: Extract a specific field from the first record
    """
    # Processor selection
    processor: str = "passthrough"

    # Field extraction (works with all processors)
    # Maps response field names → normalized names (pipe = fallback chain)
    # e.g. {"footage": "footage|totalFootage"} → tries "footage", falls back to "totalFootage"
    extract_fields: dict[str, str] = Field(default_factory=dict)

    # For field_presence: which fields to check for existence
    presence_fields: list[str] = Field(default_factory=list)

    # For count_filter: filter array records and count matches
    array_path: str = ""                # JSONPath to array (e.g. "result" or "data.records")
    filter_field: str = ""              # field to filter on (single-field mode)
    filter_values: list[str] = Field(default_factory=list)  # accepted values (case-insensitive)
    # Multi-field AND filter: ALL conditions must match for a record to count.
    # Each entry is "field_name=value" (case-insensitive comparison).
    # Example: ["informationProviderTypeCode=GOLD", "informationProviderId=GOLD"]
    filter_fields: list[str] = Field(default_factory=list)

    # For priority_match: find highest-priority status
    priority_field: str = ""            # field containing status value
    priority_order: list[str] = Field(default_factory=list)  # highest to lowest

    # For first_field: extract specific field from first row
    extract_field: str = ""

    # Outcome derivation
    outcome_rules: list[OutcomeRule] = Field(default_factory=list)

    # HTTP error → outcome mapping (status code as string key, plus "default")
    error_outcomes: dict[str, str] = Field(default_factory=dict)

    # Include raw response data in output (useful for debugging)
    include_raw: bool = False


class ToolSpec(BaseModel):
    """Specification for a single tool in tools.yaml.

    Tool types:
      - python_function: imports and calls a Python function (escape hatch)
      - http_api: declarative HTTP API call with auth, extraction, outcomes
      - sql_query: declarative SQL query (MS SQL, PostgreSQL, Azure SQL)
      - bigquery_query: declarative BigQuery query
      - a2a: agent-to-agent call with trace propagation and session mgmt
      - graphql: declarative GraphQL query/mutation
      - cassandra: declarative CQL query against Cassandra/ScyllaDB
      - redis: declarative Redis command execution
      - jira: declarative JIRA operations (search, create, update, transition)
      - kafka: declarative Kafka produce/consume
      - elasticsearch: declarative Elasticsearch/OpenSearch queries
      - batch: runs another tool in parallel for multiple parameter sets
    """
    id: str
    type: str = "python_function"
    description: str = ""

    # A2A AgentCard projection — opt-in.  When ``expose_as_skill`` is
    # True, the card builder emits a dedicated ``AgentSkill`` for this
    # tool so external clients can discover and target it by id.
    expose_as_skill: bool = False
    skill_examples: list[str] = Field(default_factory=list)
    skill_tags: list[str] = Field(default_factory=list)

    # python_function fields
    import_path: str = Field("", alias="import")
    function_ref: str = ""

    # Parameter definitions (declarative tools)
    params: list[ToolParam] = Field(default_factory=list)

    # Auth configuration (http_api, sql_query, a2a, graphql)
    auth: AuthConfig = Field(default_factory=AuthConfig)

    # Response processing (all declarative types)
    response: ResponseConfig = Field(default_factory=ResponseConfig)

    # Retry / backoff configuration (http_api, graphql, a2a)
    retry: RetryConfig = Field(default_factory=RetryConfig)

    # http_api fields
    method: str = "GET"
    url_template: str = ""
    headers: dict[str, str] = Field(default_factory=dict)
    body_template: dict[str, Any] = Field(default_factory=dict)
    query_params: dict[str, str] = Field(default_factory=dict)
    # Body serialisation format.  "json_rpc" wraps body_template in a
    # JSON-RPC 2.0 envelope so any JSON-RPC service (including MCP servers)
    # can be called as a plain http_api tool — no extra tool type needed.
    body_format: str = "json"   # json | json_rpc
    json_rpc_method: str = ""   # JSON-RPC method name; defaults to tool id
    # Method fallback: if the primary method returns one of the listed status
    # codes, retry with the next method in the list (e.g. GET→POST on 405/400).
    fallback_methods: list[str] = Field(default_factory=list)   # e.g. ["POST"]
    fallback_on_status_codes: list[int] = Field(default_factory=list)  # e.g. [400, 405]

    # sql_query fields
    connection: str = ""
    dialect: str = "mssql"          # mssql | postgresql | postgresql_async | azure_sql
    query_template: str = ""

    # bigquery_query fields
    project: str = ""
    dataset: str = ""

    # a2a (agent-to-agent) fields
    target_agent_url: str = ""      # URL template: "{{AGENT_X_URL}}/a2a/invoke"
    a2a_payload_template: dict[str, Any] = Field(default_factory=dict)
    a2a_stream: bool = False        # use streaming invoke
    a2a_session_field: str = ""     # param name for session_id

    # graphql fields
    graphql_endpoint: str = ""      # URL template
    graphql_query: str = ""         # GraphQL query/mutation string
    graphql_variables: dict[str, str] = Field(default_factory=dict)  # variable → param mapping

    # cassandra fields
    cassandra_connection: str = ""  # config key for cluster connection
    keyspace: str = ""
    cql_template: str = ""          # CQL query template

    # redis fields
    redis_connection: str = ""      # config key for Redis connection
    redis_command: str = ""         # e.g. "GET", "HGETALL", "LRANGE"
    redis_key_template: str = ""    # key template with {{params}}
    redis_args: list[str] = Field(default_factory=list)  # additional arg templates

    # jira fields
    jira_connection: str = ""       # config key for JIRA connection
    jira_operation: str = "search"  # search | create | update | transition | add_comment | get
    jira_jql_template: str = ""     # JQL query template for search
    jira_project: str = ""          # project key for create
    jira_issue_type: str = "Task"   # Story | Task | Bug | Epic | Sub-task
    jira_fields_template: dict[str, Any] = Field(default_factory=dict)  # field templates
    jira_transition_name: str = ""  # transition name for status changes
    jira_issue_key_param: str = ""  # param name holding the issue key

    # kafka fields
    kafka_connection: str = ""      # config key for Kafka broker connection
    kafka_operation: str = "produce"  # produce | consume
    kafka_topic_template: str = ""  # topic name template
    kafka_key_template: str = ""    # message key template (optional)
    kafka_value_template: dict[str, Any] = Field(default_factory=dict)  # message value
    kafka_consumer_group: str = ""  # consumer group ID for consume
    kafka_max_messages: int = 10    # max messages to consume
    kafka_schema_registry: str = "" # config key for schema registry (optional)

    # elasticsearch fields
    es_connection: str = ""         # config key for ES connection
    es_index_template: str = ""     # index name/pattern template
    es_query_template: dict[str, Any] = Field(default_factory=dict)  # ES query DSL
    es_size: int = 100              # max results
    es_sort: list[dict[str, Any]] = Field(default_factory=list)  # sort clauses
    es_source_fields: list[str] = Field(default_factory=list)  # _source filter

    # threshold_check fields — generic "do values exceed limits?" with unit conversion
    # Each entry: "param_name=limit" e.g. ["height=10.5", "width=13.0", "depth=20.5"]
    thresholds: list[str] = Field(default_factory=list)
    # Weight threshold (separate because it uses a different UOM conversion)
    weight_threshold: float = 0.0
    # Unit conversion tables: map source UOM → multiplier to convert to the base unit
    # e.g. {"CM": 0.3937, "MM": 0.03937} converts to inches
    dim_conversions: dict[str, float] = Field(default_factory=dict)
    weight_conversions: dict[str, float] = Field(default_factory=dict)
    # Which params carry the UOM codes (defaults: dim_uom, weight_uom)
    dim_uom_param: str = "dim_uom"
    weight_uom_param: str = "weight_uom"
    weight_param: str = "weight"
    # Labels for the output (pack-defined outcome codes)
    exceeds_outcome: str = "EXCEEDS"
    within_outcome: str = "WITHIN"

    # decision_matrix fields — generic first-match rule evaluation
    # Each rule: {conditions: {key: value}, requires_absent: [keys], runbook: "ID", description: "..."}
    decision_rules: list[dict[str, Any]] = Field(default_factory=list)
    decision_fallback: dict[str, str] = Field(default_factory=dict)
    # Observation values that trigger immediate fallback (e.g. ["API_ERROR", "PARSE_FAILURE"])
    decision_error_codes: list[str] = Field(default_factory=list)

    # batch fields
    batch_tool_id: str = ""         # tool to run in parallel
    max_concurrency: int = 10

    # Shared metadata
    risk: str = "low"  # low | medium | high
    requires_approval: bool = False
    output_contract: OutputContract = Field(default_factory=OutputContract)
    timeout_seconds: int = Field(default=30, ge=1, le=300)

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("timeout_seconds", mode="before")
    @classmethod
    def _clamp_timeout(cls, v: Any) -> int:
        """Clamp timeout_seconds to the valid range [1, 300].

        Silently correcting out-of-range values avoids hard pack-load failures
        for packs that may specify 0 or very large timeouts, while still
        enforcing a safe upper bound of 5 minutes to prevent runaway requests.
        """
        try:
            v = int(v)
        except (TypeError, ValueError):
            return 30
        return max(1, min(v, 300))


class ToolsManifest(BaseModel):
    """Root schema for tools.yaml."""
    tools: list[ToolSpec] = Field(default_factory=list)

