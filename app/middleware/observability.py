import logging
import time
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.services.monitoring import (
    log_event,
    request_metrics,
)


class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next,
    ):
        # Reuse an ID created by another middleware when available.
        request_id = getattr(
            request.state,
            "request_id",
            None,
        )

        if request_id is None:
            request_id = str(uuid4())
            request.state.request_id = request_id

        started_at = time.perf_counter()
        track_metrics = (
            request.url.path
            != "/performance/metrics"
        )

        if track_metrics:
            request_metrics.begin()

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            duration_ms = (
                time.perf_counter() - started_at
            ) * 1000
            path = self._route_path(request)

            # An inner middleware may have assigned the
            # canonical request ID.
            request_id = getattr(
                request.state,
                "request_id",
                request_id,
            )

            if track_metrics:
                request_metrics.finish(
                    request.method,
                    path,
                    500,
                    duration_ms,
                )

            log_event(
                "request_completed",
                level=logging.ERROR,
                request_id=request_id,
                method=request.method,
                path=path,
                status_code=500,
                duration_ms=round(
                    duration_ms,
                    2,
                ),
            )

            raise

        duration_ms = (
            time.perf_counter() - started_at
        ) * 1000
        path = self._route_path(request)

        # Always adopt the ID ultimately used by the existing
        # request-logging and error-handling middleware.
        request_id = getattr(
            request.state,
            "request_id",
            request_id,
        )

        if track_metrics:
            request_metrics.finish(
                request.method,
                path,
                status_code,
                duration_ms,
            )

        if status_code >= 500:
            log_level = logging.ERROR
        elif status_code >= 400:
            log_level = logging.WARNING
        else:
            log_level = logging.INFO

        log_event(
            "request_completed",
            level=log_level,
            request_id=request_id,
            method=request.method,
            path=path,
            status_code=status_code,
            duration_ms=round(
                duration_ms,
                2,
            ),
        )

        response.headers["X-Request-ID"] = request_id

        return response

    @staticmethod
    def _route_path(
        request: Request,
    ) -> str:
        route = request.scope.get("route")
        route_path = getattr(
            route,
            "path",
            None,
        )

        return route_path or "unmatched"
