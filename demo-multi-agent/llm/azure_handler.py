"""Walmart LLM Gateway — Azure OpenAI-compatible handler.

Supports two auth modes (auto-detected from config):
  1. **Sandbox / Stage**: Uses SANDBOX_GENAIAPI_KEY JWT as ``Authorization: Bearer``
     header.  No RSA signing needed.
  2. **Production**: Generates RSA-SHA256 signed Service Registry headers
     (WM_SEC.AUTH_SIGNATURE) from a base64-encoded private key.

The module exposes a singleton ``llm_handler`` with a
``get_azure_chat_headers()`` method that ``build_model_client()`` calls
to get fresh auth headers on every request.

Ported from: sop-normalizer/matbot/core/azure_llm.py
"""

from __future__ import annotations

import os
import ssl
import time
from typing import Dict, Optional

from agent_factory.infrastructure.settings import get_config
from agent_factory.common.logging import get_logger

config = get_config()
logger = get_logger("llm.azure_handler")

# Set the CA bundle for httpx / requests
_ca_bundle = getattr(config, "LIGHTRAG_REQUESTS_CA_BUNDLE", "")
_ssl_context = ssl.create_default_context()
if _ca_bundle and os.path.isfile(_ca_bundle):
    os.environ["REQUESTS_CA_BUNDLE"] = _ca_bundle
    os.environ["SSL_CERT_FILE"] = _ca_bundle
    _ssl_context.load_verify_locations(_ca_bundle)
    logger.info(f"CA bundle found at {_ca_bundle}, using secure mode")
else:
    logger.warning(f"CA bundle not found at {_ca_bundle!r}, using system defaults")


class LangChainHandler:
    """LLM Gateway handler with sandbox JWT and Service Registry auth.

    All configuration is read from Dynaconf (secrets.toml).
    The active environment is selected by ENV_FOR_DYNACONF.
    """

    def __init__(self) -> None:
        # Read everything from Dynaconf config (secrets.toml)
        try:
            self._sandbox_key = config.azure_chat.SANDBOX_GENAIAPI_KEY or ""
        except AttributeError:
            self._sandbox_key = ""

        try:
            self._gateway_url = config.azure_chat.LIGHTRAG_AZURE_ENDPOINT
        except AttributeError:
            self._gateway_url = "https://wmtllmgateway.stage.walmart.com/wmtllmgateway"

        # Service Registry metadata (both modes)
        self._svc_name = ""
        self._svc_env = ""

        # Service Registry fallback (production) — only used if no sandbox key
        self._consumer_id = ""
        self._key_version = ""
        self._pvt_key_base64 = ""

        try:
            self._svc_name = getattr(config.azure_chat, "LIGHTRAG_SR_SVC_NAME", "WMTLLMGATEWAY")
            self._svc_env = getattr(config.azure_chat, "LIGHTRAG_SR_SVC_ENV", "stage")
        except AttributeError:
            pass

        if not self._sandbox_key:
            try:
                self._consumer_id = config.azure_chat.LIGHTRAG_CONSUMER_ID
                self._key_version = config.azure_chat.LIGHTRAG_CONSUMER_KEY_VERSION
                self._pvt_key_base64 = config.azure_chat.LIGHTRAG_LLM_PRIVATE_KEY
            except AttributeError:
                pass

        self.last_usage: Dict | None = None

        auth_mode = "sandbox_jwt" if self._sandbox_key else (
            "service_registry" if self._consumer_id else "none"
        )
        logger.info(f"LLM auth mode: {auth_mode} url={self._gateway_url}")

    # ── Public API (called by build_model_client) ────────────────────

    def get_azure_chat_headers(self, correlation_headers: Optional[Dict] = None) -> Dict[str, str]:
        """Build auth headers for the LLM Gateway.

        Priority:
          1. Sandbox JWT → Authorization: Bearer token (local dev, stage)
          2. Service Registry → RSA-signed SOA headers (production)
        """
        headers = {
            "Content-Type": "application/json",
            "WM_SVC.NAME": self._svc_name or "WMTLLMGATEWAY",
            "WM_SVC.ENV": self._svc_env or "stage",
            "wm_llm_gw.user_type": "TECH_DEVELOPMENT",
            "wm_llm_gw.user_name": self._consumer_id or "agent-factory",
        }

        if self._sandbox_key:
            # Sandbox JWT auth — Bearer token
            headers["Authorization"] = f"Bearer {self._sandbox_key}"
            logger.debug("auth_mode=sandbox_jwt")
        elif self._consumer_id and self._pvt_key_base64:
            # Service Registry RSA signature auth (production)
            sr_headers = self._build_sr_headers()
            headers.update(sr_headers)
            logger.debug("auth_mode=service_registry")
        else:
            logger.warning("No LLM Gateway credentials configured")

        if correlation_headers:
            headers.update(correlation_headers)

        return headers

    # ── Properties (used by build_model_client) ──────────────────────

    @property
    def api_key(self) -> str:
        """Return the API key for the OpenAI SDK.

        For sandbox JWT auth, this is the JWT token itself so the SDK
        sends it as the ``api-key`` header that the gateway validates.
        For Service Registry auth, a placeholder is fine because auth
        is handled entirely via custom SOA headers.
        """
        if self._sandbox_key:
            return self._sandbox_key
        return os.environ.get("AZURE_OPENAI_API_KEY", "placeholder")

    @property
    def gateway_url(self) -> str:
        return self._gateway_url

    @property
    def model_name(self) -> str:
        try:
            return config.azure_chat.LIGHTRAG_MODEL
        except AttributeError:
            return "gpt-4.1-mini"

    @property
    def api_version(self) -> str:
        try:
            return config.azure_chat.LIGHTRAG_API_VERSION
        except AttributeError:
            return "2024-10-21"

    # ── Private helpers ──────────────────────────────────────────────

    def _build_sr_headers(self) -> Dict[str, str]:
        """Generate Service Registry RSA-signed headers for production auth."""
        import base64
        from Crypto.PublicKey import RSA
        from Crypto.Signature import PKCS1_v1_5
        from Crypto.Hash import SHA256

        rsa_pem = base64.b64decode(self._pvt_key_base64)
        timestamp = int(time.time()) * 1000
        data = f"{self._consumer_id}\n{timestamp}\n{self._key_version}\n"
        rsakey = RSA.importKey(rsa_pem)
        signer = PKCS1_v1_5.new(rsakey)
        digest = SHA256.new()
        digest.update(data.encode("utf-8"))
        sign = signer.sign(digest)
        sig_b64 = base64.b64encode(sign).decode("utf-8")

        return {
            "WM_CONSUMER.ID": self._consumer_id,
            "WM_SEC.KEY_VERSION": str(self._key_version),
            "WM_SEC.AUTH_SIGNATURE": sig_b64,
            "WM_CONSUMER.INTIMESTAMP": str(timestamp),
        }


# Module-level singleton — lazy-init on first import
llm_handler = LangChainHandler()
