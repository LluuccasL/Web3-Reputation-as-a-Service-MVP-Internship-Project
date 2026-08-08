from fastapi import APIRouter, Depends

from app.errors import APIError
from app.middleware.rate_limit import enforce_rate_limit
from app.openapi import protected_responses
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
    description=(
        "Builds a wallet relationship graph, identifies coordinated "
        "clusters, and returns privacy-safe risk explanations."
    ),
    responses=protected_responses(
        success_description="Wallet-group Sybil analysis.",
        include_provider_failure=True,
    ),
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
