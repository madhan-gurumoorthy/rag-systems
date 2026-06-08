"""Pydantic models for ``pack.yaml`` — the top-level SOP pack manifest.

These models define the schema for the largest of the three pack
config files.  Loaded and validated by ``agent_factory.pack_loader``.

The split mirrors the YAML file boundary: ``pack.yaml`` here,
``tools.yaml`` in :mod:`agent_factory.pack_models.tools`,
``policy.yaml`` in :mod:`agent_factory.pack_models.policy`.

Back-compat
-----------
All symbols are re-exported from :mod:`agent_factory.pack_models`
(the package ``__init__``) so existing imports such as
``from agent_factory.pack_models import PackConfig`` keep working
unchanged.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PipelineAgentSpec(BaseModel):
    """Specification for one agent in a pipeline (from pack.yaml)."""
    name: str
    role: str = ""
    prompt_file: str = ""
    tools: list[str] = Field(default_factory=list)


class PipelineSpec(BaseModel):
    """A named pipeline (e.g. incident, retrieval) in a pack."""
    type: str = "selector"  # selector | round_robin
    agents: list[PipelineAgentSpec] = Field(default_factory=list)
    max_turns: int = 25
    termination_agent: str = ""
    selector_prompt: str = ""


class RuntimeConfig(BaseModel):
    """Pack-declared entry points resolved via importlib at load time.

    Each entry-point value is a ``"<module>:<attr>"`` reference. Empty
    means the pack opts out of that hook (e.g. eval-only packs skip
    ``graph_builder``).

    * ``graph_builder(pack, work_item_store=..., checkpointer=...)`` → compiled LangGraph.
    * ``state_schema`` → TypedDict subclass used as the LangGraph state.
    * ``state_factory(session_id=..., agent_id=..., ...)`` → initial state dict.

    ``response_budget_seconds`` (optional) overrides the framework
    default wall-clock budget for ``POST /a2a/work-item/process``.
    When unset, the runtime reads
    ``[default.work_item_runtime].RESPONSE_BUDGET_SECONDS`` from
    secrets.toml and falls back to ``180.0`` if neither is configured.
    """
    graph_builder: str = ""
    state_schema: str = ""
    state_factory: str = ""
    response_budget_seconds: Optional[float] = None

    @field_validator("graph_builder", "state_schema", "state_factory")
    @classmethod
    def _validate_entry_point(cls, v: str) -> str:
        if not v:
            return v
        module_part, sep, attr_part = v.partition(":")
        if not sep or not module_part.strip() or not attr_part.strip():
            raise ValueError(
                f"Runtime entry-point '{v}' must be '<module>:<attribute>' "
                f"with both halves non-empty."
            )
        return v

    @field_validator("response_budget_seconds")
    @classmethod
    def _validate_response_budget(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        if v <= 0:
            raise ValueError("response_budget_seconds must be > 0")
        return float(v)


class ModelConfig(BaseModel):
    """LLM model configuration — drives build_model_client() from pack.yaml.

    When present, the builder uses these values instead of the global
    config defaults.  This allows each pack to target a different model,
    provider, temperature, etc.

    Supported providers:
      - azure_openai (default): Uses AzureOpenAIChatCompletionClient
      - openai: Uses OpenAIChatCompletionClient
      - stub: Returns a no-op client (for testing / offline packs)
    """
    provider: str = "azure_openai"  # azure_openai | openai | stub
    model: str = ""                 # e.g. "gpt-4o", overrides LIGHTRAG_MODEL
    deployment: str = ""            # Azure deployment name (defaults to model)
    api_version: str = ""           # Azure API version override
    endpoint: str = ""              # Azure endpoint override
    max_tokens: int = 4096
    temperature: float = 0.1
    extra_params: dict[str, Any] = Field(default_factory=dict)


class RulesEngineConfig(BaseModel):
    """Configuration for the pluggable Python decision engine.

    Allows each pack to point at its own rules module.
    """
    module_path: str = ""       # dotted path to the pack's rules module
    apply_function: str = "apply_decision_matrix"  # entry point function name


class RAGConfig(BaseModel):
    """RAG fallback configuration — so the RAG tool reads domain/card info from the pack."""
    domain: str = ""            # e.g. "modular-planning-execution"
    rag_query_prefix: str = ""  # prefix for RAG queries
    prompt_template: str = ""   # optional override for the RAG prompt


class PreTriageConfig(BaseModel):
    """Pre-triage gate — fast validation BEFORE the LLM pipeline.

    When enabled, the runtime resolves the upstream payload (either
    from ``state["domain_payload"]`` or by calling ``fetch_tool``) and
    checks ``assignment_groups`` / ``keywords`` / ``categories`` against
    fields in that payload.  Work items that don't match are recorded
    as ``skipped`` — zero LLM cost.

    Pack-agnostic: ``fetch_tool`` names the tool ID that retrieves the
    payload, ``fetch_param`` names the kwarg that carries
    ``external_ref`` (defaults to ``"external_ref"``), and
    ``payload_field_prefix`` lets a source-system that namespaces its
    fields (e.g. SNOW prefixes columns with ``incident_``) be probed
    without changing the framework code.  ``external_id_keys`` lists
    the payload keys, in order, to read the upstream record id from.
    """
    enabled: bool = False
    fetch_tool: str = ""
    fetch_param: str = "external_ref"
    payload_field_prefix: str = ""
    external_id_keys: list[str] = Field(
        default_factory=lambda: ["external_id"],
        description="Payload keys to try in order when extracting the upstream record id.",
    )
    assignment_groups: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    # Groups that indicate "already routed" — skip with a friendly reason
    routed_groups: dict[str, str] = Field(
        default_factory=dict,
        description="Map assignment_group substring → display label for skip reason.",
    )
    # Keywords that trigger Slack thread creation before triage
    slack_notification_keywords: list[str] = Field(
        default_factory=list,
        description="If any keyword matches short_desc, start a Slack thread early.",
    )


class DisplayConfig(BaseModel):
    """Human-readable display names for tools and outcome codes.

    Used by the runtime to render Slack summaries and audit logs.
    If a tool or outcome is not listed, the runtime falls back to
    the raw tool_id or outcome code.
    """
    tool_names: dict[str, str] = Field(
        default_factory=dict,
        description="Map tool_id (lowercase, underscores) → human label.",
    )
    outcome_labels: dict[str, str] = Field(
        default_factory=dict,
        description="Map OUTCOME_CODE → human label.",
    )


class ResolutionStatusConfig(BaseModel):
    """Pack-specific closure status codes and extraction rules.

    The runtime uses ``closure_pattern`` to parse the ClosureAgent's
    output and ``statuses`` to validate / map the extracted status.
    """
    statuses: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Map status_code → description.  Only codes listed here "
            "are accepted as valid closure outcomes."
        ),
    )
    closure_pattern: str = Field(
        default=r"^[\s\-\*>#]*\**\s*status:\s*\**\s*(.+?)[\s\*]*$",
        description="Regex pattern (IGNORECASE) to extract status from closure text.",
    )
    default_status: str = Field(
        default="pending_review",
        description="Fallback status when no recognised closure status is found.",
    )


class SafetyNetOverride(BaseModel):
    """Post-pipeline status override based on tool outcome.

    If a specific tool produced a specific outcome, the runtime can
    override the closure status — regardless of what the LLM said.
    This guards against LLM hallucination of status codes.
    """
    name: str
    enabled: bool = True
    tool: str                       # tool_id (lowercase), e.g. "tool_a_01"
    outcome: str                    # outcome code, e.g. "OUTCOME_X"
    override_status: str            # force this status, e.g. "pending_review"


class SafetyNetDimensionCheck(BaseModel):
    """Post-pipeline deterministic check that the LLM may have skipped.

    If dimensions were retrieved (from ``dimension_tools``) but the
    validation tool (``check_tool``) was never invoked, the runtime
    runs it deterministically and injects the result into evidence.
    """
    name: str
    enabled: bool = True
    dimension_tools: list[str] = Field(default_factory=list)
    dimension_fields: list[str] = Field(
        default_factory=lambda: ["height", "width", "depth", "weight"],
    )
    uom_fields: list[str] = Field(
        default_factory=lambda: ["dim_uom", "weight_uom"],
    )
    check_tool: str = ""            # tool ID to run (e.g. a validation tool)
    override_on_outcome: str = ""   # outcome that triggers status override


class ApprovedActionDef(BaseModel):
    """Definition of a single post-approval action.

    The runtime iterates these in order, executing each action's tool
    if the action ID is present in the ``approved_actions`` dict from
    the approval callback.

    Parameter resolution at execution time (``agent_factory.nodes.action``):

      1. Start with the static ``params`` block (deep copied).
      2. For every key listed in ``state_params``, forward
         ``state.get(key)`` as a kwarg of the same name (only when the
         state value is truthy — empty strings / None are dropped so
         the tool sees its own default).
      3. Fallback: if ``requires_external_id`` is True AND ``state_params``
         is empty, the action node forwards ``external_ref`` and
         ``external_id``.  New packs should declare ``state_params`` explicitly.
    """
    id: str                         # e.g. "add_work_notes", "send_email"
    tool: str                       # tool ID to invoke
    enabled: bool = True
    requires_external_id: bool = False
    params: dict[str, str] = Field(
        default_factory=dict,
        description="Static param overrides, e.g. {state: Pending}",
    )
    state_params: list[str] = Field(
        default_factory=list,
        description=(
            "State keys whose values are forwarded as same-name kwargs "
            "to the tool.  Use this for arbitrary domain identifiers "
            "(order_id, cr_number, etc.) so the action node stays "
            "pack-agnostic."
        ),
    )
    closure_fields: list[str] = Field(
        default_factory=list,
        description="Fields to extract from closure_notes (prefix:value lines).",
    )
    slack_success: str = ""         # Slack message on success
    slack_failure: str = ""         # Slack message on failure


class FindingsExtractorDef(BaseModel):
    """How to extract a single field from pipeline evidence for approval."""
    field: str                      # output field name (any pack-defined key)
    tool: str                       # source tool_id (lowercase)
    path: str = ""                  # dot-path in tool result JSON
    template: str = ""              # format string with {field} placeholders
    outcome_map: dict[str, str] = Field(
        default_factory=dict,
        description="Map outcome code → display value.",
    )


class VerdictActionSet(BaseModel):
    """Actions recommended for a specific verdict."""
    actions: list[str] = Field(
        default_factory=list,
        description="List of approved_action IDs to recommend for this verdict.",
    )
    previews: dict[str, str] = Field(
        default_factory=dict,
        description="Preview templates: work_notes, email, comment, status.",
    )


class ApprovalWorkflowConfig(BaseModel):
    """Pack-level approval workflow configuration.

    Replaces the hardcoded Concord findings builder in runtime.py.
    The runtime uses ``findings_extractors`` to build the findings dict
    from evidence, then ``verdict_field`` + ``verdict_actions`` to
    determine recommended actions and preview content.
    """
    enabled: bool = False
    provider: str = "concord"       # approval system identifier
    provider_display_name: str = "" # human-readable name for Slack messages (e.g. "Concord")
    findings_extractors: list[FindingsExtractorDef] = Field(default_factory=list)
    verdict_field: str = ""         # which findings field determines action set
    verdict_actions: dict[str, VerdictActionSet] = Field(default_factory=dict)
    fallback_verdict: str = ""      # verdict to use if none matched


class SlackContextField(BaseModel):
    """A single field shown in the Slack qualification message.

    Each entry adds one ``Label: value`` chip to the context line.
    The runtime tries each key in ``raw_keys`` (in order) against the
    incident's raw SNOW fields and uses the first non-empty match.
    """
    label: str                              # e.g. "Store", "Caller"
    raw_keys: list[str] = Field(default_factory=list,
        description="SNOW raw field names to try in order.")
    prefix: str = ""                        # optional prefix for the value (e.g. "#")


class SlackConfig(BaseModel):
    """Pack-level Slack notification configuration.

    Controls thread titles, client identity, and message templates
    so the generic runtime can post domain-appropriate Slack updates.
    """
    client_name: str = "agent-factory"
    client_version: str = "1.0.0"
    thread_title_template: str = "🔍 {ref_link} — Investigation"
    thread_title_fallback: str = "🔍 *{external_ref}* — Investigation"
    notify_context_fields: list[SlackContextField] = Field(default_factory=list,
        description="Extra fields shown in the qualification message context line.")


# ── Triage extraction config ─────────────────────────────────────────

class TriageFieldDef(BaseModel):
    """Definition of a structured field to extract from incident text.

    The runtime tries each name in ``aliases`` (in order), using a
    regex like ``<alias>: <value>``.  Optional flags drive parsing:

    - ``multiline``: capture across newlines until next field/section
    - ``int_value``: cast extracted value to int (None if non-numeric)
    - ``required``: include in ``missing_inputs`` when blank
    """
    name: str                             # output field name (any pack-defined key)
    aliases: list[str] = Field(default_factory=list,
        description="Labels to try in order (case-insensitive).")
    multiline: bool = False               # use multi-line capture pattern
    int_value: bool = False               # cast result to int
    required: bool = False                # include in missing_inputs if blank


class SymptomRule(BaseModel):
    """Maps short-description keywords to a symptom code."""
    symptom: str                          # output symptom code
    keywords: list[str] = Field(default_factory=list,
        description="Lowercase substrings to match in short_description.")


class TriageExtractionConfig(BaseModel):
    """Pack-level config for the triage stage.

    Lets each pack define the structured fields it expects to find in
    the incident text, plus the symptom-classification rules.  When
    ``fields`` is empty, the runtime falls back to extracting only the
    incident number — keeping a no-config pack functional.

    LLM-driven extraction
    ---------------------

    When ``use_llm`` is True, the triage node calls a fresh
    ``AzureChatOpenAI`` client and asks the LLM to extract the declared
    ``fields`` as JSON.  On any LLM failure (timeout, gateway error,
    unparsable JSON), the node falls back to the deterministic
    regex/config extraction path so a pipeline never blocks on the LLM.

      • ``llm_prompt_file``    — basename (no extension) of a pack prompt
                                  to render for the extraction call.
                                  When unset or not found in the pack,
                                  the framework's built-in default
                                  prompt is used.
      • ``llm_timeout_seconds`` — wall-clock cap on the LLM call.
                                  Failure → deterministic fallback.
    """
    fields: list[TriageFieldDef] = Field(default_factory=list)
    symptom_rules: list[SymptomRule] = Field(default_factory=list)
    default_symptom: str = "general_incident"
    description_marker: str = "--- Full Description ---"
    external_ref_pattern: str = Field(
        default="",
        description=(
            "Regex (with one capture group) matching the upstream "
            "record's human-facing identifier in the work-item text. "
            "Empty means no text-driven extraction — packs that already "
            "carry external_ref on state can leave this unset."
        ),
    )
    use_llm: bool = Field(
        default=False,
        description=(
            "When True, attempt LLM-driven extraction first and fall "
            "back to deterministic regex/config extraction on failure."
        ),
    )
    llm_prompt_file: str = Field(
        default="",
        description=(
            "Pack prompt basename (no extension) for the LLM extraction "
            "call.  When unset or missing, the framework default prompt "
            "is used."
        ),
    )
    llm_timeout_seconds: float = Field(
        default=30.0,
        description="Wall-clock cap on the LLM extraction call.",
    )


# ── Evidence field extraction config ─────────────────────────────────

class FieldExtractorRule(BaseModel):
    """Rule for extracting a value from a tool_result evidence entry.

    Matches a tool_result whose ``tool`` name matches ``tool_match``
    (case-insensitive substring or exact match), then either:
      - reads ``preview_keys`` (in order) from the parsed JSON preview
      - or maps ``outcome`` to a value via ``outcome_value_map``

    The first non-empty match wins.  ``default`` populates the field
    when no rule produces a value.
    """
    field: str                            # output field name (any pack-defined key)
    tool_match: str = ""                  # substring match against entry["tool"] (case-insensitive)
    tool_match_all: list[str] = Field(default_factory=list,
        description="ALL substrings must match (AND).")
    preview_keys: list[str] = Field(default_factory=list,
        description="Keys to try in order on the parsed JSON preview.")
    outcome_value_map: dict[str, str] = Field(default_factory=dict,
        description="Map outcome code → value (overrides preview_keys when matched).")
    default: str = ""


class EvidenceExtractionConfig(BaseModel):
    """Pack-level config for extracting fields from tool_result evidence.

    Drives the generic ``_extract_fields_from_evidence`` pass.  Each rule
    produces one field; ``defaults`` provides starting values for fields
    not produced by any rule (useful for unit-of-measure fallbacks or
    other pack-specific defaults).
    """
    rules: list[FieldExtractorRule] = Field(default_factory=list)
    defaults: dict[str, str] = Field(default_factory=dict)


# ── Decision matrix config ───────────────────────────────────────────


class DecisionRule(BaseModel):
    """A single rule in the deterministic decision matrix.

    Rules are evaluated in declared order; the first match wins.  A rule
    matches when:

      • every (key, value) pair in ``conditions`` is present in the
        observations dict (case-insensitive), AND
      • every key in ``requires_absent`` is absent (or blank) in the
        observations dict.

    The matched rule contributes ``runbook`` + ``description`` to the
    final decision payload.  ``id`` is echoed back as ``matched_rule``
    for audit logs.
    """
    id: str = ""
    conditions: dict[str, str] = Field(
        default_factory=dict,
        description="Map observation_key → expected_value (case-insensitive).",
    )
    requires_absent: list[str] = Field(
        default_factory=list,
        description="Observation keys that MUST be blank/absent for the rule to fire.",
    )
    runbook: str = ""
    description: str = ""


class DecisionFallback(BaseModel):
    """Fallback decision when no rule matches and no error-code shortcut fires."""
    runbook: str = "ESCALATE"
    description: str = "No rule matched"


class DecisionMatrixConfig(BaseModel):
    """Pack-level config for the deterministic decision node.

    Mirrors the rule-evaluation contract that ``decision_matrix`` tool
    specs already expose, but elevated to a first-class node config so
    the SOP Normalizer can emit it directly.  Each pack supplies one
    matrix; the runtime walks ``rules`` in declared order.  If any
    observation value appears in ``error_codes``, the matrix
    short-circuits to ``fallback`` with high confidence.
    """
    rules: list[DecisionRule] = Field(default_factory=list)
    fallback: DecisionFallback = Field(default_factory=DecisionFallback)
    error_codes: list[str] = Field(
        default_factory=list,
        description="Observation values that immediately trigger fallback.",
    )


# ── Closure template + post-verdict action config ────────────────────

class VerdictInferenceRule(BaseModel):
    """Maps a runbook ID/keyword to a verdict code.

    Used as a fallback when no diagnostic tool produced a verdict
    outcome directly.  The first matching rule wins.
    """
    verdict: str                          # output verdict code
    runbook_keywords: list[str] = Field(default_factory=list,
        description="Uppercase substrings checked against the runbook ID.")


class PostVerdictAction(BaseModel):
    """Tool to run after the deterministic decision but before closure.

    Used to look up data needed by closure templates (e.g. an external
    contact lookup) without requiring an extra LLM round-trip.  Only
    fires when the verdict matches and ``required_fields`` are blank in
    the extracted evidence.
    """
    name: str                             # human-readable name
    enabled: bool = True
    when_verdict: str = ""                # only run for this verdict (uppercase)
    when_field_blank: str = ""            # only run if this field is blank
    tool: str                             # tool ID to call
    param_from_field: dict[str, str] = Field(default_factory=dict,
        description="Map tool param name → field in extracted fields dict.")
    result_to_field: str = ""             # which field to populate from result
    result_keys: list[str] = Field(default_factory=list,
        description="Keys in the tool result to try in order.")


class ClosureTemplateConfig(BaseModel):
    """Pack-level config for closure rendering and verdict inference.

    The runtime uses ``verdict_field`` to read the verdict from the
    extracted evidence fields, falling back to ``verdict_inference``
    rules when blank.  The verdict then selects a Jinja2 template from
    ``template_map``; ``default_template`` is used otherwise.
    """
    verdict_field: str = "verdict"        # which evidence field carries the verdict
    template_map: dict[str, str] = Field(
        default_factory=dict,
        description="Map verdict code → Jinja2 template filename.",
    )
    default_template: str = ""            # template when no verdict matches
    verdict_inference: list[VerdictInferenceRule] = Field(default_factory=list)
    fallback_verdict: str = "ESCALATED"   # used when no rule infers a verdict
    post_verdict_actions: list[PostVerdictAction] = Field(default_factory=list)


class PackConfig(BaseModel):
    """Root schema for pack.yaml."""
    id: str
    name: str
    version: str = "1.0.0"
    description: str = ""
    owner_team: str = ""
    # A2A AgentCard projection — both optional, both pack-curated.
    # ``examples`` populates the umbrella skill's example prompts;
    # ``tags`` are appended to ``[pack_id, "chat"]`` for discovery.
    examples: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    # Default tenant_id stamped on session + event rows when no
    # `X-Tenant-Id` header is supplied.  Required for the multi-tenant
    # RLS story — empty default means callers MUST send the header.
    # Per-pack override lets ops ship a tenant identity for callers
    # that have no way to send a header (e.g. SNOW webhooks).
    tenant_id: str = ""
    default: bool = False
    decision_engine: str = "python"  # python | yaml_rules
    model: ModelConfig = Field(default_factory=ModelConfig)
    rules_engine: RulesEngineConfig = Field(default_factory=RulesEngineConfig)
    rag: RAGConfig = Field(default_factory=RAGConfig)
    pre_triage: PreTriageConfig = Field(default_factory=PreTriageConfig)
    pipelines: dict[str, PipelineSpec] = Field(default_factory=dict)

    display: DisplayConfig = Field(default_factory=DisplayConfig)
    resolution_statuses: ResolutionStatusConfig = Field(default_factory=ResolutionStatusConfig)
    safety_net_overrides: list[SafetyNetOverride] = Field(default_factory=list)
    safety_net_dimension_checks: list[SafetyNetDimensionCheck] = Field(default_factory=list)
    approved_actions: list[ApprovedActionDef] = Field(default_factory=list)
    approval_workflow: ApprovalWorkflowConfig = Field(default_factory=ApprovalWorkflowConfig)
    triage_extraction: TriageExtractionConfig = Field(default_factory=TriageExtractionConfig)
    evidence_extraction: EvidenceExtractionConfig = Field(default_factory=EvidenceExtractionConfig)
    closure_templates: ClosureTemplateConfig = Field(default_factory=ClosureTemplateConfig)
    slack: SlackConfig = Field(default_factory=SlackConfig)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)

