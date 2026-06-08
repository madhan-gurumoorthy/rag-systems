"""
Agent-to-Agent (A2A) HTTP Client with automatic trace propagation.

This module provides a reusable client for making calls to other agents
while automatically propagating trace context and required headers.
"""

from typing import Dict, Any, Optional
import httpx
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from .logging import get_logger
from .tracing import trace_function
from agent_factory.infrastructure.telemetry import TracingConfig
from agent_factory.infrastructure.settings import get_config

logger = get_logger("agent_client")


def _get_agent_name() -> str:
    """Lazily read agent name from config (avoids module-level Dynaconf lookup in tests)."""
    try:
        constants = get_config().constants
        return constants.AGENT_NAME or TracingConfig.SERVICE_NAME or "unknown"
    except AttributeError:
        return TracingConfig.SERVICE_NAME or "unknown"


class AgentClient:
    """
    HTTP client for agent-to-agent communication with automatic trace propagation.

    Features:
    - Automatic W3C trace context propagation
    - Required A2A headers injection
    - Correlation ID pass-through
    - Error handling and logging
    - Response correlation headers
    """

    def __init__(
        self,
        timeout: float = 60.0,
        base_headers: Optional[Dict[str, str]] = None
    ):
        """
        Initialize the agent client.

        Args:
            timeout: Request timeout in seconds
            base_headers: Additional headers to include in all requests
        """
        self.calling_agent_name = _get_agent_name()
        self.timeout = timeout
        self.base_headers = base_headers or {}
        self.trace_propagator = TraceContextTextMapPropagator()
        
        # Initialize HTTP client
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True
        )
    
    def _prepare_headers(
        self, 
        session_id: str,
        user_id: Optional[str] = None,
        additional_headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        """
        Prepare headers for agent-to-agent communication.
                
        Args:
            session_id: Session identifier (also used as conversation_id)
            user_id: Optional user identifier
            additional_headers: Additional headers to include
            
        Returns:
            Complete headers dictionary
        """
        # Start with base headers
        headers = {
            "Content-Type": "application/json",
            **self.base_headers
        }
        
        # Add mandatory A2A headers (aligned with main.py)
        headers.update({
            "X-Calling-Agent": self.calling_agent_name,
            "X-Session-ID": session_id,  # Serves as both session and conversation ID
        })
        
        # Add optional user ID
        if user_id:
            headers["X-User-ID"] = user_id
        
        # Propagate current trace context using W3C traceparent header
        trace_context = {}
        self.trace_propagator.inject(trace_context)
        headers.update(trace_context)
        
        # Add custom headers (e.g., service registry auth)
        # Users can modify agent_factory/api/middleware/headers.py to implement their own logic
        try:
            from agent_factory.api.middleware.headers import generate_custom_headers
            custom_headers = generate_custom_headers(correlation_headers=headers.copy())
            if custom_headers:
                headers.update(custom_headers)
        except Exception as e:
            logger.warning(f"Failed to generate custom headers: {e}")
            # Continue without custom headers - don't fail the request
        
        # Add any additional headers
        if additional_headers:
            headers.update(additional_headers)
        
        return headers
    
    @trace_function(span_name="agent.http.invoke")
    async def invoke(
        self,
        target_agent_url: str,
        payload: Dict[str, Any],
        session_id: str,
        user_id: Optional[str] = None,
        additional_headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Make an HTTP call to another agent.
        
        Args:
            target_agent_url: Full URL of the target agent endpoint (e.g., "http://agent-service/api/invoke")
            payload: Request payload dictionary (flexible structure for different agents)
            session_id: Session identifier
            user_id: Optional user identifier
            additional_headers: Additional headers to include
            
        Returns:
            Dictionary containing:
            - "data": Response JSON data from the target agent
            - "headers": Response headers dictionary
            - "status_code": HTTP status code
            
        Raises:
            AgentCallError: If the agent call fails
        """
        try:
            # Prepare headers
            headers = self._prepare_headers(
                session_id=session_id,
                user_id=user_id,
                additional_headers=additional_headers
            )
            
            # Log the outgoing call
            logger.info(f"Calling agent - target: {target_agent_url}, session: {session_id[:8]}")
            
            # Make the HTTP call
            response = await self.http_client.post(
                target_agent_url,
                json=payload,
                headers=headers
            )
            
            # Handle response
            if response.status_code == 200:
                response_data = response.json()

                # Log success
                response_agent = response.headers.get('X-Agent-Name', 'unknown')
                logger.info(f"Agent call successful - target_agent: {response_agent}")

                return {
                    "data": response_data,
                    "headers": dict(response.headers),
                    "status_code": response.status_code
                }
            else:
                # Handle error response - log BEFORE raising so failures are always captured
                error_msg = f"Agent call failed with status {response.status_code}"
                response_body = ""
                try:
                    error_data = response.json()
                    error_msg += f": {error_data.get('detail', {}).get('message', 'Unknown error')}"
                    response_body = str(error_data)[:500]
                except Exception:
                    response_body = response.text[:500] if response.text else "No response body"
                    error_msg += f": {response_body}"

                logger.error(
                    f"Backend API call failed - target: {target_agent_url}, "
                    f"status: {response.status_code}, session: {session_id[:8]}, "
                    f"response_body: {response_body}",
                    extra={
                        "operation_type": "agent_call_failure",
                        "error_type": f"HTTP_{response.status_code}",
                        "target_url": target_agent_url,
                        "status_code": response.status_code,
                    }
                )
                raise AgentCallError(error_msg, status_code=response.status_code)
                
        except httpx.TimeoutException:
            error_msg = f"Agent call timed out after {self.timeout}s - target: {target_agent_url}, session: {session_id[:8]}"
            logger.error(
                error_msg,
                extra={
                    "operation_type": "agent_call_failure",
                    "error_type": "timeout",
                    "target_url": target_agent_url,
                    "timeout_seconds": self.timeout,
                }
            )
            raise AgentCallError(error_msg, status_code=408)

        except httpx.RequestError as e:
            error_msg = f"Agent call connection failed - target: {target_agent_url}, session: {session_id[:8]}, error: {str(e)}"
            logger.error(
                error_msg,
                extra={
                    "operation_type": "agent_call_failure",
                    "error_type": "connection_error",
                    "target_url": target_agent_url,
                }
            )
            raise AgentCallError(error_msg, status_code=500)

        except AgentCallError:
            raise  # Re-raise our own errors (already logged above)

        except Exception as e:
            error_msg = f"Unexpected error in agent call - target: {target_agent_url}, session: {session_id[:8]}, error: {type(e).__name__}: {str(e)}"
            logger.error(
                error_msg,
                exc_info=True,
                extra={
                    "operation_type": "agent_call_failure",
                    "error_type": type(e).__name__,
                    "target_url": target_agent_url,
                }
            )
            raise AgentCallError(f"Unexpected error: {str(e)}", status_code=500)
    
    @trace_function(span_name="agent.http.invoke_stream")
    async def invoke_stream(
        self,
        target_agent_url: str,
        payload: Dict[str, Any],
        session_id: str,
        user_id: Optional[str] = None,
        additional_headers: Optional[Dict[str, str]] = None
    ):
        """
        Make a streaming HTTP call to another agent.
        
        Args:
            target_agent_url: Full URL of the target agent streaming endpoint
            payload: Request payload dictionary (flexible structure for different agents)
            session_id: Session identifier
            user_id: Optional user identifier
            additional_headers: Additional headers to include
            
        Yields:
            Streaming response chunks from the target agent
            
        Raises:
            AgentCallError: If the agent call fails
        """
        try:
            # Prepare headers
            headers = self._prepare_headers(
                session_id=session_id,
                user_id=user_id,
                additional_headers=additional_headers
            )
            
            # Log the outgoing call
            logger.info(f"Calling agent (stream) - target: {target_agent_url}, session: {session_id[:8]}")
            
            # Make streaming request
            async with self.http_client.stream(
                "POST",
                target_agent_url,
                json=payload,
                headers=headers
            ) as response:

                if response.status_code != 200:
                    # Read error body for logging context
                    error_body = ""
                    try:
                        error_body = await response.aread()
                        error_body = error_body.decode("utf-8", errors="replace")[:500]
                    except Exception:
                        error_body = "Could not read error response body"

                    error_msg = (
                        f"Streaming agent call failed - target: {target_agent_url}, "
                        f"status: {response.status_code}, session: {session_id[:8]}, "
                        f"response_body: {error_body}"
                    )
                    logger.error(
                        error_msg,
                        extra={
                            "operation_type": "agent_call_failure",
                            "error_type": f"HTTP_{response.status_code}",
                            "target_url": target_agent_url,
                            "status_code": response.status_code,
                        }
                    )
                    raise AgentCallError(error_msg, status_code=response.status_code)

                # Stream the response
                async for chunk in response.aiter_lines():
                    if chunk:
                        yield chunk

        except AgentCallError:
            raise  # Already logged above

        except httpx.TimeoutException:
            error_msg = f"Streaming agent call timed out after {self.timeout}s - target: {target_agent_url}, session: {session_id[:8]}"
            logger.error(
                error_msg,
                extra={
                    "operation_type": "agent_call_failure",
                    "error_type": "timeout",
                    "target_url": target_agent_url,
                    "timeout_seconds": self.timeout,
                }
            )
            raise

        except httpx.RequestError as e:
            error_msg = f"Streaming agent call connection failed - target: {target_agent_url}, session: {session_id[:8]}, error: {str(e)}"
            logger.error(
                error_msg,
                extra={
                    "operation_type": "agent_call_failure",
                    "error_type": "connection_error",
                    "target_url": target_agent_url,
                }
            )
            raise

        except Exception as e:
            logger.error(
                f"Streaming call failed unexpectedly - target: {target_agent_url}, "
                f"session: {session_id[:8]}, error: {type(e).__name__}: {str(e)}",
                exc_info=True,
                extra={
                    "operation_type": "agent_call_failure",
                    "error_type": type(e).__name__,
                    "target_url": target_agent_url,
                }
            )
            raise


class AgentCallError(Exception):
    """Exception raised when an agent call fails."""
    
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code