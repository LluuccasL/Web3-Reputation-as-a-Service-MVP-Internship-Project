import hashlib
import math
import os
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from fastapi import Response, Security

from app.errors import APIError
from app.security.api_key import require_api_key


DEFAULT_REQUEST_LIMIT = 60
DEFAULT_WINDOW_SECONDS = 60


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    reset_after: int


class InMemoryRateLimiter:
    """
    Single-server, in-memory rate limiter.

    Week 7 can replace this storage with Redis without changing the routes.
    """

    def __init__(self):
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    @staticmethod
    def fingerprint(api_key: str) -> str:
        """
        Hash the key so raw API keys are never stored in rate-limit buckets.
        """
        return hashlib.sha256(
            api_key.encode("utf-8")
        ).hexdigest()

    def clear(self) -> None:
        """Clear all rate-limit state. Primarily useful for tests."""
        with self._lock:
            self._requests.clear()

    def check(
        self,
        api_key: str,
        limit: int,
        window_seconds: int,
    ) -> RateLimitDecision:
        now = time.monotonic()
        key_hash = self.fingerprint(api_key)

        with self._lock:
            request_times = self._requests[key_hash]
            cutoff = now - window_seconds

            while request_times and request_times[0] <= cutoff:
                request_times.popleft()

            if len(request_times) >= limit:
                reset_after = max(
                    1,
                    math.ceil(
                        window_seconds
                        - (now - request_times[0])
                    ),
                )

                return RateLimitDecision(
                    allowed=False,
                    limit=limit,
                    remaining=0,
                    reset_after=reset_after,
                )

            request_times.append(now)

            remaining = max(
                0,
                limit - len(request_times),
            )

            reset_after = max(
                1,
                math.ceil(
                    window_seconds
                    - (now - request_times[0])
                ),
            )

            return RateLimitDecision(
                allowed=True,
                limit=limit,
                remaining=remaining,
                reset_after=reset_after,
            )


rate_limiter = InMemoryRateLimiter()


def read_positive_integer(
    environment_name: str,
    default: int,
) -> int:
    raw_value = os.getenv(
        environment_name,
        str(default),
    )

    try:
        value = int(raw_value)
    except ValueError as exc:
        raise APIError(
            status_code=500,
            code="RATE_LIMIT_CONFIG_ERROR",
            message="The rate-limit configuration is invalid.",
        ) from exc

    if value < 1:
        raise APIError(
            status_code=500,
            code="RATE_LIMIT_CONFIG_ERROR",
            message="The rate-limit configuration is invalid.",
        )

    return value


def enforce_rate_limit(
    response: Response,
    api_key: str = Security(require_api_key),
) -> str:
    """
    Authenticate the API key and enforce its request limit.
    """
    limit = read_positive_integer(
        "RATE_LIMIT_REQUESTS",
        DEFAULT_REQUEST_LIMIT,
    )

    window_seconds = read_positive_integer(
        "RATE_LIMIT_WINDOW_SECONDS",
        DEFAULT_WINDOW_SECONDS,
    )

    decision = rate_limiter.check(
        api_key=api_key,
        limit=limit,
        window_seconds=window_seconds,
    )

    response.headers["X-RateLimit-Limit"] = str(
        decision.limit
    )
    response.headers["X-RateLimit-Remaining"] = str(
        decision.remaining
    )
    response.headers["X-RateLimit-Reset"] = str(
        decision.reset_after
    )

    if not decision.allowed:
        raise APIError(
            status_code=429,
            code="RATE_LIMIT_EXCEEDED",
            message=(
                "Too many requests. Wait before trying again."
            ),
            headers={
                "Retry-After": str(decision.reset_after),
                "X-RateLimit-Limit": str(decision.limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(
                    decision.reset_after
                ),
            },
        )

    return api_key
