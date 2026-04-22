"""Unit tests for approvals/events.py — the in-process pub/sub that wakes
agentport__await_approval when a human commits a decision."""

import asyncio
import uuid

import pytest

from agent_port.approvals import events


@pytest.fixture(autouse=True)
def reset_events_state():
    """Guarantee a clean module state between tests — these dicts are singletons."""
    events._events.clear()
    events._statuses.clear()
    events._refcounts.clear()
    yield
    events._events.clear()
    events._statuses.clear()
    events._refcounts.clear()


@pytest.mark.anyio
async def test_wait_returns_approved_when_notified():
    request_id = uuid.uuid4()

    async def notifier():
        # Give the waiter a tick to register before we fire.
        await asyncio.sleep(0.01)
        events.notify_decision(request_id, "approved")

    notify_task = asyncio.create_task(notifier())
    status = await events.wait_for_decision(request_id, timeout=1.0)
    await notify_task

    assert status == "approved"
    # Cleanup: no stale entries left behind.
    assert request_id not in events._events
    assert request_id not in events._statuses
    assert request_id not in events._refcounts


@pytest.mark.anyio
async def test_wait_returns_denied_when_notified():
    request_id = uuid.uuid4()

    async def notifier():
        await asyncio.sleep(0.01)
        events.notify_decision(request_id, "denied")

    notify_task = asyncio.create_task(notifier())
    status = await events.wait_for_decision(request_id, timeout=1.0)
    await notify_task

    assert status == "denied"
    assert request_id not in events._events
    assert request_id not in events._statuses


@pytest.mark.anyio
async def test_wait_times_out_when_no_notify():
    request_id = uuid.uuid4()

    status = await events.wait_for_decision(request_id, timeout=0.05)
    assert status == "timeout"
    # Cleanup runs even on timeout.
    assert request_id not in events._events
    assert request_id not in events._refcounts


@pytest.mark.anyio
async def test_pre_check_short_circuits_when_already_approved():
    request_id = uuid.uuid4()

    # Pre-check says "already decided" — no notifier fires, but we should
    # return immediately instead of hanging on the event.
    status = await events.wait_for_decision(request_id, timeout=5.0, pre_check=lambda: "approved")
    assert status == "approved"
    # Cleanup still happens.
    assert request_id not in events._events


@pytest.mark.anyio
async def test_pre_check_short_circuits_when_already_denied():
    request_id = uuid.uuid4()

    status = await events.wait_for_decision(request_id, timeout=5.0, pre_check=lambda: "denied")
    assert status == "denied"
    assert request_id not in events._events


@pytest.mark.anyio
async def test_pre_check_pending_falls_through_to_wait():
    request_id = uuid.uuid4()

    async def notifier():
        await asyncio.sleep(0.01)
        events.notify_decision(request_id, "approved")

    notify_task = asyncio.create_task(notifier())
    status = await events.wait_for_decision(request_id, timeout=1.0, pre_check=lambda: "pending")
    await notify_task

    assert status == "approved"


@pytest.mark.anyio
async def test_concurrent_waiters_both_wake_on_single_notify():
    request_id = uuid.uuid4()

    async def waiter():
        return await events.wait_for_decision(request_id, timeout=1.0)

    task_a = asyncio.create_task(waiter())
    task_b = asyncio.create_task(waiter())

    # Let both waiters park before notifying.
    await asyncio.sleep(0.02)
    events.notify_decision(request_id, "approved")

    results = await asyncio.gather(task_a, task_b)
    assert results == ["approved", "approved"]

    # Full cleanup only after the last waiter drops.
    assert request_id not in events._events
    assert request_id not in events._refcounts


@pytest.mark.anyio
async def test_notify_with_no_waiters_is_noop():
    """Firing a decision for a request nobody is waiting on does nothing and leaks nothing."""
    request_id = uuid.uuid4()
    events.notify_decision(request_id, "approved")
    assert request_id not in events._events
    assert request_id not in events._statuses


@pytest.mark.anyio
async def test_cancelled_waiter_cleans_up_refcount():
    """A cancelled wait_for_decision must decrement the refcount so the entry isn't leaked."""
    request_id = uuid.uuid4()

    async def waiter():
        await events.wait_for_decision(request_id, timeout=10.0)

    task = asyncio.create_task(waiter())
    # Let it register.
    await asyncio.sleep(0.01)
    assert events._refcounts.get(request_id) == 1

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # Cleanup on cancel.
    assert request_id not in events._events
    assert request_id not in events._refcounts
