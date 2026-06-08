"""Per-method unit tests for the DevOps Health Check pack tools.

Covers every callable in ``packs/devops_health_check/health_checks.py``
in isolation.  These functions are the deterministic mocks the
toy pack's decision matrix branches on (HOST_DOWN / CPU_HIGH / etc.),
so the contract is intentionally simple: hostname-prefix → fixed
outcome shape.  Tests pin the prefix rules, the return-dict keys,
and the threshold semantics.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Tests under packs/<pack_id>/tests/ are 3 levels below the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from packs.devops_health_check import health_checks
from packs.devops_health_check.health_checks import (
    check_cpu,
    check_ping,
    notify_oncall,
    restart_service,
)


# ─────────────────────────────────────────────────────────────────────
# check_ping
# ─────────────────────────────────────────────────────────────────────


class TestCheckPing:
    def test_healthy_host_returns_up_with_latency(self):
        result = check_ping("host-1")

        assert result == {
            "hostname": "host-1",
            "status": "up",
            "latency_ms": 12.3,
        }

    def test_down_prefix_returns_down_with_none_latency(self):
        result = check_ping("down-host-7")

        assert result["hostname"] == "down-host-7"
        assert result["status"] == "down"
        assert result["latency_ms"] is None

    @pytest.mark.parametrize(
        "hostname",
        ["DOWN-host", "Down-app01", "down-anything"],
    )
    def test_down_prefix_is_case_insensitive(self, hostname):
        # The pack's decision matrix matches outcomes after normalisation,
        # but the wrapper itself must accept any case in the prefix.
        result = check_ping(hostname)
        assert result["status"] == "down"

    def test_busy_prefix_is_still_up(self):
        # ``busy-*`` only flags CPU; it must still ping up.
        result = check_ping("busy-host-2")
        assert result["status"] == "up"
        assert result["latency_ms"] == 12.3

    def test_empty_hostname_treated_as_up(self):
        # The empty string is the safest "no info" case for the mock —
        # it must not raise, must not return down.
        result = check_ping("")
        assert result["status"] == "up"
        assert result["hostname"] == ""


# ─────────────────────────────────────────────────────────────────────
# check_cpu
# ─────────────────────────────────────────────────────────────────────


class TestCheckCpu:
    def test_healthy_host_under_threshold(self):
        result = check_cpu("host-1")

        assert result["hostname"] == "host-1"
        assert result["cpu_percent"] == 22.5
        assert result["threshold"] == 85.0
        assert result["exceeds"] is False

    def test_busy_prefix_exceeds_threshold(self):
        result = check_cpu("busy-host-2")

        assert result["hostname"] == "busy-host-2"
        assert result["cpu_percent"] == 96.4
        assert result["exceeds"] is True

    def test_threshold_is_constant_across_calls(self):
        a = check_cpu("host-a")
        b = check_cpu("busy-host-b")
        assert a["threshold"] == b["threshold"] == 85.0

    @pytest.mark.parametrize(
        "hostname",
        ["BUSY-app", "Busy-001", "busy-x"],
    )
    def test_busy_prefix_is_case_insensitive(self, hostname):
        result = check_cpu(hostname)
        assert result["exceeds"] is True
        assert result["cpu_percent"] == 96.4

    def test_down_prefix_does_not_imply_busy(self):
        # The CPU mock only flags ``busy-*``; ``down-*`` hosts report
        # normal load (ping is the right tool for down detection).
        result = check_cpu("down-host-7")
        assert result["exceeds"] is False
        assert result["cpu_percent"] == 22.5


# ─────────────────────────────────────────────────────────────────────
# notify_oncall
# ─────────────────────────────────────────────────────────────────────


class TestNotifyOncall:
    def test_returns_delivered_envelope(self):
        result = notify_oncall(hostname="host-1", message="please check")

        assert result == {
            "delivered": True,
            "hostname": "host-1",
            "message": "please check",
            "channel": "#devops-oncall",
        }

    def test_message_is_passed_through_verbatim(self):
        # The post-approval action node forwards rendered message
        # bodies that may contain newlines / markdown / unicode.
        body = "CPU 96%\n*Action:* restart kafka\n— bot 🤖"
        result = notify_oncall(hostname="busy-1", message=body)
        assert result["message"] == body
        assert result["delivered"] is True

    def test_hostname_is_echoed(self):
        result = notify_oncall(hostname="down-host-7", message="x")
        assert result["hostname"] == "down-host-7"


# ─────────────────────────────────────────────────────────────────────
# restart_service
# ─────────────────────────────────────────────────────────────────────


class TestRestartService:
    def test_returns_restarted_envelope(self):
        result = restart_service(hostname="down-host-7", service_name="kafka")

        assert result["restarted"] is True
        assert result["hostname"] == "down-host-7"
        assert result["service_name"] == "kafka"

    def test_restart_id_embeds_hostname_and_service(self):
        result = restart_service(hostname="h1", service_name="nginx")
        # The ID format is the contract the audit log relies on for
        # human searchability — restart-<host>-<service>.
        assert result["restart_id"] == "restart-h1-nginx"

    def test_handles_unicode_service_name(self):
        result = restart_service(hostname="h1", service_name="nginx-α")
        assert result["restart_id"] == "restart-h1-nginx-α"
        assert result["service_name"] == "nginx-α"


# ─────────────────────────────────────────────────────────────────────
# module surface
# ─────────────────────────────────────────────────────────────────────


def test_module_exports_match_tool_manifest():
    """__all__ must publish exactly the 4 tools the pack's tools.yaml
    binds via ``python_function``."""
    assert set(health_checks.__all__) == {
        "check_ping",
        "check_cpu",
        "notify_oncall",
        "restart_service",
    }
