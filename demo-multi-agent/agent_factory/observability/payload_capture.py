"""Bounded, redacted request/response preview capture.

Used by the auto HTTP transports to attach a small JSON preview of the
upstream payload to each ``api_call`` event, so the dashboard can show
"what did SIV actually return" without blowing up storage or leaking PII.

Design constraints (in order):

1. **Zero added latency on the caller's path.**  The transport may stash
   raw bytes into the recorder dict (cheap memcpy) but every expensive
   step — JSON parse, redaction walk, truncation — runs inside the
   already fire-and-forget ``_emit`` task on the event loop, after the
   originating coroutine has returned.
2. **Bounded size.**  Hard cap at ``MAX_PREVIEW_BYTES`` per body.
   Responses above the cap are reported as ``{"_truncated": true}``
   with their byte count, never expanded.
3. **PII-safe by default.**  Any JSON key matching ``REDACT_KEY_PATTERN``
   has its value replaced with ``"***"``.  The pattern is operator-
   tunable via ``[default.observability.redact_keys]`` in
   ``secrets.toml``.

Operators can also flip the whole capture off for one or more services
by listing them under ``[default.observability.capture_disable]``.
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional

try:
    from agent_factory.common.logging import get_logger
    logger = get_logger("observability.payload_capture")
except ImportError:  # pragma: no cover
    import logging
    logger = logging.getLogger("observability.payload_capture")


# ── Tunables (lazy-load from settings on first use) ──────────────────

# 8 KB per preview — enough to see the shape and the few fields that
# matter, small enough that 100 events per session stay under 1 MB.
DEFAULT_MAX_PREVIEW_BYTES = 8 * 1024

# Keys whose VALUES should be replaced with "***" before storage.
DEFAULT_REDACT_KEYS = (
    "password", "passwd", "secret", "token", "apikey", "api_key",
    "authorization", "auth", "ssn", "creditcard", "credit_card",
    "cardnumber", "card_number", "cvv", "phone", "email", "private_key",
)


def _load_capture_config() -> dict:
    """Lazy-load capture tunables from the dynaconf settings block.

    Falls back silently to defaults if the block is missing.
    """
    try:
        from agent_factory.infrastructure.settings import get_settings
        s = get_settings()
        block = getattr(s, "observability", None)
        if block is None:
            return {}
        if hasattr(block, "to_dict"):
            block = block.to_dict()
        if isinstance(block, dict):
            return block
    except Exception as exc:  # pragma: no cover
        logger.debug("observability config load failed: %s", exc)
    return {}


_CONFIG_CACHE: Optional[dict] = None


def _config() -> dict:
    global _CONFIG_CACHE
    if _CONFIG_CACHE is None:
        _CONFIG_CACHE = _load_capture_config()
    return _CONFIG_CACHE


def _redact_pattern() -> re.Pattern:
    keys = _config().get("redact_keys") or DEFAULT_REDACT_KEYS
    return re.compile("|".join(re.escape(k) for k in keys), re.IGNORECASE)


def _max_bytes() -> int:
    cap = _config().get("max_preview_bytes")
    if isinstance(cap, int) and cap > 0:
        return cap
    return DEFAULT_MAX_PREVIEW_BYTES


def capture_disabled_for(service: str) -> bool:
    """``True`` if payload capture is turned off for ``service`` via config."""
    disabled = _config().get("capture_disable") or []
    if isinstance(disabled, str):
        disabled = [disabled]
    return service in disabled


# ── Capture (cheap — runs on the caller's path) ──────────────────────

def stash_response_bytes(
    rec: dict,
    *,
    content: Optional[bytes],
    content_type: Optional[str],
) -> None:
    """Attach raw response bytes to the recorder dict for later parsing.

    Cheap — just two key sets.  The expensive parse/redact/truncate work
    is deferred to :func:`finalize_preview`, which runs inside the
    fire-and-forget ``_emit`` task.

    Skips when:
      * ``content`` is empty or ``None``
      * ``content_type`` is missing or non-JSON-ish
      * raw length already exceeds the cap (we record only the byte
        count in that case — no preview)
    """
    if not content:
        return
    if not _is_json_ct(content_type):
        rec["_response_content_type"] = content_type or ""
        return
    cap = _max_bytes()
    if len(content) > cap:
        rec["response_preview"] = {"_truncated": True, "_bytes": len(content)}
        rec["_response_content_type"] = content_type or ""
        return
    rec["_response_bytes_raw"] = content
    rec["_response_content_type"] = content_type or ""


def stash_request_bytes(
    rec: dict,
    *,
    content: Optional[bytes],
    content_type: Optional[str],
) -> None:
    """Same contract as :func:`stash_response_bytes`, for the request side."""
    if not content:
        return
    if not _is_json_ct(content_type):
        return
    cap = _max_bytes()
    if len(content) > cap:
        rec["request_preview"] = {"_truncated": True, "_bytes": len(content)}
        return
    rec["_request_bytes_raw"] = content


# ── Finalize (heavy — runs inside the fire-and-forget _emit task) ──

def finalize_preview(rec: dict) -> None:
    """Convert any stashed raw bytes into parsed, redacted preview dicts.

    Mutates ``rec`` in place: removes the raw byte keys and replaces
    them with ``response_preview`` / ``request_preview`` JSON-friendly
    structures.  Best-effort — bad JSON becomes a ``{"_raw": "..."}``
    string preview rather than crashing the recorder.
    """
    raw = rec.pop("_response_bytes_raw", None)
    if raw is not None:
        rec["response_preview"] = _bytes_to_preview(raw)
    raw_req = rec.pop("_request_bytes_raw", None)
    if raw_req is not None:
        rec["request_preview"] = _bytes_to_preview(raw_req)


def _bytes_to_preview(raw: bytes) -> Any:
    """Parse ``raw`` bytes as JSON and redact PII keys.  Falls back to a
    truncated string if parsing fails."""
    try:
        text = raw.decode("utf-8", errors="replace")
        parsed = json.loads(text)
    except Exception:
        return {"_raw": raw[:512].decode("utf-8", errors="replace")}
    return _redact(parsed)


def _redact(node: Any, _depth: int = 0) -> Any:
    """Recursively replace values whose key matches the redact pattern.

    Depth-capped at 16 to keep pathological payloads from stalling the
    background task.  Below the cap the redaction walks the entire tree.
    """
    if _depth > 16:
        return "***depth-capped***"
    pat = _redact_pattern()
    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            if isinstance(k, str) and pat.search(k):
                out[k] = "***"
            else:
                out[k] = _redact(v, _depth + 1)
        return out
    if isinstance(node, list):
        return [_redact(item, _depth + 1) for item in node]
    return node


def _is_json_ct(content_type: Optional[str]) -> bool:
    if not content_type:
        return False
    ct = content_type.split(";", 1)[0].strip().lower()
    return ct.endswith("/json") or ct.endswith("+json")
