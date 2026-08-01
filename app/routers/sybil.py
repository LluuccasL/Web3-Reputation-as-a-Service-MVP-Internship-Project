from fastapi import APIRouter, Depends

from app.errors import APIError
from app.middleware.rate_limit import enforce_rate_limit
from app.schemas_sybil import (
    SybilAnalyzeRequest,
    SybilAnalyzeResponse,
)
from app.services.enrichment import enrich_wallet
from app.services.sybil_detection import analyze_sybil_clusters


router = APIRouter(
    prefix="/sybil",
    tags=["sybil"],
)


@router.post(
    "/analyze",
    response_model=SybilAnalyzeResponse,
    summary="Analyze a group of wallets for Sybil behavior",
    responses={
        401: {"description": "Invalid or missing API key."},
        422: {"description": "Invalid request body."},
        429: {"description": "Rate limit exceeded."},
        500: {"description": "Sybil analysis failed."},
        503: {
            "description": (
                "Required blockchain provider data is unavailable."
            )
        },
    },
)
def analyze_wallet_group(
    payload: SybilAnalyzeRequest,
    _api_key: str = Depends(enforce_rate_limit),
) -> SybilAnalyzeResponse:
    try:
        enriched_wallets = [
            enrich_wallet(address)
            for address in payload.wallet_addresses
        ]

        result = analyze_sybil_clusters(
            enriched_wallets,
            timing_window_seconds=(
                payload.timing_window_seconds
            ),
        )

        return SybilAnalyzeResponse.model_validate(result)

    except RuntimeError as exc:
        raise APIError(
            status_code=503,
            code="BLOCKCHAIN_PROVIDER_ERROR",
            message=(
                "Required blockchain provider data is unavailable."
            ),
        ) from exc

    except ValueError as exc:
        raise APIError(
            status_code=422,
            code="INVALID_SYBIL_ANALYSIS",
            message=str(exc),
        ) from exc

    except Exception as exc:
        raise APIError(
            status_code=500,
            code="SYBIL_ANALYSIS_FAILED",
            message=(
                "Failed to analyze wallets for Sybil behavior."
            ),
        ) from exc
