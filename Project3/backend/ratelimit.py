"""In-process request throttling for the public auth endpoints.

`/api/auth/login` and `/api/auth/register` are anonymous and each one runs a
bcrypt operation (12 rounds), so unthrottled requests are both an online
password-guessing channel and a cheap way to burn CPU.  This module provides
the limits the handlers apply before doing that work.

Scope and limits of this approach
---------------------------------
The counters live in the memory of one Functions worker process.  When the
app scales out, each instance counts separately, and a restart clears them.
That still bounds what any single instance will spend on one client or one
account, which is the cost this guards against.  A global limit would need a
shared store or a gateway (Front Door / API Management) in front of the app.
"""
import threading
import time
from collections import deque


class SlidingWindowLimiter:
    """Allow at most `limit` events per key within `window` seconds."""

    def __init__(self, limit: int, window: float, max_keys: int = 10_000):
        self.limit = limit
        self.window = window
        # Bounds memory when many distinct keys (IPs, emails) are seen.
        self.max_keys = max_keys
        self._events: dict[str, deque] = {}
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float):
        events = self._events.get(key)
        if events is None:
            return None
        cutoff = now - self.window
        while events and events[0] <= cutoff:
            events.popleft()
        if not events:
            del self._events[key]
            return None
        return events

    def _evict_if_full(self, now: float):
        if len(self._events) < self.max_keys:
            return
        for key in list(self._events):
            self._prune(key, now)
        # Still full: drop the keys whose newest event is oldest.
        overflow = len(self._events) - self.max_keys + 1
        if overflow > 0:
            stalest = sorted(self._events, key=lambda k: self._events[k][-1])
            for key in stalest[:overflow]:
                del self._events[key]

    def retry_after(self, key: str, now: float | None = None) -> float:
        """Seconds until `key` may act again; 0 when it may act now."""
        now = time.monotonic() if now is None else now
        with self._lock:
            events = self._prune(key, now)
            if events is None or len(events) < self.limit:
                return 0.0
            return max(0.0, events[0] + self.window - now)

    def record(self, key: str, now: float | None = None) -> None:
        """Count one event for `key`."""
        now = time.monotonic() if now is None else now
        with self._lock:
            events = self._prune(key, now)
            if events is None:
                self._evict_if_full(now)
                events = self._events[key] = deque()
            events.append(now)

    def hit(self, key: str, now: float | None = None) -> float:
        """Check and count in one step.

        Returns 0 and records the event when allowed; otherwise returns the
        seconds to wait and records nothing, so a client that keeps retrying
        while blocked does not extend its own block.
        """
        now = time.monotonic() if now is None else now
        with self._lock:
            events = self._prune(key, now)
            if events is not None and len(events) >= self.limit:
                return max(0.0, events[0] + self.window - now)
            if events is None:
                self._evict_if_full(now)
                events = self._events[key] = deque()
            events.append(now)
            return 0.0

    def reset(self, key: str) -> None:
        with self._lock:
            self._events.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._events.clear()


def client_ip(headers) -> str:
    """Best-effort client address for an Azure Functions HTTP request.

    The Azure front end appends the address it received the connection from
    to X-Forwarded-For, so the right-most entry is the one a client cannot
    forge; anything to its left came from the request itself.  Entries may
    carry a port ("203.0.113.7:51234", "[2001:db8::1]:443").
    """
    raw = headers.get("x-forwarded-for") or headers.get("X-Forwarded-For") or ""
    entry = raw.split(",")[-1].strip()
    if not entry:
        return "unknown"
    if entry.startswith("["):  # [IPv6]:port
        return entry[1:].split("]", 1)[0] or "unknown"
    if entry.count(":") == 1:  # IPv4:port
        return entry.split(":", 1)[0]
    return entry
