"""End-to-end smoke tests against a live agent-factory deployment.

Targets the host in ``E2E_BASE_URL`` (set by the kitt ``e2e_tests``
looper flow to the deployed pack URL).  Runs after deploy and is
TestBurst-reported.
"""
from __future__ import annotations

import os

import httpx
import pytest

_E2E_BASE_URL = os.getenv(
    "E2E_BASE_URL", "https://stage.gif-tote-validation.matbot.walmart.com"
).rstrip("/")
_TIMEOUT = float(os.getenv("E2E_HTTP_TIMEOUT", "15"))


def test_healthz_responds():
    """Live: ``GET /healthz`` returns 200 with a JSON body."""
    response = httpx.get(f"{_E2E_BASE_URL}/healthz", timeout=_TIMEOUT)
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, dict)
    assert "status" in body


def test_readyz_responds():
    """Live: ``GET /readyz`` returns 200 once dependencies are warm."""
    response = httpx.get(f"{_E2E_BASE_URL}/readyz", timeout=_TIMEOUT)
    assert response.status_code == 200
