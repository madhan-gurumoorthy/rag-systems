"""Pydantic models for ``policy.yaml`` — pack-level approval and
blast-radius rules.

The smallest of the three pack config files.  Read at startup and
consulted at runtime by the approval gate and the action node.

The split mirrors the YAML file boundary: ``policy.yaml`` here,
``pack.yaml`` in :mod:`agent_factory.pack_models.pack`,
``tools.yaml`` in :mod:`agent_factory.pack_models.tools`.

Back-compat
-----------
All symbols are re-exported from :mod:`agent_factory.pack_models`
(the package ``__init__``) so existing imports such as
``from agent_factory.pack_models import PolicyConfig`` keep working
unchanged.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ApprovalPolicy(BaseModel):
    """Approval gate configuration."""
    required_for_cards: list[str] = Field(default_factory=list)
    required_for_tools: list[str] = Field(default_factory=list)
    approval_channel: str = "slack"
    timeout_minutes: int = 30
    ad_group: str = ""


class BlastRadiusPolicy(BaseModel):
    """Blast radius limits — generic key/value pairs defined per pack."""
    max_batch_size: int = 1
    limits: dict[str, int] = Field(default_factory=dict)


class PolicyConfig(BaseModel):
    """Root schema for policy.yaml."""
    approvals: ApprovalPolicy = Field(default_factory=ApprovalPolicy)
    blast_radius: BlastRadiusPolicy = Field(default_factory=BlastRadiusPolicy)
    permitted_actions: list[str] = Field(default_factory=list)
    denied_actions: list[str] = Field(default_factory=list)
    feature_flags: dict[str, bool] = Field(default_factory=dict)
