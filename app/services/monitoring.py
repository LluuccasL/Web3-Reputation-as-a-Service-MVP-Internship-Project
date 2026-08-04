import json
import logging
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from threading import Lock
from typing import Any


class JSONLogFormatter(logging.Formatter):
    def format(
        self,
        record: logging.LogRecord,
    ) -> str:
        payload = {
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": getattr(
                record,
                "event_name",
                record.getMessage(),
            ),
        }

        event_data = getattr(
            record,
            "event_data",
            {},
        )

        if isinstance(event_data, dict):
            payload.update(event_data)

        if record.exc_info:
            payload["exception"] = (
                self.formatException(record.exc_info)
            )

        return json.dumps(
            payload,
            default=str,
            sort_keys=True,
        )


def create_monitoring_logger() -> logging.Logger:
    logger = logging.getLogger(
        "web3_trust.monitoring"
    )

    if not logger.handlers:
        handler = logging.StreamHandler(
            sys.stdout
        )
        handler.setFormatter(JSONLogFormatter())
        logger.addHandler(handler)

    level_name = os.getenv(
        "LOG_LEVEL",
        "INFO",
    ).upper()

    logger.setLevel(
        getattr(
            logging,
            level_name,
            logging.INFO,
        )
    )
    logger.propagate = False

    return logger


monitoring_logger = create_monitoring_logger()


def log_event(
    event_name: str,
    level: int = logging.INFO,
    **fields: Any,
) -> None:
    monitoring_logger.log(
        level,
        event_name,
        extra={
            "event_name": event_name,
            "event_data": fields,
        },
    )


class RequestMetrics:
    def __init__(self):
        self.lock = Lock()
        self.reset()

    def reset(self) -> None:
        with self.lock:
            self.started_at = time.monotonic()
            self.total_requests = 0
            self.active_requests = 0
            self.errors = 0
            self.total_latency_ms = 0.0
            self.routes = defaultdict(
                lambda: {
                    "requests": 0,
                    "errors": 0,
                    "total_latency_ms": 0.0,
                    "max_latency_ms": 0.0,
                }
            )

    def begin(self) -> None:
        with self.lock:
            self.active_requests += 1

    def finish(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
    ) -> None:
        key = (method, path)

        with self.lock:
            self.active_requests = max(
                0,
                self.active_requests - 1,
            )
            self.total_requests += 1
            self.total_latency_ms += duration_ms

            route = self.routes[key]
            route["requests"] += 1
            route[
                "total_latency_ms"
            ] += duration_ms
            route["max_latency_ms"] = max(
                route["max_latency_ms"],
                duration_ms,
            )

            if status_code >= 400:
                self.errors += 1
                route["errors"] += 1

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            average_latency_ms = (
                self.total_latency_ms
                / self.total_requests
                if self.total_requests
                else 0.0
            )

            routes = []

            for (
                method,
                path,
            ), values in sorted(
                self.routes.items()
            ):
                requests = values["requests"]

                routes.append(
                    {
                        "method": method,
                        "path": path,
                        "requests": requests,
                        "errors": values["errors"],
                        "average_latency_ms": round(
                            values[
                                "total_latency_ms"
                            ]
                            / requests,
                            2,
                        ),
                        "max_latency_ms": round(
                            values[
                                "max_latency_ms"
                            ],
                            2,
                        ),
                    }
                )

            return {
                "uptime_seconds": round(
                    time.monotonic()
                    - self.started_at,
                    2,
                ),
                "total_requests": (
                    self.total_requests
                ),
                "active_requests": (
                    self.active_requests
                ),
                "errors": self.errors,
                "average_latency_ms": round(
                    average_latency_ms,
                    2,
                ),
                "routes": routes,
            }


request_metrics = RequestMetrics()
