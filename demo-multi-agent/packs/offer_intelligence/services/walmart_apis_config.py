"""
Centralized config for upstream Walmart APIs used by the OL Triage pack.

Single source of truth for base URLs, consumer IDs, service headers, and
Uber Keys mapping-type aliases.

Resolution order for each value:
  1. OS env var (e.g. IQS_BASE_URL)
  2. Hard-coded production default
"""
from __future__ import annotations

import os
from typing import Any

# ── Timeouts ─────────────────────────────────────────────────────────────
DEFAULT_REQUEST_TIMEOUT = 30.0
UBER_KEYS_TIMEOUT = 10.0
SIV_REQUEST_TIMEOUT = 10.0
IQS_TOKEN_VALIDITY_SECONDS = 150
SIV_CONCURRENCY = 8


def _resolve(env_var: str, default: str) -> str:
    """env var → default."""
    val = os.getenv(env_var, "").strip()
    if val:
        return val
    return default


# ── Base URLs ───────────────────────────────────────────────────────────
IQS_BASE_URL = _resolve(
    "IQS_BASE_URL",
    "http://iqs.walmart.com/catalog/v1",
)
IQS_UBER_V1_URL = _resolve(
    "IQS_UBER_V1_URL",
    "http://iqs.walmart.com/uber/v1",
)
UBER_MAPPING_BASE_URL = _resolve(
    "UBER_MAPPING_BASE_URL",
    "http://uber-mappings-read-nsf.walmart.com/mappings?=null",
)
UBER_KEYS_BASE_URL = _resolve(
    "UBER_KEYS_BASE_URL",
    "http://uber-keys-read-nsf.walmart.com/mappings",
)
RAMPART_BASE_URL = _resolve(
    "RAMPART_BASE_URL",
    "https://rampart-prod.location-services-v2.k8s.glb.us.walmart.net/v4/graphql",
)
OL_API_ENDPOINT = _resolve(
    "OL_API_ENDPOINT",
    "http://offer-store-setup.prod.offerstore.catdev.prod.walmart.com",
)
OFFER_API_ENDPOINT = _resolve(
    "OFFER_API_ENDPOINT",
    "http://offer-store-setup.prod.offerstore.catdev.prod.walmart.com",
)
PRODUCT_API_ENDPOINT = _resolve(
    "PRODUCT_API_ENDPOINT",
    "http://product-store-read-app.prod.walmart.com",
)
STORE_PRICE_ENDPOINT = _resolve(
    "STORE_PRICE_ENDPOINT",
    "http://item-pricing-setup-service-wcnp.us.walmart.net",
)
OASIS_ENDPOINT = _resolve(
    "OASIS_ENDPOINT",
    "http://oasis-availability-api-sf.wakanda.prod.walmart.com",
)
LIGHTRAG_REQUESTS_CA_BUNDLE = _resolve("LIGHTRAG_REQUESTS_CA_BUNDLE", "") or None

# ── Consumer IDs ────────────────────────────────────────────────────────
IQS_CONSUMER_ID = _resolve(
    "IQS_CONSUMER_ID",
    "2125c457-ef1b-404a-9563-398829563bc8",
)
UBER_KEYS_CONSUMER_ID = _resolve(
    "UBER_KEYS_CONSUMER_ID",
    "2707c258-7500-4952-b8c3-fe435fdb91de",
)
RAMPART_CONSUMER_ID = _resolve(
    "RAMPART_CONSUMER_ID",
    "2125c457-ef1b-404a-9563-398829563bc8",
)
IQS_KEY_VERSION = _resolve("IQS_KEY_VERSION", "2")


# ── Uber Keys mapping aliases (friendly → API-level) ─────────────────────
MAPPING_TYPE_ALIASES: dict[str, str] = {
    "ITEMID_TO_OFFERID": "ITEMID_TO_DOTCOM_OFFERID",
    "GTIN_TO_OFFERID": "GTIN_TO_DOTCOM_OFFERID",
    "ITEMID_TO_WPID": "ITEMID_TO_WPID",
    "OFFERID_TO_WPID": "OFFERID_TO_WPID",
    "OFFERID_TO_ITEMID": "OFFERID_TO_ITEMID",
    "WPID_TO_ITEMID": "WPID_TO_ITEMID",
    "WPID_TO_GTIN": "WPID_TO_GTIN",
    "GTIN_TO_WPID": "GTIN_TO_WPID",
    "GTIN_TO_ITEMID": "GTIN_TO_ITEMID",
    "GTIN_TO_CID": "GTIN_TO_CID",
    "OFFERID_TO_GTIN": "DOTCOM_OFFER_ID_TO_GTIN",
    "WUPC_TO_GTIN": "WUPC_TO_GTIN",
    "COMPONENT_TO_BUNDLE": "COMPONENT_TO_BUNDLE",
    "BUNDLE_TO_COMPONENT": "BUNDLE_TO_COMPONENT",
}


def resolve_mapping_type(mapping_type: str) -> str:
    """Convert a friendly mapping type name to the API-level type."""
    return MAPPING_TYPE_ALIASES.get(mapping_type, mapping_type)


# ── Standard request headers ────────────────────────────────────────────
def uber_mapping_headers() -> dict[str, str]:
    """Headers for the Uber Mappings (POST) endpoint used by SIV."""
    return {
        "WM_CONSUMER.ID": IQS_CONSUMER_ID,
        "WM_SVC.NAME": "UBER-MAPPINGS-READ-NSF",
        "WM_SVC.ENV": "prod",
        "Content-Type": "application/json",
        "wm_svc.version": "0.0.1",
    }


def uber_keys_headers() -> dict[str, str]:
    """Headers for the Uber Keys (GET) endpoint used by Merloc."""
    return {
        "WM_CONSUMER.ID": UBER_KEYS_CONSUMER_ID,
        "WM_SVC.ENV": "prod",
        "WM_MART_ID": "0",
        "WM_SVC.NAME": "uber-keys-read-nsf",
        "wm_svc.version": "0.0.1",
        "Content-Type": "application/json",
    }


def rampart_headers() -> dict[str, str]:
    """Headers for the Rampart GraphQL endpoint used by Merloc."""
    return {
        "Cache-Control": "no-cache",
        "Content-Type": "application/json",
        "WM_CONSUMER.ID": RAMPART_CONSUMER_ID,
        "WM_SVC.ENV": "prod",
        "WM_SVC.NAME": "RAMPART",
    }


# ── IQS private-key resolution ──────────────────────────────────────────
def get_iqs_private_key_text() -> str:
    """Resolve the IQS RSA private key text.

    Resolution order:
      1. IQS_PRIVATE_KEY env var (raw key contents)
      2. IQS_PRIVATE_KEY_PATH env var (path to key file)
      3. <pack_root>/certs/iqs_private_key.key (project-relative default)

    Returns the key text, or empty string if not configured.
    """
    text = os.getenv("IQS_PRIVATE_KEY", "")
    if text:
        return text

    env_path = os.getenv("IQS_PRIVATE_KEY_PATH", "")
    if env_path and os.path.exists(env_path):
        try:
            with open(env_path) as fh:
                return fh.read()
        except OSError:
            pass

    pack_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    default_path = os.path.join(pack_root, "certs", "iqs_private_key.key")
    if os.path.exists(default_path):
        try:
            with open(default_path) as fh:
                return fh.read()
        except OSError:
            pass

    return ""
