"""
Tracing configuration for different environments
"""
import os
from agent_factory.infrastructure.settings import get_config

class TracingConfig:
    """Configuration for distributed tracing"""

    # Service configuration — lazily resolved from secrets.toml / env var.
    # The try/except guard ensures the class can be imported before Dynaconf
    # has a secrets.toml present (e.g. in tests and CI environments).
    try:
        SERVICE_NAME: str = get_config().AGENT_NAME
    except Exception:
        SERVICE_NAME: str = "agent-factory"

    SERVICE_VERSION = "1.0.0"
    
    # Environment-specific collector endpoints
    COLLECTOR_ENDPOINTS = {
        "dev": "https://trace-collector.nonprod.walmart.com",
        "qa": "https://trace-collector.nonprod.walmart.com", 
        "stage": "https://trace-collector.nonprod.walmart.com",
        "prod": "https://trace-collector.prod.walmart.com",
        "local": "https://trace-collector.nonprod.walmart.com"  # Local also sends to nonprod
    }
    
    # Default attributes for all spans
    DEFAULT_ATTRIBUTES = {
        "wm.app": SERVICE_NAME,
        "wm.app.version": SERVICE_VERSION,
        "cloud.provider": "Private",
        "cloud.infrastructure_service": "WCNP",
        "telemetry.sdk.language": "python",
        "telemetry.sdk.name": "opentelemetry"
    }
    
    @classmethod
    def get_ca_bundle_path(cls) -> str:
        """Get CA bundle path for Walmart certificates"""
        # Try to get from config first
        try:
            from agent_factory.infrastructure.settings import get_config
            config = get_config()
            ca_bundle = getattr(config, 'LIGHTRAG_REQUESTS_CA_BUNDLE', None)
            if ca_bundle and os.path.exists(ca_bundle):
                return ca_bundle
        except Exception:
            pass
        
        # Fallback paths
        fallback_paths = [
            "agent_factory/infrastructure/ca-bundle.crt",
            "/etc/ssl/certs/ca-bundle.crt",
            "/etc/ssl/certs/ca-certificates.crt"
        ]
        
        for path in fallback_paths:
            if os.path.exists(path):
                return path
        
        return None
    
    @classmethod
    def get_environment(cls) -> str:
        """Get current deployment environment"""
        return os.getenv("DEPLOYMENT_ENVIRONMENT", "dev").lower()
    
    @classmethod
    def get_collector_endpoint(cls) -> str:
        """Get appropriate collector endpoint for current environment"""
        env = cls.get_environment()
        
        # Check for custom endpoint first
        custom_endpoint = (
            os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT") or 
            os.getenv("OTEL_COLLECTOR_HOST_NAME")
        )
        if custom_endpoint:
            return custom_endpoint
            
        return cls.COLLECTOR_ENDPOINTS.get(env, cls.COLLECTOR_ENDPOINTS["dev"])
    
    @classmethod
    def is_tracing_enabled(cls) -> bool:
        """Check if tracing should be enabled"""
        return os.getenv("TRACING_ENABLED", "true").lower() == "true"
    
    @classmethod
    def is_insecure_mode(cls) -> bool:
        """Check if insecure mode is enabled (for non-production)"""
        # Force insecure mode for nonprod endpoints unless explicitly set to false
        env_value = os.getenv("OTEL_EXPORTER_OTLP_INSECURE")
        if env_value is not None:
            return env_value.lower() == "true"
        
        # Default to secure mode if CA bundle is available, insecure otherwise
        ca_bundle = cls.get_ca_bundle_path()
        if ca_bundle:
            # Use logging instead of print - import lazily to avoid circular imports
            try:
                from agent_factory.common.logging import get_logger
                logger = get_logger("tracing_config")
                logger.info(f"CA bundle found at {ca_bundle}, using secure mode")
            except ImportError:
                pass  # Fallback silently if logging not available during early init
            return False  # Use secure mode with CA bundle
        
        # Default to insecure for Walmart collectors when no CA bundle
        try:
            from agent_factory.common.logging import get_logger
            logger = get_logger("tracing_config")
            logger.warning("No CA bundle found, using insecure mode")
        except ImportError:
            pass  # Fallback silently if logging not available during early init
        return True
