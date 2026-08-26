import threading
import time
from collections import defaultdict, deque


class RateLimitExceeded(RuntimeError):
    def __init__(self, retry_after):
        self.retry_after = max(int(retry_after), 1)
        super().__init__(f"rate limit exceeded, retry after {self.retry_after}s")


class SlidingWindowRateLimiter:
    def __init__(self):
        self._events = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key, limit, window_seconds):
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit:
                raise RateLimitExceeded(window_seconds - (now - events[0]))
            events.append(now)


auth_rate_limiter = SlidingWindowRateLimiter()
