"""LangChain `AzureChatOpenAI` factory for the LangGraph + chat paths.

Sole model client
-----------------
The ONLY model-client factory in the codebase.  Both the chat endpoints
(`langchain_chat`) and the LangGraph topology call into
:func:`build_langchain_model_client`.

The module speaks to the Walmart Azure OpenAI gateway and uses the
shared authentication path (`llm.azure_handler`).

Why a fresh client per call
---------------------------
The Walmart gateway issues short-TTL SOA signatures via the
`llm.azure_handler` package.  Caching a client at module level means the
signature ages out and subsequent requests fail, so every call builds
a fresh client with a fresh signature.
"""
from __future__ import annotations

import json
import os
from typing import Any

from agent_factory.common.logging import get_logger
from agent_factory.infrastructure.settings import get_config


# ── SSE-decode safety patch for the Walmart Azure OpenAI gateway ───────
# The gateway occasionally concatenates two JSON objects in a single
# SSE data field.  We patch ServerSentEvent.json to parse only the first
# valid object.  Importing this module installs the patch once.
try:
    import openai._streaming as _oai_streaming

    if not getattr(_oai_streaming.ServerSentEvent.json, "_walmart_safe_patched", False):
        _original_sse_json = _oai_streaming.ServerSentEvent.json
        _json_decoder = json.JSONDecoder()

        def _safe_sse_json(self):  # type: ignore[no-redef]
            try:
                return _original_sse_json(self)
            except json.JSONDecodeError as e:
                if "Extra data" in str(e):
                    obj, _ = _json_decoder.raw_decode(self.data)
                    return obj
                raise

        _safe_sse_json._walmart_safe_patched = True  # type: ignore[attr-defined]
        _oai_streaming.ServerSentEvent.json = _safe_sse_json
except Exception:  # pragma: no cover — SDK internals may shift across versions
    pass


_config = get_config()
_ca_bundle = getattr(_config, "LIGHTRAG_REQUESTS_CA_BUNDLE", "")
if _ca_bundle and os.path.exists(_ca_bundle):
    os.environ["SSL_CERT_FILE"] = _ca_bundle

logger = get_logger("agents.langchain_client")


def build_langchain_model_client(
    *,
    max_tokens: int = 4096,
    temperature: float = 0.1,
) -> Any:
    """Build a fresh LangChain `AzureChatOpenAI` with current auth headers.

    Must be called per-request — the underlying SOA signature expires.

    Args:
        max_tokens: Cap on completion tokens.
        temperature: Sampling temperature.

    Returns:
        A `langchain_openai.AzureChatOpenAI` instance configured against
        the Walmart Azure OpenAI gateway with the SOA signature headers
        applied via the default_headers path.
    """
    # Lazy imports so the module loads cleanly in tests that mock
    # langchain_openai out and in environments without the Walmart
    # llm.azure_handler package.
    from langchain_openai import AzureChatOpenAI
    from llm.azure_handler import llm_handler  # type: ignore[import]  # Walmart-internal

    headers = llm_handler.get_azure_chat_headers()
    model = llm_handler.model_name
    api_version = llm_handler.api_version
    endpoint = llm_handler.gateway_url
    api_key = llm_handler.api_key

    logger.info(
        "[DEBUG] build_langchain_model_client: model=%s endpoint=%s "
        "api_version=%s api_key_parts=%d header_keys=%s",
        model,
        endpoint,
        api_version,
        len(api_key.split(".")) if api_key else 0,
        list(headers.keys()),
    )

    # `default_headers` is forwarded into the underlying openai SDK's
    # AsyncAzureOpenAI client and carries the SOA-signed auth.
    return AzureChatOpenAI(
        azure_deployment=model,
        api_version=api_version,
        azure_endpoint=endpoint,
        api_key=api_key,
        default_headers=headers,
        max_tokens=max_tokens,
        temperature=temperature,
    )


__all__ = ["build_langchain_model_client"]
