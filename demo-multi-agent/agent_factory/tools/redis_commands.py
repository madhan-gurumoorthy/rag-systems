"""Declarative Redis command dispatcher for the ``redis`` tool type.

A single async function — :func:`dispatch_redis_command` — maps the
12 commands the ``redis`` tool spec officially supports onto the
corresponding ``redis.asyncio`` client methods.  Anything not in the
table is forwarded to :py:meth:`redis.asyncio.Redis.execute_command`
as-is, which keeps the executor honest for the long tail of Redis
verbs that don't need bespoke argument parsing.

The :class:`~agent_factory.tools.handlers.redis.RedisHandler` dispatches
into this via the thin instance-method shim on
:class:`~agent_factory.tools.executor.ToolExecutor`
(``_execute_redis_command``).  ``TestExecuteRedisCommand`` in
``tests/unit/test_executor_methods.py`` exercises it directly via
``ex._execute_redis_command(client, command, key, args)`` — the shim
keeps that contract intact.

Supported commands (case-sensitive, upper-case):

  * String:  ``GET``, ``SET``, ``INCR``, ``DEL``, ``EXISTS``, ``TTL``,
             ``EXPIRE``
  * Hash:    ``HGET``, ``HGETALL``
  * List:    ``LRANGE``
  * Set:     ``SMEMBERS``, ``SISMEMBER``
"""
from __future__ import annotations

from typing import Any


async def dispatch_redis_command(
    client, command: str, key: str, args: list[str],
) -> Any:
    """Dispatch a Redis command to the appropriate client method."""
    if command == "GET":
        return await client.get(key)
    elif command == "SET":
        value = args[0] if args else ""
        ex = int(args[1]) if len(args) > 1 else None
        return await client.set(key, value, ex=ex)
    elif command == "HGETALL":
        return await client.hgetall(key)
    elif command == "HGET":
        field = args[0] if args else ""
        return await client.hget(key, field)
    elif command == "LRANGE":
        start = int(args[0]) if args else 0
        stop = int(args[1]) if len(args) > 1 else -1
        return await client.lrange(key, start, stop)
    elif command == "SMEMBERS":
        members = await client.smembers(key)
        return list(members)
    elif command == "SISMEMBER":
        member = args[0] if args else ""
        return await client.sismember(key, member)
    elif command == "EXISTS":
        return await client.exists(key)
    elif command == "DEL":
        return await client.delete(key)
    elif command == "TTL":
        return await client.ttl(key)
    elif command == "INCR":
        return await client.incr(key)
    elif command == "EXPIRE":
        seconds = int(args[0]) if args else 0
        return await client.expire(key, seconds)
    else:
        # Generic fallback — execute raw command
        return await client.execute_command(command, key, *args)


__all__ = ["dispatch_redis_command"]
