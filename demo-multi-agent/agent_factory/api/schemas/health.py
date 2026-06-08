"""
Health and status models for mod-space-pilot API.

These models define the structure for health checks, readiness probes,
and system status responses used by monitoring and orchestration systems.
"""

from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from datetime import datetime


class HealthResponse(BaseModel):
    """
    Response model for health check endpoint.
    
    Purpose:
    - Provides overall service health status
    - Includes dependency health information
    - Used by /healthz endpoint
    - Enables monitoring and alerting systems
    
    Fields:
    - status: Overall health status
    - timestamp: When the health check was performed
    - rag_ready: Whether RAG system is initialized
    - postgres_ready: Whether PostgreSQL is available
    - redis_ready: Whether Redis is available
    - version: Service version information
    """
    status: str = Field(
        ...,
        description="Overall health status",
        pattern="^(healthy|unhealthy|degraded)$",
        example="healthy"
    )
    timestamp: str = Field(
        ...,
        description="Health check timestamp in ISO format",
        example="2025-09-16T10:30:45.123Z"
    )
    rag_ready: bool = Field(
        ...,
        description="Whether RAG system is initialized and ready"
    )
    postgres_ready: bool = Field(
        ...,
        description="Whether PostgreSQL database is available"
    )
    redis_ready: bool = Field(
        ...,
        description="Whether Redis cache is available"
    )
    version: Optional[str] = Field(
        default="1.0.0",
        description="Service version"
    )
    dependencies: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Detailed dependency status information"
    )

    class Config:
        """Pydantic configuration"""
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "timestamp": "2025-09-16T10:30:45.123Z",
                "rag_ready": True,
                "postgres_ready": True,
                "redis_ready": True,
                "version": "1.0.0",
                "dependencies": {
                    "lightrag": {"status": "healthy", "last_check": "2025-09-16T10:30:40Z"},
                    "postgres": {"status": "healthy", "connections": 5},
                    "redis": {"status": "healthy", "memory_usage": "45%"}
                }
            }
        }


class ReadinessResponse(BaseModel):
    """
    Response model for readiness check endpoint.
    
    Purpose:
    - Indicates if service is ready to accept traffic
    - Used by Kubernetes readiness probes
    - More strict than health checks
    - Used by /readyz endpoint
    
    Fields:
    - status: Readiness status
    - timestamp: When the readiness check was performed
    - ready: Boolean indicating if service is ready
    - blocking_dependencies: List of dependencies preventing readiness
    """
    status: str = Field(
        ...,
        description="Readiness status",
        pattern="^(ready|not_ready)$",
        example="ready"
    )
    timestamp: str = Field(
        ...,
        description="Readiness check timestamp in ISO format",
        example="2025-09-16T10:30:45.123Z"
    )
    ready: bool = Field(
        ...,
        description="Boolean indicating if service is ready to accept traffic"
    )
    blocking_dependencies: Optional[list] = Field(
        default_factory=list,
        description="List of dependencies preventing readiness"
    )
    details: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional readiness check details"
    )

    class Config:
        """Pydantic configuration"""
        json_schema_extra = {
            "example": {
                "status": "ready",
                "timestamp": "2025-09-16T10:30:45.123Z",
                "ready": True,
                "blocking_dependencies": [],
                "details": {
                    "rag_initialization_time": 12.5,
                    "database_connection_pool": "healthy"
                }
            }
        }


class MetricsResponse(BaseModel):
    """
    Response model for metrics endpoint.
    
    Purpose:
    - Provides operational metrics for monitoring
    - Includes performance and usage statistics
    - Used for dashboards and alerting
    - Optional endpoint for detailed monitoring
    
    Fields:
    - requests_total: Total number of requests processed
    - requests_per_second: Current request rate
    - average_response_time: Average response time in seconds
    - error_rate: Current error rate as percentage
    - active_connections: Number of active connections
    """
    requests_total: int = Field(
        ...,
        description="Total number of requests processed",
        ge=0
    )
    requests_per_second: float = Field(
        ...,
        description="Current request rate",
        ge=0.0
    )
    average_response_time: float = Field(
        ...,
        description="Average response time in seconds",
        ge=0.0
    )
    error_rate: float = Field(
        ...,
        description="Current error rate as percentage",
        ge=0.0,
        le=100.0
    )
    active_connections: int = Field(
        ...,
        description="Number of active connections",
        ge=0
    )
    uptime_seconds: float = Field(
        ...,
        description="Service uptime in seconds",
        ge=0.0
    )

    class Config:
        """Pydantic configuration"""
        json_schema_extra = {
            "example": {
                "requests_total": 15420,
                "requests_per_second": 12.5,
                "average_response_time": 2.34,
                "error_rate": 0.02,
                "active_connections": 8,
                "uptime_seconds": 86400.0
            }
        }
