"""Request models for the Agent Factory HTTP surface.

These models define the structure of incoming requests to the public
endpoints.  They include validation rules and default values where
appropriate.

Inbound shapes
--------------

* ``ChatRequest`` — legacy chat invocation (``query: str``).
* ``InvokeRequest`` — accept-any-input model.  ``input`` may be any
  JSON-shaped value (str, dict, list, scalar).  The pre-triage node's
  :func:`normalise_inbound_state` helper extracts the canonical state
  slots (``external_ref``, ``external_id``, ``domain_payload``,
  ``work_item_text``) regardless of which shape the caller sent.
"""

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Any, Literal, Optional

# Pack ids: lowercase alphanumeric + underscores, starting with a letter
# — same shape the registry enforces.  Inbound ``agent_id`` values that
# do not match are coerced to ``None`` so they cannot flow further into
# the registry / loader path as raw caller input.
_PACK_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")

# Strict UUID shape for ``session_id`` — the dispatcher already rejects
# non-UUID values at runtime; enforcing the pattern at parse time keeps
# arbitrary strings off the HTTP surface in the first place.
_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


class ChatRequest(BaseModel):
    """
    Request model for chat/invoke endpoints.
    
    Purpose:
    - Validates incoming chat requests
    - Ensures required fields are present
    - Provides default values for optional fields
    - Used by both /a2a/invoke and /a2a/invoke-stream endpoints
    
    Note: Header values take precedence over request body values.
    If a field is provided in both header and body, the header value will be used.
    
    Fields:
    - query: The user's question or request (REQUIRED)
    - user_id: User identifier (OPTIONAL - prefer X-User-ID header)
    - session_id: Session identifier (OPTIONAL - prefer X-Session-ID header)  
    - conversation_id: Conversation identifier (OPTIONAL - prefer X-Conversation-ID header)
    - agent_name: Target agent name (OPTIONAL - defaults to "mod-space-pilot")
    
    Header Priority:
    1. X-User-ID header → request.user_id → "unknown"
    2. X-Session-ID header → request.session_id → auto-generated
    3. X-Conversation-ID header → request.conversation_id → auto-generated
    4. X-Calling-Agent header for service identification
    5. Idempotency-Key header for safe retries
    """
    query: str = Field(
        ...,
        min_length=1,
        description="User query or incident description (REQUIRED)",
        example="INC1234567 — checkout service latency spike since 14:30 UTC"
    )
    
    # These fields are optional in the body since headers take precedence
    user_id: Optional[str] = Field(
        default=None,
        description="User identifier (OPTIONAL - prefer X-User-ID header)",
        example="user_789"
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Session identifier (OPTIONAL - prefer X-Session-ID header)",
        example="sess_abc123"
    )
    conversation_id: Optional[str] = Field(
        default=None,
        description="Conversation identifier (OPTIONAL - prefer X-Conversation-ID header)",
        example="conv_def456"
    )
    agent_name: Optional[str] = Field(
        default=None,
        description="Target agent name (OPTIONAL - defaults to 'mod-space-pilot')",
        example="mod-space-pilot"
    )

    class Config:
        """Pydantic configuration"""
        json_schema_extra = {
            "example": {
                "query": "What is SG order issue?"
            },
            "description": "Minimal request with only required field. Optional fields can be provided via headers for better separation of concerns."
        }


class InvokeRequest(BaseModel):
    """Accept-any-input invocation model.

    The framework's normalisation layer (see
    :func:`agent_factory.nodes.pre_triage.normalise_inbound_state`)
    flattens ``input`` into the canonical state slots so any caller can
    POST whatever shape they have on hand — a free-form string, an
    upstream-system record dict, a list of items, etc.

    Fields
    ------
    * ``input`` — REQUIRED.  Any JSON-shaped value: ``str``, ``dict``,
      ``list``, scalar.  Dict-shaped input is treated as the
      ``domain_payload`` verbatim; non-dict input is flattened to
      ``work_item_text``.
    * ``session_id`` — OPTIONAL conversation/thread identifier.
      Falls back to the ``X-Session-ID`` header, then to a generated id.
    * ``agent_id`` — OPTIONAL target pack id.  When unset, the active
      pack from the registry is used.
    * ``kind`` — OPTIONAL hint for routing inside the framework
      (``"work_item"`` / ``"approval_callback"`` / ``"chat"``).  When
      unset, the dispatcher infers the kind from the input shape.
    * ``metadata`` — OPTIONAL free-form context (trace ids, calling-agent
      tags, etc.).  Stored on the work_item / session ``domain_data``.
    """

    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "example": {
                "input": "What are the steps to triage a checkout latency spike?",
                "session_id": "sess_abc123",
                "kind": "chat",
            },
            "description": (
                "Accept-any-input request — `input` may be a str, dict, "
                "list, or scalar.  The default example is a `kind=\"chat\"` "
                "invocation with a free-form query string.  For "
                "`kind=\"work_item\"` send the upstream record as a dict "
                "(e.g. `{\"external_ref\": \"INC52148837\", ...}`); for "
                "`kind=\"approval_callback\"` send "
                "`{\"external_ref\": \"...\", \"approved\": true, ...}`.  "
                "When `kind` is omitted the dispatcher infers it from "
                "the input shape."
            ),
        },
    )

    input: Any = Field(
        ...,
        description=(
            "Inbound payload — any JSON-shaped value (str, dict, list, "
            "scalar).  Dict-shaped input is treated as the upstream "
            "domain_payload verbatim; non-dict input is flattened into "
            "work_item_text."
        ),
    )
    session_id: Optional[str] = Field(
        default=None,
        description=(
            "Conversation/thread identifier.  Falls back to the "
            "X-Session-ID header, then to a generated id."
        ),
    )
    agent_id: Optional[str] = Field(
        default=None,
        description=(
            "Target pack id.  When unset, the active pack from the "
            "registry is used."
        ),
    )
    kind: Optional[Literal["work_item", "approval_callback", "chat"]] = Field(
        default=None,
        description=(
            "Hint for routing inside the framework.  When unset, the "
            "dispatcher infers the kind from the input shape."
        ),
    )
    metadata: Optional[dict[str, Any]] = Field(
        default=None,
        description=(
            "Free-form context (trace ids, calling-agent tags, etc.).  "
            "Stored on the work_item / session domain_data."
        ),
    )

    @field_validator("agent_id", mode="before")
    @classmethod
    def _sanitize_agent_id(cls, value: Any) -> Optional[str]:
        """Reject any ``agent_id`` that isn't a well-formed pack id.

        Returns ``None`` for empty / non-string / malformed input so the
        dispatcher falls back to the active pack from the registry.
        Returning ``None`` (rather than raising) keeps the contract that
        ``agent_id`` is optional while breaking the taint flow from the
        HTTP body into the pack loader.
        """
        if value is None:
            return None
        if not isinstance(value, str):
            return None
        candidate = value.strip()
        if not candidate or not _PACK_ID_PATTERN.match(candidate):
            return None
        return candidate

    @field_validator("session_id", mode="before")
    @classmethod
    def _sanitize_session_id(cls, value: Any) -> Optional[str]:
        """Reject any ``session_id`` that isn't a UUID.

        The dispatcher's ``_coerce_session_id`` will generate a fresh
        id when this returns ``None``, so the request still succeeds
        for callers that omit the field.
        """
        if value is None:
            return None
        if not isinstance(value, str):
            return None
        candidate = value.strip()
        if not candidate or not _UUID_PATTERN.match(candidate):
            return None
        return candidate
