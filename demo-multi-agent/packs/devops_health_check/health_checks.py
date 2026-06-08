from __future__ import annotations

from typing import Any

_CPU_THRESHOLD_PERCENT = 85.0


def check_ping(hostname: str) -> dict[str, Any]:
    """Mock ping — ``down-*`` hostnames return status=down."""
    is_down = hostname.lower().startswith("down-")
    return {
        "hostname": hostname,
        "status": "down" if is_down else "up",
        "latency_ms": None if is_down else 12.3,
    }


def check_cpu(hostname: str) -> dict[str, Any]:
    """Mock CPU check — ``busy-*`` hostnames return above-threshold load."""
    cpu_pct = 96.4 if hostname.lower().startswith("busy-") else 22.5
    return {
        "hostname": hostname,
        "cpu_percent": cpu_pct,
        "threshold": _CPU_THRESHOLD_PERCENT,
        "exceeds": cpu_pct > _CPU_THRESHOLD_PERCENT,
    }


def notify_oncall(hostname: str, message: str) -> dict[str, Any]:
    """Mock on-call notification."""
    return {
        "delivered": True,
        "hostname": hostname,
        "message": message,
        "channel": "#devops-oncall",
    }


def restart_service(hostname: str, service_name: str) -> dict[str, Any]:
    """Mock service restart."""
    return {
        "restarted": True,
        "hostname": hostname,
        "service_name": service_name,
        "restart_id": f"restart-{hostname}-{service_name}",
    }


__all__ = ["check_ping", "check_cpu", "notify_oncall", "restart_service"]
