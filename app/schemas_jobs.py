from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas import WalletAddress


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ScoreWalletJobRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "wallet_address": (
                    "0x1234567890abcdef1234567890abcdef12345678"
                )
            }
        },
    )

    wallet_address: WalletAddress


class JobAcceptedResponse(BaseModel):
    job_id: str
    status: JobStatus
    status_url: str
    deduplicated: bool = False


class JobResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: str
    wallet_address: str
    job_type: str
    status: JobStatus
    attempts: int
    result: dict[str, Any] | None
    error: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class JobListResponse(BaseModel):
    count: int = Field(ge=0)
    jobs: list[JobResponse]


class LatestScoreResponse(BaseModel):
    wallet_address: str
    job_id: str
    result: dict[str, Any]
    updated_at: datetime
