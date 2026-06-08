"""Functional smoke tests for the agent factory runtime.

In-process FastAPI smoke checks that boot the app without a live
database or LLM provider.  Runs inside the kitt ``functional_tests``
looper flow and is TestBurst-reported.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DYNACONF_AGENT_NAME", "test-agent")
os.environ.setdefault("ENV_FOR_DYNACONF", "testing")

import app as app_module  # noqa: E402


def test_app_object_exposes_metadata():
    """The FastAPI app object exists and carries a non-empty title."""
    assert app_module.app is not None
    assert isinstance(app_module.app.title, str)
    assert app_module.app.title.strip()


def test_healthz_returns_ok():
    """``/healthz`` returns 200 with a JSON body."""
    with TestClient(app_module.app) as client:
        response = client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, dict)
    assert "status" in body
