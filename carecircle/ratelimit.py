"""
ratelimit.py
------------
A simple, thread-safe sliding-window rate limiter.

PURPOSE: Prevent the app from spamming the Groq / Weather APIs. We enforce a
hard ceiling (default 10 calls per 60 seconds, configurable). When the limit is
reached, calls are rejected gracefully and the agents fall back to deterministic
demo output instead of hammering the API — protecting both cost and rate limits.
"""

import threading
import time
from collections import deque
from .config import config


class RateLimiter:
    def __init__(self, max_calls: int, window_seconds: float = 60.0) -> None:
        self.max_calls = max_calls
        self.window = window_seconds
        self._calls: deque[float] = deque()
        self._lock = threading.Lock()

    def allow(self) -> bool:
        """Return True if a call is permitted right now, and record it.
        Returns False if the per-minute ceiling has been hit."""
        now = time.monotonic()
        with self._lock:
            # Drop timestamps older than the window.
            while self._calls and (now - self._calls[0]) > self.window:
                self._calls.popleft()
            if len(self._calls) >= self.max_calls:
                return False
            self._calls.append(now)
            return True

    def remaining(self) -> int:
        now = time.monotonic()
        with self._lock:
            while self._calls and (now - self._calls[0]) > self.window:
                self._calls.popleft()
            return max(0, self.max_calls - len(self._calls))


# Shared, app-wide limiter for all outbound LLM/API calls.
api_limiter = RateLimiter(max_calls=config.MAX_API_CALLS_PER_MINUTE, window_seconds=60.0)