"""Custom logging utility — plain-text / JSON syslog-style formatting with
session, message, and trace ID propagation via contextvars."""
from __future__ import annotations

import logging
import os
import socket
import sys
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Optional

# Context variables for request tracking (propagate through asyncio tasks).
_session_id_var: ContextVar[Optional[str]] = ContextVar("session_id", default=None)
_message_id_var: ContextVar[Optional[str]] = ContextVar("message_id", default=None)
_user_id_var: ContextVar[Optional[str]] = ContextVar("user_id", default=None)
_agent_name_var: ContextVar[Optional[str]] = ContextVar("agent_name", default=None)
_calling_agent_var: ContextVar[Optional[str]] = ContextVar("calling_agent", default=None)


def get_current_trace_info() -> dict:
    """Get current trace and span IDs for debugging - Import from tracing utils"""
    try:
        from agent_factory.common.tracing import get_current_trace_info as _get_trace_info
        return _get_trace_info()
    except ImportError:
        return {"trace_id": "no_trace", "span_id": "no_span", "trace_flags": 0}


def get_session_id() -> Optional[str]:
    return _session_id_var.get()


def set_session_id(session_id: Optional[str]) -> None:
    _session_id_var.set(session_id)


def get_message_id() -> Optional[str]:
    return _message_id_var.get()


def set_message_id(message_id: Optional[str]) -> None:
    _message_id_var.set(message_id)


def get_user_id() -> Optional[str]:
    return _user_id_var.get()


def set_user_id(user_id: Optional[str]) -> None:
    _user_id_var.set(user_id)


def get_agent_name() -> Optional[str]:
    return _agent_name_var.get()


def set_agent_name(agent_name: Optional[str]) -> None:
    _agent_name_var.set(agent_name)


def get_calling_agent() -> Optional[str]:
    return _calling_agent_var.get()


def set_calling_agent(calling_agent: Optional[str]) -> None:
    _calling_agent_var.set(calling_agent)


def set_full_context(user_id: str, session_id: str, message_id: Optional[str] = None, agent_name: Optional[str] = None, calling_agent: Optional[str] = None) -> None:
    """Set complete logging context for requests.
    
    Args:
        user_id: User identifier
        session_id: Session identifier
        message_id: Optional message identifier
        agent_name: Optional agent name (this service)
        calling_agent: Optional calling agent name (upstream caller)
    """
    set_user_id(user_id)
    set_session_id(session_id)
    if message_id:
        set_message_id(message_id)
    if agent_name:
        set_agent_name(agent_name)
    if calling_agent:
        set_calling_agent(calling_agent)


def clear_session_context() -> None:
    """Clear all session-related context variables."""
    _session_id_var.set(None)
    _message_id_var.set(None)
    _user_id_var.set(None)
    _agent_name_var.set(None)


@contextmanager
def with_session_context(session_id: Optional[str], message_id: Optional[str] = None):
    """Context manager for session context."""
    session_token = _session_id_var.set(session_id)
    message_token = _message_id_var.set(message_id) if message_id else None
    try:
        yield
    finally:
        _session_id_var.reset(session_token)
        if message_token:
            _message_id_var.reset(message_token)


@contextmanager
def with_full_context(user_id: str, session_id: str, message_id: Optional[str] = None, agent_name: Optional[str] = None):
    """Context manager for complete request context."""
    user_token = _user_id_var.set(user_id)
    session_token = _session_id_var.set(session_id)
    message_token = _message_id_var.set(message_id) if message_id else None
    agent_token = _agent_name_var.set(agent_name) if agent_name else None
    try:
        yield
    finally:
        _user_id_var.reset(user_token)
        _session_id_var.reset(session_token)
        if message_token:
            _message_id_var.reset(message_token)
        if agent_token:
            _agent_name_var.reset(agent_token)


class _ConversationContextFilter(logging.Filter):
    """Injects session_id, message_id, user_id, trace_id into every LogRecord."""

    def __init__(self, app_name: str):
        super().__init__()
        self._hostname = socket.gethostname()
        self._app_name = app_name

    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        # Get simplified context information
        user_id = get_user_id()
        session_id = get_session_id()
        message_id = get_message_id()
        agent_name = get_agent_name()
        calling_agent = get_calling_agent()
        
        # Get trace context information
        trace_info = get_current_trace_info()
        
        # Attach attributes - simplified format
        record.user_id = user_id or "no_user"
        record.session_id = session_id or "no_sess"
        record.message_id = message_id or "no_msg"
        record.agent_name = agent_name
        record.calling_agent = calling_agent or "NA"
        record.trace_id = trace_info.get("trace_id", "no_trace")
        record.span_id = trace_info.get("span_id", "no_span")
        record.hostname = self._hostname
        record.service = self._app_name
        return True


class _SyslogPlainFormatter(logging.Formatter):
    """Plain-text syslog formatter without timestamp."""

    def format(self, record: logging.LogRecord) -> str:
        # Get IDs for formatting
        session_id = getattr(record, "session_id", "no_sess")
        message_id = getattr(record, "message_id", "no_msg")
        user_id = getattr(record, "user_id", "no_user")
        trace_id = getattr(record, "trace_id", "no_trace")
        calling_agent = getattr(record, "calling_agent", "NA")
        
        # Format calling agent
        record.calling_agent_prefix = f"calling_agent={calling_agent} " if calling_agent and calling_agent != "NA" else ""
        
        return super().format(record)

    def __init__(self):
        super().__init__(
            fmt="%(levelname)s SID=%(session_id)s MID=%(message_id)s UID=%(user_id)s TID=%(trace_id)s %(calling_agent_prefix)s%(message)s"
        )


class _SyslogJsonFormatter(logging.Formatter):
    """JSON structured formatter optimized for OpenObserve with robust error handling."""
    
    def format(self, record: logging.LogRecord) -> str:
        try:
            import json
            from datetime import datetime
            
            log_entry = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "level": record.levelname,
                "service": os.getenv("SERVICE_NAME", "mod-space-pilot"),
                "user_id": self._safe_get(record, "user_id"),
                "session_id": self._safe_get(record, "session_id"),
                "message_id": self._safe_get(record, "message_id"),
                "trace_id": self._safe_get(record, "trace_id"),  # Keep full trace ID for JSON
                "span_id": self._safe_get(record, "span_id"),   # Keep full span ID for JSON
                "agent_name": self._safe_get(record, "agent_name"),
                "logger": record.name,
                "module": getattr(record, "module", None),
                "function": getattr(record, "funcName", None),
                "line": getattr(record, "lineno", None),
                "message": self._safe_get_message(record)
            }
            
            # Add exception info if present with robust error handling
            if record.exc_info:
                log_entry["exception"] = self._format_exception_safe(record)
                log_entry["has_exception"] = True
            else:
                log_entry["has_exception"] = False
            
            # Add extra fields from record if present
            self._add_extra_fields(log_entry, record)
                
            # Remove None values to keep logs clean
            log_entry = {k: v for k, v in log_entry.items() if v is not None}
                
            return json.dumps(log_entry, separators=(',', ':'), ensure_ascii=False, default=self._json_serializer)
            
        except Exception as e:
            # Fallback to plain text if JSON formatting fails
            return f"LOG_FORMAT_ERROR: {str(e)} | Original: {getattr(record, 'getMessage', lambda: str(record))()}"
    
    def _safe_get(self, record, attr_name, default=None):
        """Safely get attribute from record with fallback"""
        try:
            return getattr(record, attr_name, default)
        except Exception:
            return default
    
    def _safe_truncate(self, value, length):
        """Safely truncate string value"""
        try:
            if value and isinstance(value, str) and len(value) > length:
                return value[:length]
            return value
        except Exception:
            return str(value)[:length] if value else None
    
    def _safe_get_message(self, record):
        """Safely get log message with fallback"""
        try:
            return record.getMessage()
        except Exception as e:
            try:
                return str(record.msg)
            except Exception:
                return f"Message format error: {str(e)}"
    
    def _format_exception_safe(self, record):
        """Safely format exception with robust error handling"""
        try:
            if not record.exc_info:
                return None
                
            exc_type, exc_value, exc_traceback = record.exc_info
            
            exception_info = {
                "type": exc_type.__name__ if exc_type else "Unknown",
                "message": str(exc_value) if exc_value else "No message",
                "stack_trace": None
            }
            
            # Try to format stack trace
            try:
                stack_trace = self.formatException(record.exc_info)
                # Truncate very long stack traces for JSON readability
                if len(stack_trace) > 5000:
                    exception_info["stack_trace"] = stack_trace[:5000] + "\n... [truncated]"
                    exception_info["stack_trace_truncated"] = True
                else:
                    exception_info["stack_trace"] = stack_trace
            except Exception:
                try:
                    import traceback
                    stack_trace = ''.join(traceback.format_exception(*record.exc_info))
                    if len(stack_trace) > 5000:
                        exception_info["stack_trace"] = stack_trace[:5000] + "\n... [truncated]"
                        exception_info["stack_trace_truncated"] = True
                    else:
                        exception_info["stack_trace"] = stack_trace
                except Exception:
                    exception_info["stack_trace"] = "Stack trace formatting failed"
            
            return exception_info
            
        except Exception as e:
            return {
                "type": "ExceptionFormattingError",
                "message": str(e),
                "stack_trace": "Failed to format original exception",
                "formatter_error": True
            }
    
    def _json_serializer(self, obj):
        """Custom JSON serializer for non-standard types"""
        try:
            if hasattr(obj, '__dict__'):
                return str(obj)
            elif hasattr(obj, '__str__'):
                return str(obj)
            else:
                return repr(obj)
        except Exception:
            return "<unserializable>"
    
    def _add_extra_fields(self, log_entry: dict, record):
        """Add extra fields from record if present"""
        try:
            # Standard extra fields that might be added via logger.info(..., extra={...})
            standard_fields = [
                "token_count", "operation_type", "duration_ms", "success",
                "query_length", "error_type", "error_context",
                "recovery_id", "recovery_suggestion",
                "stack_trace_truncated", "formatter_error"
            ]
            
            for field in standard_fields:
                if hasattr(record, field):
                    value = getattr(record, field)
                    if value is not None:
                        log_entry[field] = self._sanitize_value(value)
                        
            # Add any other extra fields that might be custom
            if hasattr(record, '__dict__'):
                for key, value in record.__dict__.items():
                    # Add fields that are not standard logging fields and not already processed
                    if (key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                                  'filename', 'module', 'lineno', 'funcName', 'created', 'msecs',
                                  'relativeCreated', 'thread', 'threadName', 'processName', 'process',
                                  'getMessage', 'exc_info', 'exc_text', 'stack_info', 'user_id',
                                  'session_id', 'conversation_id', 'agent_name', 'trace_id', 'span_id',
                                  'hostname', 'service'] and 
                        key not in log_entry and 
                        not key.startswith('_')):
                        log_entry[key] = self._sanitize_value(value)
                        
        except Exception:
            pass  # Ignore errors when adding extra fields

    def _sanitize_value(self, value):
        """Sanitize value for JSON serialization"""
        try:
            # Handle common problematic types
            if isinstance(value, bool):  # Check bool before int
                return value
            elif isinstance(value, int):
                # Handle very large integers
                if abs(value) > 9007199254740991:  # JavaScript safe integer limit
                    return str(value)
                return value
            elif isinstance(value, float):
                # Handle special float values that break JSON
                if value != value:  # NaN
                    return "NaN"
                elif value == float('inf'):
                    return "Infinity" 
                elif value == float('-inf'):
                    return "-Infinity"
                else:
                    return value
            elif isinstance(value, str):
                # Ensure string is safe for JSON and not too long
                if len(value) > 10000:  # Truncate very long strings
                    return value[:10000] + "... [truncated]"
                return value.encode('utf-8', errors='replace').decode('utf-8')
            elif isinstance(value, (list, tuple)):
                # Limit list size and sanitize elements
                if len(value) > 100:
                    sanitized_list = [self._sanitize_value(item) for item in value[:100]]
                    sanitized_list.append("... [truncated]")
                    return sanitized_list
                return [self._sanitize_value(item) for item in value]
            elif isinstance(value, dict):
                # Limit dict size and sanitize values
                if len(value) > 50:
                    truncated_dict = {str(k): self._sanitize_value(v) for k, v in list(value.items())[:50]}
                    truncated_dict["__truncated__"] = True
                    return truncated_dict
                return {str(k): self._sanitize_value(v) for k, v in value.items()}
            else:
                str_value = str(value)
                if len(str_value) > 1000:
                    return str_value[:1000] + "... [truncated]"
                return str_value
        except Exception:
            return "<serialization_failed>"


def _build_handler(app_name: str, use_json: bool = False) -> logging.Handler:
    handler = logging.StreamHandler(stream=sys.stdout)
    if use_json:
        handler.setFormatter(_SyslogJsonFormatter())
    else:
        handler.setFormatter(_SyslogPlainFormatter())
    handler.addFilter(_ConversationContextFilter(app_name=app_name))
    return handler


def _determine_log_format() -> bool:
    """Determine whether to use JSON logging based on environment"""
    # Check explicit override first
    log_format = os.getenv("LOG_FORMAT", "").lower()
    if log_format in ["json", "plain"]:
        return log_format == "json"
    
    # Auto-detect based on environment
    environment = os.getenv("ENVIRONMENT", "").lower()
    deploy_env = os.getenv("DEPLOY_ENV", "").lower()
    
    # Use JSON for production/staging environments
    if environment in ["production", "prod", "staging", "stage"]:
        return True
    if deploy_env in ["production", "prod", "staging", "stage"]:
        return True
    
    # Use plain text for local development
    return False


def get_logger(name: str, level: int = logging.INFO, use_json: bool = None) -> logging.Logger:
    """Create or retrieve a logger with environment-aware formatting.

    Args:
        name: Logger name
        level: Logging level (default: INFO)
        use_json: If True, use JSON formatter; if False, use plain text formatter.
                 If None, auto-detect based on environment

    Environment Variables:
        LOG_FORMAT: "json" or "plain" - explicit override
        ENVIRONMENT: "production", "staging", "development" - auto-detection

    Ensures no duplicate handlers are added on repeated calls.
    """
    # Determine logging format
    if use_json is None:
        use_json = _determine_log_format()
    
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False  # avoid duplicate logs via root

    # Reuse existing handler if already configured
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        app_name = os.getenv("APP_NAME", name)
        logger.addHandler(_build_handler(app_name, use_json=use_json))

    return logger


def configure_lightrag_logging(app_name: str = "mod-space-pilot", level: int = logging.INFO) -> None:
    """Configure LightRAG logger to use our custom format.
    
    This ensures LightRAG logs follow the same format as our application logs.
    Should be called during application initialization.
    """
    # Determine logging format
    use_json = _determine_log_format()
    
    # Configure LightRAG root logger
    lightrag_logger = logging.getLogger("lightrag")
    lightrag_logger.setLevel(level)
    lightrag_logger.propagate = False
    
    # Remove existing handlers to avoid duplicates
    for handler in lightrag_logger.handlers[:]:
        lightrag_logger.removeHandler(handler)
    
    # Add our custom handler
    lightrag_logger.addHandler(_build_handler(app_name, use_json=use_json))
    
    # Also configure specific LightRAG submodules if they exist
    for module_name in ["lightrag.kg", "lightrag.base", "lightrag.llm", "lightrag.storage"]:
        module_logger = logging.getLogger(module_name)
        module_logger.setLevel(level)
        module_logger.propagate = True  # Let parent lightrag logger handle it
    
    logger = get_logger(__name__)
    logger.info("LightRAG logging configured with custom format")


def generate_session_id(user_id: str = "NA", prefix: str = "sess") -> str:
    """Generate a UUIDv7 session identifier.

    Returns a RFC-9562 UUIDv7 string suitable for use as ``session.session_id``
    (UUID column).  The ``user_id`` and ``prefix`` args are accepted but
    are not embedded in the value — both are already captured in the
    logging context and the session row's ``domain_data`` column.
    """
    import os as _os
    import time as _time

    ts_ms = int(_time.time() * 1000) & 0xFFFFFFFFFFFF
    rand_a = int.from_bytes(_os.urandom(2), "big") & 0x0FFF
    rand_b = int.from_bytes(_os.urandom(8), "big") & 0x3FFFFFFFFFFFFFFF
    uuid_int = (
        (ts_ms << 80)
        | (0x7 << 76)
        | (rand_a << 64)
        | (0x2 << 62)
        | rand_b
    )
    return str(uuid.UUID(int=uuid_int))


def generate_conversation_id(session_id: str = None, prefix: str = "conv") -> str:
    """Generate a conversation ID within a session.
    
    Args:
        session_id: Parent session ID (optional)
        prefix: Conversation ID prefix (default: 'conv')
    
    Returns:
        Format: conv-{timestamp}-{random}
        Example: conv-20241217143022-def456
    """
    from datetime import datetime
    
    # Use timestamp for ordering conversations
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    
    # Add random component
    random_suffix = str(uuid.uuid4())[:6]
    
    return f"{prefix}-{timestamp}-{random_suffix}"


def configure_for_openobserve(service_name: str = "mod-space-pilot") -> None:
    """Configure logging optimally for OpenObserve"""
    os.environ["LOG_FORMAT"] = "json"
    os.environ["SERVICE_NAME"] = service_name


def configure_for_local_development() -> None:
    """Configure logging for local development"""
    os.environ["LOG_FORMAT"] = "plain"


def force_json_logging() -> None:
    """Force JSON logging (useful for local testing of production format)"""
    os.environ["LOG_FORMAT"] = "json"


# Utility functions for structured logging
def log_user_query(logger: logging.Logger, query: str, user_id: str):
    """Log user queries with structured data"""
    extra = {
        "operation_type": "user_query",
        "query_length": len(query)
    }
    logger.info(f"User {user_id} query: {query[:100]}{'...' if len(query) > 100 else ''}", extra=extra)


def log_operation_timing(logger: logging.Logger, operation: str, duration_ms: float, success: bool = True):
    """Log operation timing for performance monitoring"""
    extra = {
        "operation_type": operation,
        "duration_ms": duration_ms,
        "success": success
    }
    message = f"Operation {operation} {'completed' if success else 'failed'} in {duration_ms:.2f}ms"
    logger.info(message, extra=extra)


def log_agent_response(logger: logging.Logger, agent_name: str, message: str, token_count: int = None):
    """Log agent responses with structured data"""
    # Temporarily set agent name in context
    original_agent = get_agent_name()
    set_agent_name(agent_name)
    
    try:
        extra = {}
        if token_count:
            extra["token_count"] = token_count
        logger.info(message, extra=extra)
    finally:
        set_agent_name(original_agent)


# Add additional utility functions for error handling
def log_system_error(logger: logging.Logger, error: Exception, context: str = "system"):
    """Log system-level errors with additional context"""
    extra = {
        "error_type": type(error).__name__,
        "error_context": context,
        "operation_type": "system_error"
    }
    logger.error(f"System error in {context}: {str(error)}", exc_info=True, extra=extra)


def create_error_recovery_context():
    """Create a context for error recovery logging"""
    recovery_id = str(uuid.uuid4())[:8]
    return {
        "recovery_id": recovery_id,
        "timestamp": time.time(),
        "operation_type": "error_recovery"
    }
