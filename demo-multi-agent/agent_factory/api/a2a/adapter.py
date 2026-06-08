"""Wire the A2A AgentCard + executor onto the existing FastAPI app.

Two-step lifecycle:

* :func:`init_a2a` — build the AgentCard (after packs are loaded) and
  the request handler.  Called from :mod:`agent_factory.api.lifespan`.
* :func:`mount_a2a` — add A2A routes (``POST /a2a`` + ``GET
  /.well-known/agent-card.json``) onto the app.  Called from
  :mod:`app` after the lifespan has registered route modules so the
  A2A endpoint sits alongside the dashboard/health routes.
"""
from __future__ import annotations

from typing import Optional

from a2a.server.apps import A2AFastAPIApplication
from a2a.server.events import InMemoryQueueManager
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCard

from agent_factory.api.a2a.agent_card import build_agent_card
from agent_factory.api.a2a.executor import create_executor
from agent_factory.common.logging import get_logger

logger = get_logger("agent_factory_api.a2a.adapter")

# Mount path for the JSON-RPC endpoint.  AgentCard is always at
# ``/.well-known/agent-card.json`` per the A2A discovery contract.
_RPC_PATH = "/a2a"


class _A2AAdapter:
    """Holds the SDK-built app between :func:`init_a2a` and :func:`mount_a2a`."""

    def __init__(self) -> None:
        self.app: Optional[A2AFastAPIApplication] = None
        self.agent_card: Optional[AgentCard] = None

    def initialize(self) -> bool:
        try:
            self.agent_card = build_agent_card()
            executor = create_executor()
            handler = DefaultRequestHandler(
                agent_executor=executor,
                task_store=InMemoryTaskStore(),
                queue_manager=InMemoryQueueManager(),
            )
            self.app = A2AFastAPIApplication(
                agent_card=self.agent_card,
                http_handler=handler,
            )
            logger.info(
                "A2A adapter initialised: card=%s skills=%d rpc=%s",
                self.agent_card.name,
                len(self.agent_card.skills),
                _RPC_PATH,
            )
            return True
        except Exception as exc:
            logger.error("A2A adapter init failed: %s", exc, exc_info=True)
            self.app = None
            self.agent_card = None
            return False

    def mount(self, app) -> bool:
        if self.app is None:
            logger.warning("A2A adapter not initialised; skipping mount.")
            return False
        try:
            before = list(app.router.routes)
            self.app.add_routes_to_app(
                app,
                agent_card_url="/.well-known/agent-card.json",
                rpc_url=_RPC_PATH,
            )
            # Mounts added at app-startup time (landing SPA at "/",
            # console SPA at "/console") were appended before us; bring
            # A2A's newly-added routes to the front so the catch-all
            # StaticFiles app does not shadow GET
            # /.well-known/agent-card.json.
            new_routes = [r for r in app.router.routes if r not in before]
            app.router.routes = new_routes + [
                r for r in app.router.routes if r not in new_routes
            ]
            logger.info(
                "A2A routes mounted: agent_card=/.well-known/agent-card.json rpc=%s",
                _RPC_PATH,
            )
            return True
        except Exception as exc:
            logger.error("A2A mount failed: %s", exc, exc_info=True)
            return False


_adapter = _A2AAdapter()


def init_a2a() -> bool:
    """Build the AgentCard and request handler.  Idempotent."""
    if _adapter.app is not None:
        return True
    return _adapter.initialize()


def mount_a2a(app) -> bool:
    """Mount A2A routes onto an existing FastAPI app."""
    return _adapter.mount(app)
