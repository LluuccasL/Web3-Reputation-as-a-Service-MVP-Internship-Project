from fastapi import APIRouter, Depends, Query

from app.errors import APIError
from app.middleware.rate_limit import enforce_rate_limit
from app.models import BackgroundJob
from app.routers.trust import refresh_trust_result
from app.routers.trust import (
    calculate_trust_result,
    clear_trust_cache,
)
from app.routers.wallets import normalize_address
from app.schemas import WalletAddress
from app.schemas_jobs import (
    JobAcceptedResponse,
    JobListResponse,
    JobResponse,
    JobStatus,
    LatestScoreResponse,
    ScoreWalletJobRequest,
)
from app.services.job_queue import (
    JobQueue,
    get_job_queue,
)


router = APIRouter(tags=["background jobs"])


def calculate_job_result(
    address: str,
    refresh: bool,
) -> dict:
    if refresh:
        result = refresh_trust_result(address)
    else:
        result = calculate_trust_result(address)

    return result.model_dump(mode="json")


def accepted_response(
    job_id: str,
    deduplicated: bool,
) -> JobAcceptedResponse:
    return JobAcceptedResponse(
        job_id=job_id,
        status=JobStatus.QUEUED,
        status_url=f"/jobs/{job_id}",
        deduplicated=deduplicated,
    )


def job_response(
    job: BackgroundJob,
) -> JobResponse:
    return JobResponse.model_validate(job)


def require_job(
    queue: JobQueue,
    job_id: str,
) -> BackgroundJob:
    job = queue.get_job(job_id)

    if job is None:
        raise APIError(
            status_code=404,
            code="JOB_NOT_FOUND",
            message="Background job not found.",
        )

    return job


def submit_scoring_job(
    queue: JobQueue,
    address: str,
    refresh: bool,
) -> tuple[str, bool]:
    job_type = (
        "refresh_score"
        if refresh
        else "score_wallet"
    )

    return queue.submit_unique(
        wallet_address=address,
        job_type=job_type,
        task=lambda: calculate_job_result(
            address,
            refresh,
        ),
    )


@router.post(
    "/jobs/score-wallet",
    response_model=JobAcceptedResponse,
    status_code=202,
)
def submit_score_wallet_job(
    payload: ScoreWalletJobRequest,
    queue: JobQueue = Depends(get_job_queue),
    _api_key: str = Depends(enforce_rate_limit),
) -> JobAcceptedResponse:
    address = normalize_address(
        payload.wallet_address
    )

    job_id, created = submit_scoring_job(
        queue,
        address,
        refresh=False,
    )

    return accepted_response(
        job_id,
        deduplicated=not created,
    )


@router.post(
    "/wallets/{wallet_address}/refresh-score",
    response_model=JobAcceptedResponse,
    status_code=202,
)
def refresh_wallet_score(
    wallet_address: WalletAddress,
    queue: JobQueue = Depends(get_job_queue),
    _api_key: str = Depends(enforce_rate_limit),
) -> JobAcceptedResponse:
    address = normalize_address(wallet_address)

    job_id, created = submit_scoring_job(
        queue,
        address,
        refresh=True,
    )

    return accepted_response(
        job_id,
        deduplicated=not created,
    )


@router.get(
    "/jobs/{job_id}",
    response_model=JobResponse,
)
def get_job(
    job_id: str,
    queue: JobQueue = Depends(get_job_queue),
    _api_key: str = Depends(enforce_rate_limit),
) -> JobResponse:
    return job_response(
        require_job(queue, job_id)
    )


@router.get(
    "/jobs",
    response_model=JobListResponse,
)
def list_jobs(
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
    status: JobStatus | None = Query(
        default=None
    ),
    queue: JobQueue = Depends(get_job_queue),
    _api_key: str = Depends(enforce_rate_limit),
) -> JobListResponse:
    jobs = queue.list_jobs(limit=100)

    if status is not None:
        jobs = [
            job
            for job in jobs
            if job.status == status.value
        ]

    jobs = jobs[:limit]

    return JobListResponse(
        count=len(jobs),
        jobs=[
            job_response(job)
            for job in jobs
        ],
    )


@router.get(
    "/wallets/{wallet_address}/latest-score",
    response_model=LatestScoreResponse,
)
def get_latest_wallet_score(
    wallet_address: WalletAddress,
    queue: JobQueue = Depends(get_job_queue),
    _api_key: str = Depends(enforce_rate_limit),
) -> LatestScoreResponse:
    address = normalize_address(wallet_address)
    score = queue.get_latest_score(address)

    if score is None:
        raise APIError(
            status_code=404,
            code="LATEST_SCORE_NOT_FOUND",
            message=(
                "No completed background score "
                "exists for this wallet."
            ),
        )

    return LatestScoreResponse(
        wallet_address=score.wallet_address,
        job_id=score.job_id,
        result=score.result,
        updated_at=score.updated_at,
    )
