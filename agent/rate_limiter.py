"""Token-bucket rate limiter.

Pionex US's Open API caps requests per source IP, shared across every
namespace (Fiat/Wallet/Institution/Trading) rather than per endpoint. A
single bucket instance must therefore be shared by every call the process
makes to the API, not one bucket per endpoint or per client instance.
"""
from __future__ import annotations

import threading
import time


class TokenBucketRateLimiter:
    def __init__(self, rate_per_second: float, burst: float | None = None) -> None:
        if rate_per_second <= 0:
            raise ValueError("rate_per_second must be positive")
        self._rate = rate_per_second
        self._capacity = burst if burst is not None else rate_per_second
        self._tokens = self._capacity
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._last_refill = now
        self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)

    def acquire(self, tokens: float = 1.0) -> None:
        """Block until `tokens` are available, then consume them."""
        while True:
            with self._lock:
                self._refill()
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                deficit = tokens - self._tokens
                wait_time = deficit / self._rate
            time.sleep(wait_time)

    def try_acquire(self, tokens: float = 1.0) -> bool:
        """Non-blocking variant: consume and return True, or return False."""
        with self._lock:
            self._refill()
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False
