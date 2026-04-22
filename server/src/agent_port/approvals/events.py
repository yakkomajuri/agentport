"""In-process pub/sub for tool-approval decisions.

When a `/approve-once`, `/allow-tool`, or `/deny` endpoint commits a decision,
it calls `notify_decision(request_id, status)`. Any coroutine parked on
`wait_for_decision(request_id, timeout)` wakes up and returns the status.

This lets the `agentport__await_approval` meta-tool long-poll for a decision
without the human needing to hop back to chat. Single-process only — when we
scale to multiple workers, swap the backend here for Postgres LISTEN/NOTIFY
or Redis pubsub; the public functions stay the same.
"""

import asyncio
import uuid
from typing import Callable, Literal

DecisionStatus = Literal["approved", "denied", "timeout"]

# One Event per in-flight request_id. Concurrent waiters for the same UUID
# share the Event so notify wakes them all. A refcount tracks how many are
# parked so we only drop the entry once everyone has unregistered.
_events: dict[uuid.UUID, asyncio.Event] = {}
_statuses: dict[uuid.UUID, str] = {}
_refcounts: dict[uuid.UUID, int] = {}
_lock = asyncio.Lock()


async def _register_waiter(request_id: uuid.UUID) -> asyncio.Event:
    async with _lock:
        event = _events.get(request_id)
        if event is None:
            event = asyncio.Event()
            _events[request_id] = event
            _refcounts[request_id] = 0
        _refcounts[request_id] += 1
        return event


async def _unregister_waiter(request_id: uuid.UUID) -> None:
    async with _lock:
        if request_id not in _refcounts:
            return
        _refcounts[request_id] -= 1
        if _refcounts[request_id] <= 0:
            _events.pop(request_id, None)
            _statuses.pop(request_id, None)
            _refcounts.pop(request_id, None)


async def wait_for_decision(
    request_id: uuid.UUID,
    timeout: float,
    pre_check: Callable[[], str | None] | None = None,
) -> DecisionStatus:
    """Wait up to `timeout` seconds for a decision on `request_id`.

    `pre_check` is an optional callable invoked *after* registering as a
    waiter but *before* blocking on the event. It should return the current
    persisted status ("approved", "denied", "pending", or None if unknown).
    If it returns "approved" or "denied", this short-circuits — that closes
    the race where the decision commits and notifies between the caller's
    own DB read and entry into this function.
    """
    event = await _register_waiter(request_id)
    try:
        if pre_check is not None:
            current = pre_check()
            if current == "approved":
                return "approved"
            if current == "denied":
                return "denied"

        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            return "timeout"

        status = _statuses.get(request_id)
        if status == "denied":
            return "denied"
        return "approved"
    finally:
        await _unregister_waiter(request_id)


def notify_decision(request_id: uuid.UUID, status: str) -> None:
    """Record the decision and wake any waiters.

    A no-op when no waiters are registered for this id. Callers must invoke
    this *after* the DB commit so a woken waiter's subsequent DB read sees
    the persisted decision.
    """
    event = _events.get(request_id)
    if event is None:
        return
    _statuses[request_id] = status
    event.set()
