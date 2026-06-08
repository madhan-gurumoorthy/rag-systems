"""
Shared IQS RSA signing helper.

Signs requests to ``iqs.walmart.com`` (catalog/v1, uber/v1) with the
pack's RSA private key. Cached signatures avoid re-signing on every
call. Thread-safe.

Used by every service in this pack that calls IQS:
  * ``siv_service``        — store-item-verification fan-out
  * ``validator_service``  — unpublish reason-code validators
  * any future IQS consumer

The key, consumer ID, and key version come from
``walmart_apis_config`` (env-var driven with prod defaults).
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from base64 import b64encode
from typing import Any, Dict, Optional, Tuple

from packs.offer_intelligence.services.walmart_apis_config import (
    IQS_CONSUMER_ID,
    IQS_KEY_VERSION,
    IQS_TOKEN_VALIDITY_SECONDS,
    get_iqs_private_key_text,
)

logger = logging.getLogger(__name__)


class IqsSignatureManager:
    """Manages RSA-signed tokens for IQS authentication.

    Caches signatures for ``IQS_TOKEN_VALIDITY_SECONDS`` to avoid
    re-signing on every request. Thread-safe.

    ``get_signature()`` returns ``(signature, epoch_ms)`` or
    ``(None, None)`` if no private key is configured — callers must
    handle the no-key case (typically by failing the request or
    falling back to demo mode).
    """

    def __init__(self) -> None:
        self._signer = None
        self._lock = threading.Lock()
        self._cache: Dict[str, Any] = {
            "signature": None,
            "epoch_ms": None,
            "expires_at": 0.0,
        }
        self._initialized = False

    def _load_key(self) -> None:
        if self._initialized:
            return

        key_text = get_iqs_private_key_text()
        if not key_text:
            logger.warning(
                "iqs_auth.private_key_missing: IQS-signed calls will error. "
                "Set IQS_PRIVATE_KEY env var, IQS_PRIVATE_KEY_PATH env var, "
                "or place the key at packs/offer_intelligence/certs/iqs_private_key.key"
            )
            self._initialized = True
            return

        try:
            from Crypto.PublicKey import RSA
            from Crypto.Signature import PKCS1_v1_5

            rsa_key = RSA.importKey(key_text)
            self._signer = PKCS1_v1_5.new(rsa_key)
            self._initialized = True
            logger.info("iqs_auth.rsa_key_loaded")
        except Exception as exc:
            logger.error(f"iqs_auth.rsa_key_load_failed error={exc}")
            self._initialized = True

    def _sign(self, epoch_ms: int) -> str:
        from Crypto.Hash import SHA256

        data = f"{IQS_CONSUMER_ID}\n{epoch_ms}\n{IQS_KEY_VERSION}\n"
        digest = SHA256.new()
        digest.update(data.encode("utf-8"))
        signature_bytes = self._signer.sign(digest)
        return b64encode(signature_bytes).decode("utf-8")

    def get_signature(self) -> Tuple[Optional[str], Optional[int]]:
        """Return a cached or freshly signed ``(signature, epoch_ms)``.

        Returns ``(None, None)`` if the private key is not configured.
        """
        self._load_key()
        if self._signer is None:
            return None, None

        now = time.time()
        with self._lock:
            if self._cache["signature"] and now < self._cache["expires_at"]:
                return self._cache["signature"], self._cache["epoch_ms"]

            epoch_ms = int(time.time() * 1000)
            signature = self._sign(epoch_ms)
            self._cache["signature"] = signature
            self._cache["epoch_ms"] = epoch_ms
            self._cache["expires_at"] = now + IQS_TOKEN_VALIDITY_SECONDS
            return signature, epoch_ms


# Module-level singleton — all callers share one cache.
_signature_manager = IqsSignatureManager()


def get_iqs_signature_manager() -> IqsSignatureManager:
    """Return the shared IQS signature manager."""
    return _signature_manager


def iqs_signed_headers(
    *,
    svc_name: str = "item-setup-query-service-app",
    svc_version: str = "0.0.1",
    tenant_id: str = "0",
    extra: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """Build the full IQS request header set with a fresh signed token.

    Raises ``RuntimeError`` if the private key is not configured —
    callers should catch and surface the failure in their response.

    Args:
        svc_name: Value for ``WM_SVC.NAME`` (defaults to the IQS
            catalog service identifier — matches what IQS expects
            for the RSA-signed consumer).
        svc_version: Value for ``WM_SVC.VERSION``.
        tenant_id: Value for ``WM_TENANT_ID``.
        extra: Optional additional headers merged on top of the signed
            base headers (extra values win on conflict).
    """
    signature, epoch_ms = _signature_manager.get_signature()
    if signature is None:
        raise RuntimeError(
            "IQS private key not configured — cannot sign IQS request"
        )

    headers: Dict[str, str] = {
        "WM_CONSUMER.ID": IQS_CONSUMER_ID,
        "WM_CONSUMER.INTIMESTAMP": str(epoch_ms),
        "WM_SEC.KEY_VERSION": IQS_KEY_VERSION,
        "WM_SEC.AUTH_SIGNATURE": signature,
        "WM_QOS.CORRELATION_ID": str(uuid.uuid4()),
        "WM_SVC.NAME": svc_name,
        "WM_SVC.VERSION": svc_version,
        "WM_TENANT_ID": tenant_id,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if extra:
        headers.update(extra)
    return headers
