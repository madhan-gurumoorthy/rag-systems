"""Pydantic models for the three SOP-Pack config files.

This package replaces the previous monolithic ``pack_models.py`` (892
LOC) with a domain-split layout that mirrors the YAML files themselves.

Layout
------
* :mod:`agent_factory.pack_models.pack`    — ``pack.yaml`` schema
  (pipelines, agents, model config, RAG, pre-triage, safety nets,
  approval workflow, triage / evidence / decision / closure config).
* :mod:`agent_factory.pack_models.tools`   — ``tools.yaml`` schema
  (tool specs, auth, retry, response processing, output contract).
* :mod:`agent_factory.pack_models.policy`  — ``policy.yaml`` schema
  (approval gate, blast-radius limits, feature flags).

Back-compat
-----------
Every symbol is re-exported here so existing call-sites and tests that
import via ``from agent_factory.pack_models import <Model>`` keep
working unchanged.  No test edits required for the split.

Public surface re-exported below (sorted by domain).
"""
from __future__ import annotations

# ── pack.yaml schema ────────────────────────────────────────────────
from agent_factory.pack_models.pack import (  # noqa: F401
    ApprovalWorkflowConfig,
    ApprovedActionDef,
    ClosureTemplateConfig,
    DecisionFallback,
    DecisionMatrixConfig,
    DecisionRule,
    DisplayConfig,
    EvidenceExtractionConfig,
    FieldExtractorRule,
    FindingsExtractorDef,
    ModelConfig,
    PackConfig,
    PipelineAgentSpec,
    PipelineSpec,
    PostVerdictAction,
    PreTriageConfig,
    RAGConfig,
    ResolutionStatusConfig,
    RulesEngineConfig,
    RuntimeConfig,
    SafetyNetDimensionCheck,
    SafetyNetOverride,
    SlackConfig,
    SlackContextField,
    SymptomRule,
    TriageExtractionConfig,
    TriageFieldDef,
    VerdictActionSet,
    VerdictInferenceRule,
)

# ── tools.yaml schema ───────────────────────────────────────────────
from agent_factory.pack_models.tools import (  # noqa: F401
    AuthConfig,
    OutcomeRule,
    OutputContract,
    ResponseConfig,
    RetryConfig,
    ToolParam,
    ToolSpec,
    ToolsManifest,
)

# ── policy.yaml schema ──────────────────────────────────────────────
from agent_factory.pack_models.policy import (  # noqa: F401
    ApprovalPolicy,
    BlastRadiusPolicy,
    PolicyConfig,
)


__all__ = [
    # pack.yaml
    "ApprovalWorkflowConfig",
    "ApprovedActionDef",
    "ClosureTemplateConfig",
    "DecisionFallback",
    "DecisionMatrixConfig",
    "DecisionRule",
    "DisplayConfig",
    "EvidenceExtractionConfig",
    "FieldExtractorRule",
    "FindingsExtractorDef",
    "ModelConfig",
    "PackConfig",
    "PipelineAgentSpec",
    "PipelineSpec",
    "PostVerdictAction",
    "PreTriageConfig",
    "RAGConfig",
    "ResolutionStatusConfig",
    "RulesEngineConfig",
    "RuntimeConfig",
    "SafetyNetDimensionCheck",
    "SafetyNetOverride",
    "SlackConfig",
    "SlackContextField",
    "SymptomRule",
    "TriageExtractionConfig",
    "TriageFieldDef",
    "VerdictActionSet",
    "VerdictInferenceRule",
    # tools.yaml
    "AuthConfig",
    "OutcomeRule",
    "OutputContract",
    "ResponseConfig",
    "RetryConfig",
    "ToolParam",
    "ToolSpec",
    "ToolsManifest",
    # policy.yaml
    "ApprovalPolicy",
    "BlastRadiusPolicy",
    "PolicyConfig",
]
