"""
Response models for mod-space-pilot API.

These models define the structure of outgoing responses from various endpoints.
They ensure consistent response format and include proper field documentation.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime


class ChatResponse(BaseModel):
    """
    Response model for chat/invoke endpoint.
    
    Purpose:
    - Standardizes chat response format
    - Includes metadata for tracing and debugging
    - Provides timing information for performance monitoring
    - Used by /a2a/invoke endpoint
    
    Fields:
    - response: The agent's response in markdown format
    - user_id: User identifier for correlation
    - session_id: Session identifier for correlation
    - conversation_id: Conversation identifier for multi-turn context
    - agent_name: Name of the agent that processed the request
    - time_taken: Processing time in seconds
    """
    response: str = Field(
        ...,
        description="Agent response in markdown format",
        example="## Options near HSR Layout\n- **Listing A** — ₹1.42 Cr…"
    )
    user_id: str = Field(
        ...,
        description="User identifier for correlation"
    )
    session_id: str = Field(
        ...,
        description="Session identifier for correlation"
    )
    conversation_id: str = Field(
        ...,
        description="Conversation identifier for multi-turn context"
    )
    agent_name: Optional[str] = Field(
        default="mod-space-pilot",
        description="Name of the agent that processed the request"
    )
    time_taken: float = Field(
        default=0.0,
        description="Processing time in seconds",
        ge=0.0
    )

    class Config:
        """Pydantic configuration"""
        json_schema_extra = {
            "example": {
                "response": "## REP Application - This application is responsible for tracking and...",
                "user_id": "user_789",
                "session_id": "sess_abc123", 
                "conversation_id": "conv_def456",
                "agent_name": "mod-space-pilot",
                "time_taken": 2.45
            }
        }


class StreamEvent(BaseModel):
    """
    Stream event model for real-time responses.
    
    Purpose:
    - Defines structure for Server-Sent Events (SSE)
    - Enables real-time streaming of agent responses
    - Supports different event types for flexible client handling
    - Used by /a2a/invoke-stream endpoint
    
    Event Types:
    - "token": Individual token/word from LLM
    - "chunk": Larger text chunk from processing
    - "log": Debug/status information
    - "progress": Processing progress updates
    - "result": Wrapped sync response body (emitted by the unified
      invoke-stream when ``kind != "chat"`` — the underlying pipeline
      runs synchronously and the response body is forwarded as one event)
    - "done": Stream completion signal
    - "error": Error information

    Fields:
    - event: Type of stream event
    - seq: Sequence number for ordering
    - ts: Timestamp in ISO format
    - data: Event-specific data payload
    """
    event: str = Field(
        ...,
        description="Event type",
        pattern="^(token|chunk|log|progress|result|done|error)$",
        example="chunk"
    )
    seq: int = Field(
        ...,
        description="Sequence number for event ordering",
        ge=0,
        example=42
    )
    ts: str = Field(
        ...,
        description="Timestamp in ISO format",
        example="2025-09-16T10:30:45.123Z"
    )
    data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Event-specific data payload",
        example={"content": "Here are some options", "tokens": 4}
    )

    class Config:
        """Pydantic configuration"""
        json_schema_extra = {
            "example": {
                "event": "chunk",
                "seq": 42,
                "ts": "2025-09-16T10:30:45.123Z",
                "data": {
                    "content": "Here are some real estate options",
                    "tokens": 6,
                    "progress": 0.75
                }
            }
        }


class AsyncTaskResponse(BaseModel):
    """
    Response model for asynchronous task creation.
    
    Purpose:
    - Returns task information for background processing
    - Enables clients to poll for task status
    - Provides task tracking capabilities
    - Used when requests are processed asynchronously
    
    Fields:
    - task_id: Unique identifier for the background task
    - status: Current task status
    - message: Human-readable status message
    - estimated_completion: Estimated completion time
    """
    task_id: str = Field(
        ...,
        description="Unique identifier for the background task"
    )
    status: str = Field(
        ...,
        description="Current task status",
        pattern="^(pending|running|completed|failed)$"
    )
    message: str = Field(
        ...,
        description="Human-readable status message"
    )
    estimated_completion: Optional[str] = Field(
        default=None,
        description="Estimated completion time in ISO format"
    )

    class Config:
        """Pydantic configuration"""
        json_schema_extra = {
            "example": {
                "task_id": "task_abc123",
                "status": "pending",
                "message": "Task queued for processing",
                "estimated_completion": "2025-09-16T10:35:00Z"
            }
        }
