"""A2A protocol surface for matbot.

Mounts an A2A v0.3 JSON-RPC endpoint (``POST /a2a``) and an AgentCard
discovery endpoint (``GET /.well-known/agent-card.json``) onto the
existing FastAPI app.  Every loaded pack is advertised as a separate
:class:`a2a.types.AgentSkill`; callers pick a pack by setting either
``metadata.agent_id`` or ``metadata.skill_id`` on the message.
"""
from agent_factory.api.a2a.adapter import init_a2a, mount_a2a

__all__ = ["init_a2a", "mount_a2a"]
