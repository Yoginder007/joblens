"""
Minimal in-process rate limiting (stdlib only, like the rest of core).

Fixed-window per client IP. Deliberately simple: the deploy target is a single
free-tier process, so shared-state backends (Redis) would be dead weight; on a
multi-worker deploy each worker enforces its own window, which still bounds
abuse per process.

Applied to the expensive/abusable endpoints: login & signup (scrypt is
CPU-heavy *by design*, so unthrottled attempts double as a CPU DoS), guest
registration (token rotation), and résumé upload.
"""
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.core.config import get_settings


class RateLimiter:
    """FastAPI dependency: ``Depends(RateLimiter(10, 60))`` = 10 calls/min/IP."""

    def __init__(self, limit: int, window_s: float, name: str = ""):
        self.limit = limit
        self.window_s = window_s
        self.name = name
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def __call__(self, request: Request) -> None:
        if not get_settings().RATE_LIMIT_ENABLED:
            return
        client = request.client.host if request.client else "unknown"
        now = time.monotonic()
        with self._lock:
            q = self._hits[client]
            while q and now - q[0] > self.window_s:
                q.popleft()
            if len(q) >= self.limit:
                retry_after = max(1, int(self.window_s - (now - q[0])))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests — please slow down.",
                    headers={"Retry-After": str(retry_after)},
                )
            q.append(now)
            # Opportunistic cleanup so idle clients don't accumulate forever.
            if len(self._hits) > 10_000:
                stale = [k for k, v in self._hits.items() if not v or now - v[-1] > self.window_s]
                for k in stale:
                    del self._hits[k]


# Shared instances (state lives with the instance, so routes must reuse these).
auth_limiter = RateLimiter(10, 60.0, name="auth")       # login/signup/guest-register
upload_limiter = RateLimiter(6, 60.0, name="upload")    # résumé uploads
