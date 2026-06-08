"""
Custom header generator for external agent calls.

Users can modify the generate_custom_headers() function to add their own
authentication headers (service registry, OAuth, etc.).
"""

from typing import Dict, Optional

# NOTE: Import these only when you implement custom authentication:
# import base64
# import time
# from Crypto.PublicKey import RSA
# from Crypto.Signature import PKCS1_v1_5
# from Crypto.Hash import SHA256
# from agent_factory.infrastructure.settings import get_config
# from agent_factory.common.logging import get_logger


def generate_custom_headers(correlation_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """
    Generate custom authentication headers for external agent calls.
    
    **DEFAULT BEHAVIOR**: Returns empty dict (no custom headers).
    **USERS**: Modify this function body to implement your own authentication logic.
    
    Example use cases:
    - Service registry headers (WM_CONSUMER.ID, WM_SEC.AUTH_SIGNATURE)
    - Azure AD tokens  
    - OAuth bearer tokens
    - Custom API keys
    
    Args:
        correlation_headers: Existing headers (traceparent, session-id, etc.) 
                           that you may want to include or reference
    
    Returns:
        Dictionary of custom headers to add to the request.
        Empty dict by default (no impact on existing functionality).
    
    ---
    
    EXAMPLE IMPLEMENTATION (Walmart Service Registry):
    
    Step 1: Add imports at top of file:
        import base64
        import time
        from Crypto.PublicKey import RSA
        from Crypto.Signature import PKCS1_v1_5
        from Crypto.Hash import SHA256
        from agent_factory.infrastructure.settings import get_config
        from agent_factory.common.logging import get_logger
        
        logger = get_logger("custom_headers")
    
    Step 2: Add configuration to agent_factory/infrastructure/secrets.toml:
        [service_registry]
        consumer_id = "your-consumer-id"
        svc_name = "mod-space-pilot"
        svc_env = "prod"
        key_version = 1
        private_key_base64 = "base64-encoded-rsa-private-key"
    
    Step 3: Replace the return {} below with:
    
        try:
            config = get_config()
            sr_config = getattr(config, 'service_registry', None)
            
            if not sr_config:
                logger.warning("service_registry config not found")
                return {}
            
            # Read config
            consumer_id = sr_config.get('consumer_id')
            svc_name = sr_config.get('svc_name')
            svc_env = sr_config.get('svc_env')
            key_version = sr_config.get('key_version', 1)
            pvt_key_base64 = sr_config.get('private_key_base64')
            
            if not all([consumer_id, svc_name, svc_env, pvt_key_base64]):
                logger.warning("Incomplete service_registry config")
                return {}
            
            # Generate signature
            rsa_pem = base64.b64decode(pvt_key_base64)
            timestamp = int(time.time()) * 1000
            data = f"{consumer_id}\\n{timestamp}\\n{key_version}\\n"
            
            rsakey = RSA.importKey(rsa_pem)
            signer = PKCS1_v1_5.new(rsakey)
            digest = SHA256.new()
            digest.update(data.encode('utf-8'))
            sign = signer.sign(digest)
            
            signature = base64.b64encode(sign).decode("utf-8")
            
            # Build headers
            return {
                "WM_CONSUMER.ID": consumer_id,
                "WM_SVC.NAME": svc_name,
                "WM_SVC.ENV": svc_env,
                "WM_SEC.KEY_VERSION": str(key_version),
                "WM_SEC.AUTH_SIGNATURE": signature,
                "WM_CONSUMER.INTIMESTAMP": str(timestamp),
            }
            
        except Exception as e:
            logger.error(f"Failed to generate custom headers: {e}")
            return {}
    """
    
    # Default: Return empty dict (no custom headers)
    # This ensures existing functionality is not impacted
    return {}
