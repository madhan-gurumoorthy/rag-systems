"""Pydantic models for the SOP Intermediate Representation (SOP-IR).

The SOP-IR is the machine-friendly companion to human-authored SOPs.
It captures metadata, intake requirements, diagnostic checks, decision
rules, runbooks, tool references, and guardrails in a schema that the
Agent Factory runtime can validate and execute.

Teams do NOT author this JSON manually — the SOP normalizer will
generate it.  For now the ModFlex sop-ir.json is hand-built from
existing code and docs.
"""
from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


# ── Metadata ──────────────────────────────────────────────────────────
class SOPMetadata(BaseModel):
    """Top-level identity and ownership."""
    title: str
    owner_team: str
    version: str = "1.0.0"
    systems: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


# ── Intake ────────────────────────────────────────────────────────────
class IntakeSpec(BaseModel):
    """What inputs are required before diagnostic checks can begin."""
    required_inputs: list[str] = Field(default_factory=list)


# ── Diagnostics ───────────────────────────────────────────────────────
class ObservationOutputs(BaseModel):
    """Canonical observation codes emitted by a diagnostic check."""
    observation_codes: list[str] = Field(default_factory=list)


class DiagnosticSpec(BaseModel):
    """A single diagnostic check (read-only)."""
    id: str = Field(..., pattern=r"^(DIAG|QRY)-")
    depends_on: list[str] = Field(default_factory=list)
    purpose: str = ""
    inputs: list[str] = Field(default_factory=list)
    outputs: ObservationOutputs = Field(default_factory=ObservationOutputs)


# ── Decision Rules ────────────────────────────────────────────────────
class DecisionCondition(BaseModel):
    """Conditions that must hold for a decision rule to fire.

    Matching semantics (all three must pass):

    * ``all``         — every observation code in this list must be present.
    * ``any``         — at least one code in this list must be present
                        (skipped when the list is empty).
    * ``expressions`` — every expression string must evaluate to ``True``
                        (skipped when the list is empty).

    ``expressions`` support value-based comparisons against the observations
    dict.  See :mod:`agent_factory.decision.expressions` for the full syntax.

    Example sop-ir.json snippet::

        {
          "when": {
            "all": ["API_DEGRADED"],
            "any": [],
            "expressions": ["checks.api_check.error_rate >= 0.5"]
          },
          "then_runbook": "RUNBOOK-THROTTLE-TRAFFIC"
        }
    """
    all: list[str] = Field(default_factory=list)
    any: list[str] = Field(default_factory=list)
    expressions: list[str] = Field(
        default_factory=list,
        description=(
            "Optional value-based expression conditions evaluated against the "
            "observations dict. All must be True for the rule to match. "
            "Syntax: '<field_path> <op> <literal>' or "
            "'<field_path> is_present|is_absent'. "
            "Operators: ==, !=, >, >=, <, <=, contains, startswith, endswith. "
            "Field paths support dot-notation (e.g. 'checks.api.count')."
        ),
    )


class DecisionRule(BaseModel):
    """Maps observation codes to a runbook card."""
    when: DecisionCondition
    then_runbook: str = Field(..., description="RUNBOOK-* identifier")


# ── Runbooks ──────────────────────────────────────────────────────────
class RunbookAction(BaseModel):
    """A single action step inside a runbook."""
    id: str = ""
    depends_on: list[str] = Field(default_factory=list)
    description: str = ""
    tool_id: str = ""
    params: dict[str, Any] = Field(default_factory=dict)


class RunbookVerification(BaseModel):
    """A verification step after runbook actions."""
    id: str = ""
    description: str = ""


class RunbookSpec(BaseModel):
    """A complete runbook (maps to a card like A1, A2, etc.).

    The ``tags`` dict carries domain-specific metadata populated by the
    sop-normalizer; the RAG fallback and decision engine read it at runtime.

    Convention for tags:
      - issue_tag: classification tag for the issue type
      - fix_tag:   classification tag for the fix type
      - card_id:   short card identifier (e.g. "A1", "B1")
    Any additional domain-specific tags can be added freely.
    """
    id: str
    depends_on: list[str] = Field(default_factory=list)
    name: str = ""
    description: str = ""
    card_id: str = ""  # Short ID like "A1", "B1" — derived from id if empty
    tags: dict[str, str] = Field(default_factory=dict)
    actions: list[RunbookAction] = Field(default_factory=list)
    verifications: list[RunbookVerification] = Field(default_factory=list)


# ── Tool References ───────────────────────────────────────────────────
class ToolRef(BaseModel):
    """A tool referenced by the SOP-IR (details live in tools.yaml)."""
    id: str
    description: str = ""


# ── Dependency Graph ──────────────────────────────────────────────────
class ParallelTrack(BaseModel):
    """A group of steps that can run in parallel."""
    track: str = ""
    steps: list[str] = Field(default_factory=list)


class DependencyGraph(BaseModel):
    """Execution dependency graph generated by the SOP normalizer.

    Captures which nodes depend on others, enabling the runtime to
    identify parallelizable tracks and critical paths.
    """
    edges: list[dict[str, str]] = Field(default_factory=list)
    entry_points: list[str] = Field(default_factory=list)
    exit_points: list[str] = Field(default_factory=list)
    parallel_tracks: list[ParallelTrack] = Field(default_factory=list)


# ── Guardrails ────────────────────────────────────────────────────────
class GuardrailApprovals(BaseModel):
    """Approval requirements for high-risk tools."""
    required_for_tools: list[str] = Field(default_factory=list)


class BlastRadius(BaseModel):
    """Upper bounds on scope of automated actions — generic key/value limits."""
    max_batch_size: int = 1
    limits: dict[str, int] = Field(default_factory=dict)


class Guardrails(BaseModel):
    """Pack-level guardrails."""
    permitted_actions: list[str] = Field(default_factory=list)
    approvals: GuardrailApprovals = Field(default_factory=GuardrailApprovals)
    blast_radius: BlastRadius = Field(default_factory=BlastRadius)


# ── Top-level SOP-IR ──────────────────────────────────────────────────
class SOPIR(BaseModel):
    """Complete SOP Intermediate Representation for a domain pack."""
    metadata: SOPMetadata
    intake: IntakeSpec = Field(default_factory=IntakeSpec)
    diagnostics: list[DiagnosticSpec] = Field(default_factory=list)
    decision_flowchart: str = ""  # ASCII routing diagram (DIAG→RBK)
    decision_rules: list[DecisionRule] = Field(default_factory=list)
    runbooks: list[RunbookSpec] = Field(default_factory=list)
    tools: list[ToolRef] = Field(default_factory=list)
    dependency_graph: DependencyGraph = Field(default_factory=DependencyGraph)
    guardrails: Guardrails = Field(default_factory=Guardrails)

    # ── Convenience lookups (built from runbooks) ────────────────────

    def get_card_names(self) -> dict[str, str]:
        """Return {card_id: runbook_name} from all runbooks.

        Uses ``card_id`` if set, otherwise strips the RUNBOOK- prefix from id.
        """
        result = {}
        for rb in self.runbooks:
            cid = rb.card_id or rb.id.replace("RUNBOOK-", "")
            result[cid] = rb.name or cid
        return result

    def get_card_tags(self) -> dict[str, tuple[str, str]]:
        """Return {card_id: (issue_tag, fix_tag)} from runbook tags.

        Falls back to ("", "") if tags are not populated.
        """
        result = {}
        for rb in self.runbooks:
            cid = rb.card_id or rb.id.replace("RUNBOOK-", "")
            result[cid] = (
                rb.tags.get("issue_tag", ""),
                rb.tags.get("fix_tag", ""),
            )
        return result

    def get_runbook_by_card_id(self, card_id: str) -> RunbookSpec | None:
        """Find a runbook by its short card_id (e.g. 'A1')."""
        for rb in self.runbooks:
            cid = rb.card_id or rb.id.replace("RUNBOOK-", "")
            if cid == card_id:
                return rb
        return None

    def get_domain(self) -> str:
        """Return the domain string from metadata tags, or empty."""
        # Convention: first tag is the primary domain identifier
        return self.metadata.tags[0] if self.metadata.tags else ""
