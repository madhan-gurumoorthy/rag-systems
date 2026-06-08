"""Root conftest — applied to all tests.

Bootstraps the minimum environment for the logging subsystem to
initialise without a real ``secrets.toml``.

The logging filter in ``agent_factory/common/logging.py`` lazily imports
``agent_factory.common.tracing``, which in turn imports
``agent_factory.infrastructure.telemetry.TracingConfig``.
That class reads ``AGENT_NAME`` via Dynaconf.  Without it, any test that
exercises a code path that emits a log warning/error raises an
``AttributeError`` at import time.

We fix this by:
1. Setting ``DYNACONF_AGENT_NAME`` in ``os.environ`` (Dynaconf's env-var
   convention) *before* any module-level Dynaconf lookup fires.
2. Resetting the ``agent_factory.infrastructure.settings._config`` singleton
   so Dynaconf re-reads the env var if it was cached before the env was set.
"""
from __future__ import annotations

import os
import sys

# Dynaconf prefix for env-var overrides is "DYNACONF_" by default.
os.environ.setdefault("DYNACONF_AGENT_NAME", "test-agent")
os.environ.setdefault("ENV_FOR_DYNACONF", "testing")

# If agent_factory.infrastructure.settings was already imported and cached,
# bust the singleton so Dynaconf picks up the env var on next access.
if "agent_factory.infrastructure.settings" in sys.modules:
    import agent_factory.infrastructure.settings as _cfg_mod
    _cfg_mod._config = None
