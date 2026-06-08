"""API route modules.

Agent invocation rides on the A2A protocol surface mounted by
:mod:`agent_factory.api.a2a`:

  * ``POST /a2a``                          — JSON-RPC 2.0 (sync + stream)
  * ``GET  /.well-known/agent-card.json``  — AgentCard discovery

Modules in this package only provide cross-cutting HTTP concerns:

  * ``factory``    — pack/agent introspection (``/api/factory/*``).
  * ``health``     — ``/healthz``, ``/readyz``.
  * ``dashboard``  — read-only observability UI + JSON aggregates
                     (mounted only when ``IS_PARENT`` is set).
"""
