"""In-memory per-IP sliding-window rate limiting for auth endpoints.

Single-process self-hosted installs can lean on this directly. Multi-worker
deployments should treat each worker's counter as independent — the effective
limit becomes workers * max_requests, which is still a strong first-layer
brake against brute force. A distributed deployment should replace the store
with Redis.
"""

import time
from collections import deque

from fastapi import HTTPException, Request

# Login-failure policy — exposed as module constants so callers and tests
# can reference the numbers directly alongside the configured limiter.
IP_WINDOW_SECONDS = 15 * 60
IP_MAX_ATTEMPTS_PER_WINDOW = 20

# Per-account lockout policy (applied in user_auth.login).
ACCOUNT_LOCKOUT_THRESHOLD = 10
ACCOUNT_LOCKOUT_SECONDS = 5 * 60


class IPRateLimiter:
    """Sliding-window rate limit keyed by client IP.

    Two usage modes:

    - FastAPI dependency: ``Depends(limiter)`` or
      ``dependencies=[Depends(limiter)]`` — checks AND records a hit before
      the endpoint body runs. Fits endpoints where every call counts equally
      (email verification, forgot-password).

    - Manual: ``limiter.check(ip)`` / ``limiter.record(ip)`` /
      ``limiter.reset_ip(ip)`` — lets the caller decide when a hit counts
      (e.g. only on failed password checks) and when to clear state
      (e.g. on a successful login).

    Instances register themselves so tests can reset all limiter state
    between cases via ``reset_all_rate_limiters()``.
    """

    def __init__(self, *, name: str, max_requests: int, window_seconds: float):
        self.name = name
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = {}
        _REGISTRY.append(self)

    def _client_ip(self, request: Request) -> str:
        if request.client and request.client.host:
            return request.client.host
        return "unknown"

    def _prune(self, ip: str, now: float) -> deque[float]:
        cutoff = now - self.window_seconds
        hits = self._hits.setdefault(ip, deque())
        while hits and hits[0] < cutoff:
            hits.popleft()
        return hits

    async def __call__(self, request: Request) -> None:
        ip = self._client_ip(request)
        now = time.monotonic()
        hits = self._prune(ip, now)
        if len(hits) >= self.max_requests:
            retry_after = max(1, int(self.window_seconds - (now - hits[0])))
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Try again shortly.",
                headers={"Retry-After": str(retry_after)},
            )
        hits.append(now)

    def check(self, ip: str) -> int:
        """Return 0 if another request is allowed from this IP, else a
        Retry-After value in seconds. Does NOT record a hit.
        """
        now = time.monotonic()
        hits = self._prune(ip, now)
        if len(hits) >= self.max_requests:
            return max(1, int(self.window_seconds - (now - hits[0])))
        return 0

    def record(self, ip: str) -> None:
        """Record one hit from this IP."""
        now = time.monotonic()
        hits = self._prune(ip, now)
        hits.append(now)

    def reset_ip(self, ip: str) -> None:
        """Clear this IP's hit log (e.g. after a successful login)."""
        self._hits.pop(ip, None)

    def reset(self) -> None:
        self._hits.clear()


_REGISTRY: list[IPRateLimiter] = []


def reset_all_rate_limiters() -> None:
    for limiter in _REGISTRY:
        limiter.reset()


verify_email_code_ip_limiter = IPRateLimiter(
    name="verify-email-code",
    max_requests=10,
    window_seconds=60,
)

verify_email_ip_limiter = IPRateLimiter(
    name="verify-email",
    max_requests=10,
    window_seconds=60,
)

login_failure_ip_limiter = IPRateLimiter(
    name="login-failure",
    max_requests=IP_MAX_ATTEMPTS_PER_WINDOW,
    window_seconds=IP_WINDOW_SECONDS,
)
