from pydantic import BaseModel, Field


class CacheStatsResponse(BaseModel):
    ttl_seconds: int = Field(ge=1)
    max_size: int = Field(ge=1)
    size: int = Field(ge=0)
    inflight: int = Field(ge=0)
    hits: int = Field(ge=0)
    misses: int = Field(ge=0)
    evictions: int = Field(ge=0)
    hit_rate: float = Field(
        ge=0.0,
        le=1.0,
    )


class RouteMetricsResponse(BaseModel):
    method: str
    path: str
    requests: int = Field(ge=0)
    errors: int = Field(ge=0)
    average_latency_ms: float = Field(
        ge=0.0
    )
    max_latency_ms: float = Field(
        ge=0.0
    )


class RequestMetricsResponse(BaseModel):
    total_requests: int = Field(ge=0)
    active_requests: int = Field(ge=0)
    errors: int = Field(ge=0)
    average_latency_ms: float = Field(
        ge=0.0
    )
    routes: list[RouteMetricsResponse]


class BackgroundJobMetricsResponse(BaseModel):
    total: int = Field(ge=0)
    queued: int = Field(ge=0)
    running: int = Field(ge=0)
    completed: int = Field(ge=0)
    failed: int = Field(ge=0)


class MonitoringResponse(BaseModel):
    uptime_seconds: float = Field(
        ge=0.0
    )
    requests: RequestMetricsResponse
    cache: CacheStatsResponse
    background_jobs: (
        BackgroundJobMetricsResponse
    )
