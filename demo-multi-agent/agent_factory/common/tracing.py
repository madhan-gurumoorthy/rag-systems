"""
Simplified OpenTelemetry distributed tracing for Walmart TraceStore.
ONE class, clear separation of concerns.
"""
import os
import socket
import functools
from typing import Any, Callable, Optional, Dict
import asyncio
from urllib.parse import urlparse

from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

try:
    from opentelemetry.instrumentation.openai import OpenAIInstrumentor
except ImportError:
    OpenAIInstrumentor = None

try:
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter as GRPCExporter
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as HTTPExporter
except ImportError:
    GRPCExporter = None
    HTTPExporter = None

from agent_factory.infrastructure.telemetry import TracingConfig


class DistributedTracer:
    """
    All-in-one distributed tracing class.
    
    Handles:
    1. OpenTelemetry setup (console/OTLP exporters)
    2. W3C trace context propagation (distributed tracing)
    3. Span decorators (functions and FastAPI endpoints)
    4. Trace info extraction
    """
    
    def __init__(self):
        self.tracer_provider = None
        self.tracer = None
        self.service_name = TracingConfig.SERVICE_NAME
        self.logger = None
        self.propagator = TraceContextTextMapPropagator()
    
    # ========================================================================
    # 1. INITIALIZATION
    # ========================================================================
    
    def _get_logger(self):
        """Lazy logger initialization"""
        if self.logger is None:
            from agent_factory.common.logging import get_logger
            self.logger = get_logger("tracing")
        return self.logger
    
    def setup(self, service_name: str = None, environment: str = None, 
              app_version: str = None) -> TracerProvider:
        """Initialize distributed tracing"""
        self.service_name = service_name or TracingConfig.SERVICE_NAME
        env = environment or TracingConfig.get_environment()
        app_version = app_version or TracingConfig.SERVICE_VERSION
        
        logger = self._get_logger()
        
        if not TracingConfig.is_tracing_enabled():
            logger.warning("Tracing disabled via TRACING_ENABLED=false")
            return None
        
        # Create resource with service metadata
        resource = Resource.create({
            SERVICE_NAME: self.service_name,
            "service.version": app_version,
            "deployment.environment": env,
            **self._get_k8s_attributes()
        })
        
        self.tracer_provider = TracerProvider(resource=resource)
        
        # Add exporter (console or OTLP)
        collector = TracingConfig.get_collector_endpoint()
        if collector:
            exporter = self._create_exporter(collector)
        else:
            exporter = ConsoleSpanExporter()
        
        self.tracer_provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(self.tracer_provider)
        self.tracer = trace.get_tracer(self.service_name)
        
        # Instrument OpenAI
        if OpenAIInstrumentor:
            OpenAIInstrumentor().instrument()
        
        logger.info(f"Tracing initialized: {self.service_name} [{env}]")
        return self.tracer_provider
    
    def _create_exporter(self, endpoint: str):
        """Create OTLP exporter (gRPC or HTTP)"""
        logger = self._get_logger()

        protocol_override = (
            os.getenv("OTEL_EXPORTER_OTLP_TRACES_PROTOCOL")
            or os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL")
            or ""
        ).lower()

        parsed = urlparse(endpoint if "://" in endpoint else f"https://{endpoint}")
        host = parsed.hostname or ""
        port = parsed.port
        path = parsed.path or ""

        def should_use_grpc() -> bool:
            if protocol_override.startswith("grpc"):
                return True
            if protocol_override.startswith("http"):
                return False

            if port == 4317:
                return True
            if port == 4318:
                return False

            if host and "trace-collector" in host:
                return True

            if path and path.rstrip("/").endswith("v1/traces"):
                return False

            # Default to gRPC when unsure, matching Walmart TraceStore expectations
            return True

        insecure = TracingConfig.is_insecure_mode()
        ca_bundle = None if insecure else TracingConfig.get_ca_bundle_path()

        if should_use_grpc() and GRPCExporter:
            grpc_endpoint = endpoint
            try:
                if ca_bundle and host:
                    # Ensure gRPC uses Walmart CA bundle when available
                    os.environ.setdefault("GRPC_DEFAULT_SSL_ROOTS_FILE_PATH", ca_bundle)
                exporter = GRPCExporter(endpoint=grpc_endpoint, insecure=insecure)
                logger.info(f"Configured gRPC OTLP exporter for {host or grpc_endpoint}")
                return exporter
            except Exception as exc:
                logger.error(f"Failed to create gRPC OTLP exporter: {exc}")
                # Fall through to HTTP exporter as a fallback

        if HTTPExporter:
            http_endpoint = endpoint.rstrip('/')
            if not path.rstrip('/').endswith("v1/traces"):
                http_endpoint = f"{http_endpoint}/v1/traces"
            try:
                exporter = HTTPExporter(
                    endpoint=http_endpoint,
                    certificate_file=ca_bundle,
                    insecure=insecure,
                )
                logger.info(f"Configured HTTP OTLP exporter for {host or http_endpoint}")
                return exporter
            except Exception as exc:
                logger.error(f"Failed to create HTTP OTLP exporter: {exc}")

        logger.warning("OTLP exporter unavailable, falling back to console exporter")
        return ConsoleSpanExporter()
    
    def _get_k8s_attributes(self) -> Dict[str, str]:
        """Auto-detect Kubernetes metadata"""
        attrs = {}
        mappings = {
            "k8s.namespace.name": ["NAMESPACE", "K8S_NAMESPACE"],
            "k8s.pod.name": ["HOSTNAME", "POD_NAME"],
        }
        for attr, env_vars in mappings.items():
            for env_var in env_vars:
                if value := os.getenv(env_var):
                    attrs[attr] = value
                    break
        return attrs
    
    def get_tracer(self) -> trace.Tracer:
        """Get tracer instance"""
        if not self.tracer:
            self.setup()
        return self.tracer
    
    # ========================================================================
    # 2. TRACE INFO EXTRACTION
    # ========================================================================
    
    def get_trace_info(self) -> Dict[str, str]:
        """Get current trace/span IDs (single source of truth)"""
        current_span = trace.get_current_span()
        
        if not current_span or not current_span.is_recording():
            return {"trace_id": "no_trace", "span_id": "no_span"}
        
        ctx = current_span.get_span_context()
        if ctx.trace_id == 0:
            return {"trace_id": "no_trace", "span_id": "no_span"}
        
        return {
            "trace_id": format(ctx.trace_id, "032x"),
            "span_id": format(ctx.span_id, "016x")
        }
    
    # ========================================================================
    # 3. W3C TRACE CONTEXT PROPAGATION (for distributed tracing)
    # ========================================================================
    
    def extract_trace_headers(self, request) -> Dict[str, str]:
        """Extract W3C traceparent/tracestate from HTTP headers"""
        headers = {}
        if tp := request.headers.get("traceparent"):
            headers["traceparent"] = tp
        if ts := request.headers.get("tracestate"):
            headers["tracestate"] = ts
        return headers
    
    def extract_parent_span_id(self, traceparent: str) -> str:
        """Parse parent span ID from traceparent header"""
        if not traceparent:
            return "unknown"
        try:
            # Format: 00-{trace_id}-{parent_span_id}-{flags}
            parts = traceparent.split('-')
            return parts[2] if len(parts) >= 3 else "unknown"
        except Exception:
            return "unknown"
    
    def propagate_context(self, request):
        """Attach incoming trace context (returns token or None)"""
        from opentelemetry import context as otel_context
        
        headers = self.extract_trace_headers(request)
        if not headers:
            return None
        
        ctx = self.propagator.extract(headers)
        remote_span = trace.get_current_span(ctx)
        
        if remote_span and remote_span.get_span_context().is_valid:
            return otel_context.attach(ctx)
        return None
    
    def add_correlation_headers(self, response, trace_id: str, span_id: str,
                               session_id: str, message_id: str = None):
        """Inject trace correlation headers into response
        
        NOTE: All headers are conditionally set only if their values are not None.
        This ensures consistent header behavior - headers with None values are not set.
        The message_id is optional (default None) and follows the same conditional logic.
        """
        # Only set headers if values are not None
        if trace_id:
            response.headers["X-Trace-ID"] = trace_id
        if span_id:
            response.headers["X-Span-ID"] = span_id
        if session_id:
            response.headers["X-Session-ID"] = session_id
        if message_id:
            response.headers["X-Message-ID"] = message_id
        return response
    
    # ========================================================================
    # 4. DECORATORS
    # ========================================================================
    
    def trace_function(self, span_name: str = None, **attributes):
        """
        Decorator for tracing any function.
        
        Usage:
            @tracer.trace_function("db.query", table="users")
            async def query_users():
                ...
        """
        def decorator(func: Callable) -> Callable:
            actual_name = span_name or f"{func.__module__}.{func.__name__}"
            
            if asyncio.iscoroutinefunction(func):
                @functools.wraps(func)
                async def async_wrapper(*args, **kwargs):
                    with self.get_tracer().start_as_current_span(actual_name) as span:
                        for key, value in attributes.items():
                            span.set_attribute(key, str(value))
                        try:
                            result = await func(*args, **kwargs)
                            span.set_status(trace.Status(trace.StatusCode.OK))
                            return result
                        except Exception as e:
                            span.record_exception(e)
                            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                            raise
                return async_wrapper
            else:
                @functools.wraps(func)
                def sync_wrapper(*args, **kwargs):
                    with self.get_tracer().start_as_current_span(actual_name) as span:
                        for key, value in attributes.items():
                            span.set_attribute(key, str(value))
                        try:
                            result = func(*args, **kwargs)
                            span.set_status(trace.Status(trace.StatusCode.OK))
                            return result
                        except Exception as e:
                            span.record_exception(e)
                            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                            raise
                return sync_wrapper
        return decorator
    
    def trace_endpoint(self, span_name: str):
        """
        Decorator for FastAPI A2A endpoints.
        
        Handles W3C propagation + correlation headers automatically.
        
        Usage:
            @tracer.trace_endpoint("api.invoke")
            async def invoke(request, http_request, traceparent=None, ...):
                ...
        """
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                from opentelemetry import context as otel_context
                import time
                
                start_time = time.time()
                
                # Extract HTTP request
                http_request = kwargs.get('http_request')
                traceparent = kwargs.get('traceparent')
                
                # Propagate W3C context if present
                token = None
                if http_request and traceparent:
                    token = self.propagate_context(http_request)
                
                try:
                    # Create span
                    with self.get_tracer().start_as_current_span(span_name) as span:
                        span.set_attribute("http.method", "POST")
                        
                        # Call endpoint
                        result = await func(*args, **kwargs)
                        
                        # Add correlation headers
                        if hasattr(result, 'headers'):
                            info = self.get_trace_info()
                            session_id = kwargs.get('x_session_id', 'auto-generated')
                            message_id = kwargs.get('x_message_id')
                            self.add_correlation_headers(
                                result, info['trace_id'], info['span_id'],
                                session_id, message_id
                            )
                        
                        span.set_status(trace.Status(trace.StatusCode.OK))
                        return result
                        
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                    raise
                finally:
                    if token:
                        otel_context.detach(token)
            
            return wrapper
        return decorator


# ============================================================================
# GLOBAL SINGLETON
# ============================================================================

_tracer = DistributedTracer()

# Public API
setup_tracing = _tracer.setup
get_tracer = _tracer.get_tracer
get_current_trace_info = _tracer.get_trace_info
trace_function = _tracer.trace_function
trace_a2a_endpoint = _tracer.trace_endpoint
extract_parent_span_id = _tracer.extract_parent_span_id
add_correlation_headers = _tracer.add_correlation_headers


# ============================================================================
# CONTEXT MANAGER (for manual child spans)
# ============================================================================

class traced_operation:
    """Context manager for child spans"""
    def __init__(self, operation_name: str, **attributes):
        self.operation_name = operation_name
        self.attributes = attributes
        self.span = None
    
    def __enter__(self):
        self.span = get_tracer().start_span(self.operation_name)
        self.span.__enter__()
        for key, value in self.attributes.items():
            self.span.set_attribute(key, str(value))
        return self.span
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.span:
            if exc_type:
                self.span.record_exception(exc_val)
                self.span.set_status(trace.Status(trace.StatusCode.ERROR, str(exc_val)))
            else:
                self.span.set_status(trace.Status(trace.StatusCode.OK))
            self.span.__exit__(exc_type, exc_val, exc_tb)
        return False
