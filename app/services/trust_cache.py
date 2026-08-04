import time
from collections import OrderedDict
from dataclasses import dataclass
from threading import Event, RLock
from typing import Callable, Generic, TypeVar


T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    value: T
    expires_at: float


class TTLCache(Generic[T]):
    def __init__(
        self,
        ttl_seconds: int,
        max_size: int,
    ):
        self.ttl_seconds = max(1, ttl_seconds)
        self.max_size = max(1, max_size)
        self.entries: OrderedDict[str, CacheEntry[T]] = (
            OrderedDict()
        )
        self.inflight: dict[str, Event] = {}
        self.lock = RLock()
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def get_or_compute(
        self,
        key: str,
        compute,
    ) -> tuple[T, bool]:
        while True:
            with self.lock:
                entry = self.entries.get(key)

                if (
                    entry is not None
                    and entry.expires_at
                    > time.monotonic()
                ):
                    self.hits += 1
                    self.entries.move_to_end(key)
                    return entry.value, True

                wait_event = self.inflight.get(key)

                if wait_event is None:
                    wait_event = Event()
                    self.inflight[key] = wait_event
                    self.misses += 1
                    should_compute = True
                else:
                    should_compute = False

            if not should_compute:
                wait_event.wait()
                continue

            try:
                value = compute()
            except Exception:
                with self.lock:
                    completed_event = (
                        self.inflight.pop(
                            key,
                            None,
                        )
                    )

                    if completed_event is not None:
                        completed_event.set()

                raise

            with self.lock:
                if (
                    key not in self.entries
                    and len(self.entries)
                    >= self.max_size
                ):
                    self.entries.popitem(
                        last=False
                    )
                    self.evictions += 1

                self.entries[key] = CacheEntry(
                    value=value,
                    expires_at=(
                        time.monotonic()
                        + self.ttl_seconds
                    ),
                )
                self.entries.move_to_end(key)

                completed_event = (
                    self.inflight.pop(
                        key,
                        None,
                    )
                )

                if completed_event is not None:
                    completed_event.set()

            return value, False


    def set(
        self,
        key: str,
        value: T,
    ) -> None:
        with self.lock:
            if (
                key not in self.entries
                and len(self.entries) >= self.max_size
            ):
                self.entries.popitem(last=False)
                self.evictions += 1

            self.entries[key] = CacheEntry(
                value=value,
                expires_at=(
                    time.monotonic()
                    + self.ttl_seconds
                ),
            )
            self.entries.move_to_end(key)

    def get_stale(
        self,
        key: str,
    ) -> T | None:
        with self.lock:
            entry = self.entries.get(key)

            if entry is None:
                return None

            self.entries.move_to_end(key)
            return entry.value

    def invalidate(
        self,
        key: str | None = None,
    ) -> None:
        with self.lock:
            if key is not None:
                self.entries.pop(key, None)
                return

            self.entries.clear()
            self.hits = 0
            self.misses = 0
            self.evictions = 0

    def stats(self) -> dict[str, int | float]:
        with self.lock:
            total = self.hits + self.misses
            hit_rate = (
                self.hits / total
                if total > 0
                else 0.0
            )

            return {
                "ttl_seconds": self.ttl_seconds,
                "max_size": self.max_size,
                "size": len(self.entries),
                "inflight": len(self.inflight),
                "hits": self.hits,
                "misses": self.misses,
                "evictions": self.evictions,
                "hit_rate": round(hit_rate, 4),
            }
