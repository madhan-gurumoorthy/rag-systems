"""
API timing decorators for performance monitoring.
"""
import time
import asyncio
import functools
from typing import Callable, Any
from agent_factory.common.logging import get_logger
from agent_factory.common.tracing import get_current_trace_info

logger = get_logger("api_timing")


def api_timer(endpoint_name: str = None):
    """
    Decorator to time API endpoint execution and log results.
    
    Args:
        endpoint_name: Custom name for the endpoint (optional)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            endpoint = endpoint_name or func.__name__
            
            # Capture trace context BEFORE function execution
            from opentelemetry import trace
            current_span = trace.get_current_span()
            
            try:
                logger.debug(f"Starting {endpoint} execution")
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                
                # Suppress noisy health/readiness check logs
                if endpoint not in {"healthz_check", "readiness_check"}:
                    # Log successful completion with preserved trace context
                    if current_span and current_span.is_recording():
                        span_context = current_span.get_span_context()
                        trace_id = format(span_context.trace_id, '032x')
                        span_id = format(span_context.span_id, '016x')

                        # Log within the span context to maintain correlation
                        with trace.use_span(current_span):
                            logger.info(
                                f"API {endpoint} completed successfully time={duration:.3f}s "
                                f"trace_id={trace_id[:8]} span_id={span_id[:8]}",
                                extra={
                                    "operation_type": "api_timing",
                                    "endpoint": endpoint,
                                    "duration_seconds": duration,
                                    "status": "success"
                                }
                            )
                    else:
                        logger.info(
                            f"API {endpoint} completed successfully time={duration:.3f}s "
                            f"trace_id=no_trace span_id=no_span",
                            extra={
                                "operation_type": "api_timing",
                                "endpoint": endpoint,
                                "duration_seconds": duration,
                                "status": "success"
                            }
                        )
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                
                # Log failed execution with preserved trace context
                if current_span and current_span.is_recording():
                    span_context = current_span.get_span_context()
                    trace_id = format(span_context.trace_id, '032x')
                    span_id = format(span_context.span_id, '016x')
                    
                    with trace.use_span(current_span):
                        logger.error(
                            f"API {endpoint} failed time={duration:.3f}s "
                            f"error={type(e).__name__} trace_id={trace_id[:8]} span_id={span_id[:8]}",
                            extra={
                                "operation_type": "api_timing",
                                "endpoint": endpoint,
                                "duration_seconds": duration,
                                "status": "error",
                                "error_type": type(e).__name__,
                                "error_message": str(e)
                            }
                        )
                else:
                    logger.error(
                        f"API {endpoint} failed time={duration:.3f}s "
                        f"error={type(e).__name__} trace_id=no_trace span_id=no_span",
                        extra={
                            "operation_type": "api_timing",
                            "endpoint": endpoint,
                            "duration_seconds": duration,
                            "status": "error",
                            "error_type": type(e).__name__,
                            "error_message": str(e)
                        }
                    )
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            endpoint = endpoint_name or func.__name__
            
            # Capture trace context BEFORE function execution
            from opentelemetry import trace
            current_span = trace.get_current_span()
            
            try:
                logger.debug(f"Starting {endpoint} execution")
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                # Suppress noisy health/readiness check logs
                if endpoint not in {"healthz_check", "readiness_check"}:
                    # Log successful completion with preserved trace context
                    if current_span and current_span.is_recording():
                        span_context = current_span.get_span_context()
                        trace_id = format(span_context.trace_id, '032x')
                        span_id = format(span_context.span_id, '016x')

                        with trace.use_span(current_span):
                            logger.info(
                                f"API {endpoint} completed successfully time={duration:.3f}s "
                                f"trace_id={trace_id[:8]} span_id={span_id[:8]}",
                                extra={
                                    "operation_type": "api_timing",
                                    "endpoint": endpoint,
                                    "duration_seconds": duration,
                                    "status": "success"
                                }
                            )
                    else:
                        logger.info(
                            f"API {endpoint} completed successfully time={duration:.3f}s "
                            f"trace_id=no_trace span_id=no_span",
                            extra={
                                "operation_type": "api_timing",
                                "endpoint": endpoint,
                                "duration_seconds": duration,
                                "status": "success"
                            }
                        )
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                
                # Log failed execution with preserved trace context
                if current_span and current_span.is_recording():
                    span_context = current_span.get_span_context()
                    trace_id = format(span_context.trace_id, '032x')
                    span_id = format(span_context.span_id, '016x')
                    
                    with trace.use_span(current_span):
                        logger.error(
                            f"API {endpoint} failed time={duration:.3f}s "
                            f"error={type(e).__name__} trace_id={trace_id[:8]} span_id={span_id[:8]}",
                            extra={
                                "operation_type": "api_timing",
                                "endpoint": endpoint,
                                "duration_seconds": duration,
                                "status": "error",
                                "error_type": type(e).__name__,
                                "error_message": str(e)
                            }
                        )
                else:
                    logger.error(
                        f"API {endpoint} failed time={duration:.3f}s "
                        f"error={type(e).__name__} trace_id=no_trace span_id=no_span",
                        extra={
                            "operation_type": "api_timing",
                            "endpoint": endpoint,
                            "duration_seconds": duration,
                            "status": "error",
                            "error_type": type(e).__name__,
                            "error_message": str(e)
                        }
                    )
                raise
        
        # Return the appropriate wrapper based on whether the function is async
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
            
    return decorator


def time_operation(operation_name: str):
    """
    Simple decorator for timing any operation (not just API endpoints).
    
    Args:
        operation_name: Name of the operation being timed
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                logger.debug(f"{operation_name} completed in {duration:.3f}s")
                return result
            except Exception as e:
                duration = time.time() - start_time
                logger.warning(f"{operation_name} failed after {duration:.3f}s: {e}")
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                logger.debug(f"{operation_name} completed in {duration:.3f}s")
                return result
            except Exception as e:
                duration = time.time() - start_time
                logger.warning(f"{operation_name} failed after {duration:.3f}s: {e}")
                raise
        
        # Return the appropriate wrapper based on whether the function is async
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
            
    return decorator


# Import asyncio for checking coroutine functions
