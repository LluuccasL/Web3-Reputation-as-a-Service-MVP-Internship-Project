from fastapi import (
    APIRouter,
    Depends,
)
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.rate_limit import (
    enforce_rate_limit,
)
from app.models import BackgroundJob
from app.openapi import protected_responses
from app.routers.trust import (
    get_trust_cache_stats,
)
from app.schemas_performance import (
    BackgroundJobMetricsResponse,
    CacheStatsResponse,
    MonitoringResponse,
    RequestMetricsResponse,
)
from app.services.monitoring import (
    request_metrics,
)


router = APIRouter(
    prefix="/performance",
    tags=["performance"],
)


@router.get(
    "/cache",
    response_model=CacheStatsResponse,
    summary="Get trust-cache statistics",
    description=(
        "Returns configured cache limits plus hit, miss, eviction, and "
        "in-flight request statistics."
    ),
    responses=protected_responses(
        success_description="Current trust-cache statistics.",
    ),
)
def get_cache_performance(
    _api_key: str = Depends(
        enforce_rate_limit
    ),
) -> CacheStatsResponse:
    return CacheStatsResponse(
        **get_trust_cache_stats()
    )


@router.get(
    "/metrics",
    response_model=MonitoringResponse,
    summary="Get service monitoring metrics",
    description=(
        "Returns uptime, route latency, errors, cache performance, and "
        "background-job counts."
    ),
    responses=protected_responses(
        success_description="Current service monitoring snapshot.",
    ),
)
def get_monitoring_metrics(
    db: Session = Depends(get_db),
    _api_key: str = Depends(
        enforce_rate_limit
    ),
) -> MonitoringResponse:
    request_snapshot = (
        request_metrics.snapshot()
    )

    rows = (
        db.query(
            BackgroundJob.status,
            func.count(BackgroundJob.id),
        )
        .group_by(BackgroundJob.status)
        .all()
    )

    job_counts = {
        status: count
        for status, count in rows
    }

    return MonitoringResponse(
        uptime_seconds=request_snapshot[
            "uptime_seconds"
        ],
        requests=RequestMetricsResponse(
            total_requests=request_snapshot[
                "total_requests"
            ],
            active_requests=request_snapshot[
                "active_requests"
            ],
            errors=request_snapshot["errors"],
            average_latency_ms=request_snapshot[
                "average_latency_ms"
            ],
            routes=request_snapshot["routes"],
        ),
        cache=CacheStatsResponse(
            **get_trust_cache_stats()
        ),
        background_jobs=(
            BackgroundJobMetricsResponse(
                total=sum(job_counts.values()),
                queued=job_counts.get(
                    "queued",
                    0,
                ),
                running=job_counts.get(
                    "running",
                    0,
                ),
                completed=job_counts.get(
                    "completed",
                    0,
                ),
                failed=job_counts.get(
                    "failed",
                    0,
                ),
            )
        ),
    )
