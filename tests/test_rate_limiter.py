import time

import pytest

from agent.rate_limiter import TokenBucketRateLimiter


def test_try_acquire_consumes_tokens_up_to_capacity():
    limiter = TokenBucketRateLimiter(rate_per_second=10, burst=10)
    for _ in range(10):
        assert limiter.try_acquire() is True
    assert limiter.try_acquire() is False


def test_try_acquire_refills_over_time():
    limiter = TokenBucketRateLimiter(rate_per_second=100, burst=1)
    assert limiter.try_acquire() is True
    assert limiter.try_acquire() is False
    time.sleep(0.02)  # 100/s => ~2 tokens refilled
    assert limiter.try_acquire() is True


def test_acquire_blocks_until_available():
    limiter = TokenBucketRateLimiter(rate_per_second=50, burst=1)
    limiter.acquire()
    start = time.monotonic()
    limiter.acquire()
    elapsed = time.monotonic() - start
    assert elapsed >= 0.015  # ~1/50s, allow scheduling slack


def test_rejects_nonpositive_rate():
    with pytest.raises(ValueError):
        TokenBucketRateLimiter(rate_per_second=0)
