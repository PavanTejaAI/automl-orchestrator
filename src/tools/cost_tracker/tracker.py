import asyncio
import time
from collections import defaultdict
from typing import Optional
from src.utils import logger


class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: int = 60):
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def check(self, user_id: str) -> bool:
        async with self._lock:
            now = time.time()
            window_start = now - self._window_seconds
            self._requests[user_id] = [t for t in self._requests[user_id] if t > window_start]
            if len(self._requests[user_id]) >= self._max_requests:
                return False
            self._requests[user_id].append(now)
            return True

    async def remaining(self, user_id: str) -> int:
        async with self._lock:
            now = time.time()
            window_start = now - self._window_seconds
            self._requests[user_id] = [t for t in self._requests[user_id] if t > window_start]
            return max(0, self._max_requests - len(self._requests[user_id]))


class CircuitBreaker:
    def __init__(self, threshold: int, timeout: int):
        self._threshold = threshold
        self._timeout = timeout
        self._failures: int = 0
        self._last_failure: float = 0
        self._state: str = "closed"
        self._lock = asyncio.Lock()

    async def can_execute(self) -> bool:
        async with self._lock:
            if self._state == "closed":
                return True
            if self._state == "open":
                if time.time() - self._last_failure >= self._timeout:
                    self._state = "half-open"
                    return True
                return False
            return True

    async def record_success(self) -> None:
        async with self._lock:
            self._failures = 0
            self._state = "closed"

    async def record_failure(self) -> None:
        async with self._lock:
            self._failures += 1
            self._last_failure = time.time()
            if self._failures >= self._threshold:
                self._state = "open"
                logger.warning("Circuit breaker opened", failures=self._failures)

    @property
    def state(self) -> str:
        return self._state


_rate_limiter: RateLimiter | None = None
_circuit_breaker: CircuitBreaker | None = None


def get_rate_limiter(max_requests: int = 30, window_seconds: int = 60) -> RateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter(max_requests, window_seconds)
    return _rate_limiter


def get_circuit_breaker(threshold: int = 5, timeout: int = 60) -> CircuitBreaker:
    global _circuit_breaker
    if _circuit_breaker is None:
        _circuit_breaker = CircuitBreaker(threshold, timeout)
    return _circuit_breaker
