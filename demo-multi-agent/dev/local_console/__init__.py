"""Local-only A2A test console for matbot.

Exposes :func:`mount_console`, an ``app.mount`` helper that serves a
Vite + React SPA at ``/console``. The SPA exercises the A2A surface
(JSON-RPC 2.0 over ``POST /a2a`` — ``message/send`` and
``message/stream``) against a running matbot instance.

Never imported from ``agent_factory/`` runtime code; ``app.py`` only
calls ``mount_console`` when ``MATBOT_ENABLE_CONSOLE`` is truthy so the
mount is invisible on deployed instances.
"""
from dev.local_console.router import mount_console

__all__ = ["mount_console"]
