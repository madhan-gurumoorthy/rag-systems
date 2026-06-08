"""
Standardized error handler for agent card compliance.
"""
import logging
import uuid
from enum import Enum
from typing import Any, Dict, Optional

from fastapi import HTTPException
from fastapi.responses import JSONResponse

from agent_factory.common.tracing import get_current_trace_info

_logger = logging.getLogger("agent_factory.errors")


class AgentErrorType(Enum):
    """Standard error types as defined in agent card"""
    VALIDATION_ERROR = "VALIDATION_ERROR"
    AUTH_FAILED = "AUTH_FAILED"
    RATE_LIMIT = "RATE_LIMIT"
    DOWNSTREAM_TIMEOUT = "DOWNSTREAM_TIMEOUT"
    DOWNSTREAM_4XX = "DOWNSTREAM_4XX"
    DOWNSTREAM_5XX = "DOWNSTREAM_5XX"
    INTERNAL = "INTERNAL"


class AgentError(Exception):
    """Standard agent error with proper formatting"""
    
    def __init__(
        self,
        error_type: AgentErrorType,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        status_code: int = 500,
        request_id: Optional[str] = None,
        trace_id: Optional[str] = None
    ):
        self.error_type = error_type
        self.message = message
        self.details = details or {}
        self.status_code = status_code
        self.request_id = request_id
        self.trace_id = trace_id
        super().__init__(message)


def create_error_response(
    error_type: AgentErrorType,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    status_code: int = 500,
    request_id: Optional[str] = None,
    trace_id: Optional[str] = None
) -> JSONResponse:
    """Create standardized error response following agent card schema"""
    
    # Get trace context if not provided
    if not trace_id or not request_id:
        trace_info = get_current_trace_info()
        if not trace_id:
            trace_id = trace_info.get("trace_id", str(uuid.uuid4()))
        if not request_id:
            request_id = trace_info.get("span_id", str(uuid.uuid4()))
    
    error_response = {
        "ok": False,
        "error": {
            "type": error_type.value,
            "message": message,
            "details": details or {}
        },
        "correlation": {
            "request_id": request_id,
            "trace_id": trace_id
        }
    }
    
    return JSONResponse(
        status_code=status_code,
        content=error_response
    )


def handle_validation_error(message: str, details: Optional[Dict[str, Any]] = None) -> JSONResponse:
    """Handle validation errors (400)"""
    return create_error_response(
        AgentErrorType.VALIDATION_ERROR,
        message,
        details,
        status_code=400
    )


def handle_auth_error(message: str = "Authentication failed", details: Optional[Dict[str, Any]] = None) -> JSONResponse:
    """Handle authentication errors (401)"""
    return create_error_response(
        AgentErrorType.AUTH_FAILED,
        message,
        details,
        status_code=401
    )


def handle_rate_limit_error(message: str = "Rate limit exceeded", details: Optional[Dict[str, Any]] = None) -> JSONResponse:
    """Handle rate limit errors (429)"""
    return create_error_response(
        AgentErrorType.RATE_LIMIT,
        message,
        details,
        status_code=429
    )


def handle_downstream_timeout(message: str, details: Optional[Dict[str, Any]] = None) -> JSONResponse:
    """Handle downstream timeout errors (504)"""
    return create_error_response(
        AgentErrorType.DOWNSTREAM_TIMEOUT,
        message,
        details,
        status_code=504
    )


def handle_downstream_4xx(message: str, details: Optional[Dict[str, Any]] = None) -> JSONResponse:
    """Handle downstream 4xx errors (502)"""
    return create_error_response(
        AgentErrorType.DOWNSTREAM_4XX,
        message,
        details,
        status_code=502
    )


def handle_downstream_5xx(message: str, details: Optional[Dict[str, Any]] = None) -> JSONResponse:
    """Handle downstream 5xx errors (502)"""
    return create_error_response(
        AgentErrorType.DOWNSTREAM_5XX,
        message,
        details,
        status_code=502
    )


def handle_internal_error(
    message: str = "Internal server error",
    details: Optional[Dict[str, Any]] = None,
    original_exception: Optional[Exception] = None
) -> JSONResponse:
    """Handle internal server errors (500).

    The original exception is logged at ERROR with full traceback so
    operators retain diagnostic context.  The response body NEVER
    includes ``exception_type`` / ``exception_message`` — those reprs
    can carry DSN fragments, file paths, or secrets that downstream
    code embedded in the exception, and 500s must not become a
    disclosure channel for any of that.
    """
    if original_exception is not None:
        _logger.error(
            "Internal server error: %s: %s",
            type(original_exception).__name__,
            original_exception,
            exc_info=original_exception,
        )

    return create_error_response(
        AgentErrorType.INTERNAL,
        message,
        details or {},
        status_code=500,
    )


def convert_http_exception_to_agent_error(exc: HTTPException) -> JSONResponse:
    """Convert FastAPI HTTPException to standardized agent error format"""
    
    # Map status codes to error types
    status_to_type = {
        400: AgentErrorType.VALIDATION_ERROR,
        401: AgentErrorType.AUTH_FAILED,
        429: AgentErrorType.RATE_LIMIT,
        500: AgentErrorType.INTERNAL,
        502: AgentErrorType.DOWNSTREAM_5XX,
        504: AgentErrorType.DOWNSTREAM_TIMEOUT
    }
    
    error_type = status_to_type.get(exc.status_code, AgentErrorType.INTERNAL)
    
    return create_error_response(
        error_type,
        str(exc.detail),
        status_code=exc.status_code
    )


# Custom exception handler for FastAPI
async def agent_exception_handler(request, exc: HTTPException):
    """Global exception handler for FastAPI that converts to agent card format"""
    return convert_http_exception_to_agent_error(exc)


async def general_exception_handler(request, exc: Exception):
    """Global exception handler for unhandled exceptions"""
    return handle_internal_error(
        "An unexpected error occurred",
        original_exception=exc
    )
