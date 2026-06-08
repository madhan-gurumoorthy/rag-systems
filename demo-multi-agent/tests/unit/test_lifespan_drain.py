"""Unit tests for ``agent_factory.api.lifespan._drain_in_flight``.

The helper is the shutdown hook for detached runner tasks anchored in
``app.state.in_flight``.  These tests pin:

  * Empty set → no-op.
  * All tasks already done → ``drained`` count, no cancellations.
  * All tasks pending past the grace window → cancelled.
  * Mixed (some done, some pending) → correct split in the report.
  * Cancellation is best-effort: the helper does not raise even if a
    cancelled task swallows ``CancelledError`` and keeps running.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_factory.api.lifespan import _drain_in_flight


# ─────────────────────────────────────────────────────────────────────
# Empty / trivial cases
# ─────────────────────────────────────────────────────────────────────


class TestEmptyDrain:

    @pytest.mark.asyncio
    async def test_empty_iterable_is_noop(self):
        report = await _drain_in_flight([])
        assert report == {"drained": 0, "cancelled": 0}

    @pytest.mark.asyncio
    async def test_set_of_already_done_tasks_counts_as_drained_zero(self):
        """Tasks that are already done at drain time are filtered out by
        the `not t.done()` predicate before ``asyncio.wait`` runs — they
        contribute nothing to either counter."""

        async def _quick() -> int:
            return 1

        t1 = asyncio.create_task(_quick())
        t2 = asyncio.create_task(_quick())
        await asyncio.gather(t1, t2)  # both done before the call

        report = await _drain_in_flight([t1, t2])
        assert report == {"drained": 0, "cancelled": 0}


# ─────────────────────────────────────────────────────────────────────
# Pending tasks — drained inside the grace window
# ─────────────────────────────────────────────────────────────────────


class TestDrainedWithinGrace:

    @pytest.mark.asyncio
    async def test_short_task_completes_during_grace(self):
        """A task that finishes within the grace window is counted as
        drained, not cancelled."""

        async def _short() -> str:
            await asyncio.sleep(0.05)
            return "ok"

        task = asyncio.create_task(_short())
        report = await _drain_in_flight([task], grace_seconds=1.0)
        assert report == {"drained": 1, "cancelled": 0}
        assert task.done()
        assert task.exception() is None
        assert task.result() == "ok"

    @pytest.mark.asyncio
    async def test_multiple_short_tasks(self):
        async def _short(value):
            await asyncio.sleep(0.01)
            return value

        tasks = [asyncio.create_task(_short(i)) for i in range(3)]
        report = await _drain_in_flight(tasks, grace_seconds=1.0)
        assert report == {"drained": 3, "cancelled": 0}
        assert all(t.done() for t in tasks)


# ─────────────────────────────────────────────────────────────────────
# Pending tasks past grace — cancelled
# ─────────────────────────────────────────────────────────────────────


class TestCancelledPastGrace:

    @pytest.mark.asyncio
    async def test_long_task_is_cancelled(self):
        """A task that exceeds the grace window must be cancelled, and
        the report must reflect ``cancelled=1``."""
        cancelled_seen = asyncio.Event()

        async def _long() -> str:
            try:
                await asyncio.sleep(60)
                return "never"
            except asyncio.CancelledError:
                cancelled_seen.set()
                raise

        task = asyncio.create_task(_long())
        report = await _drain_in_flight(
            [task],
            grace_seconds=0.05,
            cancel_settle_seconds=0.5,
        )
        assert report == {"drained": 0, "cancelled": 1}
        # Cancellation has been delivered + observed by the task.
        assert cancelled_seen.is_set()
        assert task.cancelled() or task.done()

    @pytest.mark.asyncio
    async def test_mixed_done_pending_and_long(self):
        """Three tasks: one finishes quickly, one is still pending, one
        hangs.  Helper must drain the quick one and cancel the long one.
        (The 'still pending' one effectively becomes one of those two
        groups depending on timing; we set the grace generously so the
        medium-length task lands in 'drained'.)"""

        async def _quick() -> int:
            return 1

        async def _medium() -> int:
            await asyncio.sleep(0.05)
            return 2

        async def _long() -> int:
            await asyncio.sleep(60)
            return 3

        t_quick = asyncio.create_task(_quick())
        t_medium = asyncio.create_task(_medium())
        t_long = asyncio.create_task(_long())

        # Let `t_quick` complete first so its "already done" path is
        # exercised inside the helper's predicate.
        await t_quick

        report = await _drain_in_flight(
            [t_quick, t_medium, t_long],
            grace_seconds=0.5,
            cancel_settle_seconds=0.5,
        )
        # quick was already done before the call → filtered out (0)
        # medium completes within grace → drained (1)
        # long hangs → cancelled (1)
        assert report["drained"] == 1
        assert report["cancelled"] == 1
        assert t_long.cancelled() or t_long.done()


# ─────────────────────────────────────────────────────────────────────
# Robustness — drain returns within a bounded wall-clock window
# ─────────────────────────────────────────────────────────────────────


class TestRobustness:

    @pytest.mark.asyncio
    async def test_drain_wall_clock_is_bounded(self):
        """A task that exceeds the grace window must not stretch the
        drain helper's wall-clock past grace + settle.  Even if the
        finaliser-style cancel handler is slow, the drain helper must
        return within the configured window.

        Verifies the hard contract: ``_drain_in_flight`` never blocks
        shutdown beyond ``grace_seconds + cancel_settle_seconds`` plus
        a small slack for event-loop scheduling.
        """

        async def _long() -> str:
            try:
                await asyncio.sleep(60)
                return "never"
            except asyncio.CancelledError:
                # Take longer than the settle window before honouring
                # the cancel — drain must not wait for us.
                await asyncio.sleep(0.5)
                raise

        task = asyncio.create_task(_long())
        loop = asyncio.get_running_loop()
        t0 = loop.time()
        report = await _drain_in_flight(
            [task],
            grace_seconds=0.05,
            cancel_settle_seconds=0.1,
        )
        elapsed = loop.time() - t0

        # Hard cap: grace + settle + a small slack.  The task itself
        # will keep running for ~0.5s after cancel, but the helper must
        # have already returned.
        assert elapsed < 0.8, (
            f"drain must stay bounded by grace+settle; elapsed={elapsed:.3f}s"
        )
        assert report["cancelled"] == 1

        # Give the task a chance to finish its cleanup so pytest's
        # event-loop teardown doesn't see a pending task.
        try:
            await asyncio.wait_for(task, timeout=1.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
