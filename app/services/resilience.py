import time
from collections.abc import Callable
from typing import TypeVar

from app.services.monitoring import log_event


T = TypeVar("T")

RETRYABLE_EXCEPTIONS = (
    RuntimeError,
    TimeoutError,
    ConnectionError,
)


def retry_operation(
    operation: Callable[[], T],
    operation_name: str,
    attempts: int = 3,
    base_delay_seconds: float = 0.2,
    max_delay_seconds: float = 2.0,
    sleep_fn: Callable[[float], None] | None = None,
) -> T:
    attempts = max(1, attempts)
    base_delay_seconds = max(
        0.0,
        base_delay_seconds,
    )
    max_delay_seconds = max(
        base_delay_seconds,
        max_delay_seconds,
    )
    sleeper = sleep_fn or time.sleep

    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except RETRYABLE_EXCEPTIONS as exc:
            if attempt >= attempts:
                log_event(
                    "provider_operation_failed",
                    operation=operation_name,
                    attempts=attempt,
                    error_type=type(exc).__name__,
                )
                raise

            delay_seconds = min(
                base_delay_seconds
                * (2 ** (attempt - 1)),
                max_delay_seconds,
            )

            log_event(
                "provider_retry_scheduled",
                operation=operation_name,
                attempt=attempt,
                next_attempt=attempt + 1,
                delay_seconds=delay_seconds,
                error_type=type(exc).__name__,
            )

            sleeper(delay_seconds)

    raise RuntimeError(
        f"{operation_name} did not complete."
    )
