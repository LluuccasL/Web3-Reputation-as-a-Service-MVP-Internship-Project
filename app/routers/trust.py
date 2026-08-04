import os
import time

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response

from app.errors import APIError
from app.middleware.rate_limit import enforce_rate_limit
from app.routers.wallets import (
    calculate_wallet_reputation,
    normalize_address,
)
from app.schemas import (
    CheckWalletRequest,
    GeneratedProofResponse,
    GenerateProofRequest,
    HumanLikelihood,
    TrustResponse,
    TrustTier,
    WalletReputationResponse,
)
from app.services.monitoring import log_event
from app.services.proof_service import create_signed_proof
from app.services.resilience import (
    RETRYABLE_EXCEPTIONS,
    retry_operation,
)
from app.services.trust_cache import TTLCache


router = APIRouter(tags=["trust"])

def reputation_to_trust_response(
    reputation: WalletReputationResponse,
) -> TrustResponse:
    score = max(0, min(reputation.score, 100))

    if score >= 80:
        human_likelihood = HumanLikelihood.HIGH
        trust_tier = TrustTier.GOLD
    elif score >= 50:
        human_likelihood = HumanLikelihood.MEDIUM
        trust_tier = TrustTier.SILVER
    else:
        human_likelihood = HumanLikelihood.LOW
        trust_tier = TrustTier.BRONZE

    signals = reputation.signals
    risk_flags: list[str] = []

    try:
        balance_eth = float(
            signals.get("balance_eth", 0)
        )
    except (TypeError, ValueError):
        balance_eth = 0.0

    transfer_status = signals.get("transfer_status")
    transfer_count = signals.get("transfer_count", 0)

    if balance_eth <= 0:
        risk_flags.append("zero_balance")

    if transfer_status == "unavailable":
        risk_flags.append(
            "transfer_data_unavailable"
        )
    elif transfer_count == 0:
        risk_flags.append("no_recent_transfers")

    if score < 50:
        risk_flags.append(
            "low_reputation_score"
        )

    return TrustResponse(
        wallet_address=reputation.address,
        human_likelihood=human_likelihood,
        trust_tier=trust_tier,
        confidence_score=round(score / 100, 2),
        risk_flags=risk_flags,
        scored_at=datetime.now(timezone.utc),
    )


TRUST_CACHE_TTL_SECONDS = max(
    1,
    int(os.getenv("TRUST_CACHE_TTL_SECONDS", "300")),
)
TRUST_CACHE_MAX_SIZE = max(
    1,
    int(os.getenv("TRUST_CACHE_MAX_SIZE", "256")),
)

ALCHEMY_MAX_ATTEMPTS = max(
    1,
    int(os.getenv("ALCHEMY_MAX_ATTEMPTS", "3")),
)
ALCHEMY_RETRY_BASE_SECONDS = max(
    0.0,
    float(
        os.getenv(
            "ALCHEMY_RETRY_BASE_SECONDS",
            "0.2",
        )
    ),
)
ALCHEMY_RETRY_MAX_SECONDS = max(
    ALCHEMY_RETRY_BASE_SECONDS,
    float(
        os.getenv(
            "ALCHEMY_RETRY_MAX_SECONDS",
            "2.0",
        )
    ),
)

trust_cache: TTLCache[TrustResponse] = TTLCache(
    ttl_seconds=TRUST_CACHE_TTL_SECONDS,
    max_size=TRUST_CACHE_MAX_SIZE,
)


def _calculate_trust_result_uncached(
    address: str,
) -> TrustResponse:
    reputation = retry_operation(
        lambda: calculate_wallet_reputation(
            address,
            max_count=10,
        ),
        operation_name=(
            "calculate_wallet_reputation"
        ),
        attempts=ALCHEMY_MAX_ATTEMPTS,
        base_delay_seconds=(
            ALCHEMY_RETRY_BASE_SECONDS
        ),
        max_delay_seconds=(
            ALCHEMY_RETRY_MAX_SECONDS
        ),
    )

    return reputation_to_trust_response(reputation)


def calculate_trust_result_with_metadata(
    address: str,
) -> tuple[TrustResponse, str]:
    try:
        result, cache_hit = (
            trust_cache.get_or_compute(
                address,
                lambda: (
                    _calculate_trust_result_uncached(
                        address
                    )
                ),
            )
        )
    except RETRYABLE_EXCEPTIONS as exc:
        stale_result = trust_cache.get_stale(
            address
        )

        if stale_result is None:
            raise

        log_event(
            "stale_score_served",
            error_type=type(exc).__name__,
        )

        return stale_result, "STALE"

    return (
        result,
        "HIT" if cache_hit else "MISS",
    )


def calculate_trust_result(
    address: str,
) -> TrustResponse:
    result, _ = (
        calculate_trust_result_with_metadata(
            address
        )
    )

    return result


def refresh_trust_result(
    address: str,
) -> TrustResponse:
    result = _calculate_trust_result_uncached(
        address
    )
    trust_cache.set(address, result)
    return result


def clear_trust_cache(
    address: str | None = None,
) -> None:
    trust_cache.invalidate(address)


def get_trust_cache_stats() -> dict[str, int | float]:
    return trust_cache.stats()


@router.post(
    "/check_wallet",
    response_model=TrustResponse,
    summary="Check a wallet's public trust signals",
    responses={
        401: {"description": "Invalid or missing API key."},
        422: {"description": "Invalid request body."},
        429: {"description": "Rate limit exceeded."},
        500: {"description": "Trust calculation failed."},
        503: {
            "description": (
                "The blockchain provider is temporarily unavailable."
            )
        },
    },
)
def check_wallet(
    payload: CheckWalletRequest,
    response: Response,
    _api_key: str = Depends(enforce_rate_limit),
):
    address = normalize_address(
        payload.wallet_address
    )
    started_at = time.perf_counter()

    try:
        result, cache_status = (
            calculate_trust_result_with_metadata(
                address
            )
        )
    except RuntimeError as exc:
        raise APIError(
            status_code=503,
            code="BLOCKCHAIN_PROVIDER_ERROR",
            message=(
                "The blockchain provider is temporarily "
                "unavailable."
            ),
        ) from exc
    except Exception as exc:
        raise APIError(
            status_code=500,
            code="SCORING_FAILED",
            message="Failed to calculate wallet trust.",
        ) from exc

    duration_ms = (
        time.perf_counter() - started_at
    ) * 1000

    response.headers[
        "X-Trust-Cache"
    ] = cache_status

    if cache_status == "STALE":
        response.headers["Warning"] = (
            '110 - "Stale wallet score returned"'
        )
    response.headers[
        "X-Processing-Time-Ms"
    ] = f"{duration_ms:.2f}"

    return result


@router.post(
    "/generate_proof",
    response_model=GeneratedProofResponse,
    summary="Generate a signed wallet trust proof",
    responses={
        401: {"description": "Invalid or missing API key."},
        422: {"description": "Invalid request body."},
        429: {"description": "Rate limit exceeded."},
        500: {"description": "Proof generation failed."},
        503: {
            "description": (
                "The blockchain provider is temporarily unavailable."
            )
        },
    },
)
def generate_proof(
    payload: GenerateProofRequest,
    _api_key: str = Depends(enforce_rate_limit),
):
    address = normalize_address(payload.wallet_address)

    try:
        trust_result = calculate_trust_result(address)
    except RuntimeError as exc:
        raise APIError(
            status_code=503,
            code="BLOCKCHAIN_PROVIDER_ERROR",
            message=(
                "The blockchain provider is temporarily unavailable."
            ),
        ) from exc
    except Exception as exc:
        raise APIError(
            status_code=500,
            code="SCORING_FAILED",
            message="Failed to calculate wallet trust.",
        ) from exc

    try:
        return create_signed_proof(
            trust_result=trust_result,
            valid_for_hours=payload.valid_for_hours,
        )
    except RuntimeError as exc:
        raise APIError(
            status_code=500,
            code="PROOF_SERVICE_ERROR",
            message=(
                "The proof service is not configured correctly."
            ),
        ) from exc
    except ValueError as exc:
        raise APIError(
            status_code=400,
            code="INVALID_PROOF_VALIDITY",
            message=str(exc),
        ) from exc
    except Exception as exc:
        raise APIError(
            status_code=500,
            code="PROOF_GENERATION_FAILED",
            message="Failed to generate proof.",
        ) from exc


from app.schemas_enhanced import EnhancedTrustResponse
from app.services.advanced_features import (
    calculate_advanced_features,
)
from app.services.bot_detection import (
    evaluate_bot_heuristics,
)
from app.services.enhanced_scoring import (
    calculate_enhanced_trust_result,
)
from app.services.enrichment import enrich_wallet
from app.services.risk_flags import generate_risk_flags


@router.post(
    "/check_wallet/enhanced",
    response_model=EnhancedTrustResponse,
    summary="Check a wallet with enhanced behavioral analysis",
    responses={
        401: {"description": "Invalid or missing API key."},
        422: {"description": "Invalid request body."},
        429: {"description": "Rate limit exceeded."},
        500: {"description": "Enhanced trust calculation failed."},
        503: {
            "description": (
                "Required blockchain provider data is unavailable."
            )
        },
    },
)
def check_wallet_enhanced(
    payload: CheckWalletRequest,
    _api_key: str = Depends(enforce_rate_limit),
) -> EnhancedTrustResponse:
    """
    Return the original trust result together with Week 5 analysis.

    The existing /check_wallet endpoint remains unchanged.
    """
    address = normalize_address(payload.wallet_address)

    try:
        base_result = calculate_trust_result(address)

        enriched_data = enrich_wallet(address)

        advanced_features = calculate_advanced_features(
            enriched_data
        )

        heuristic_results = evaluate_bot_heuristics(
            enriched_data,
            advanced_features,
        )

        risk_flag_results = generate_risk_flags(
            enriched_data,
            advanced_features,
            heuristic_results,
        )

        enhanced_result = calculate_enhanced_trust_result(
            base_result,
            enriched_data,
            advanced_features,
            risk_flag_results,
        )

        return EnhancedTrustResponse.model_validate(
            {
                **enhanced_result,
                "wallet_address": address,
                "source_status": enriched_data.get(
                    "source_status",
                    {},
                ),
                "data_errors": enriched_data.get(
                    "errors",
                    {},
                ),
            }
        )

    except RuntimeError as exc:
        raise APIError(
            503,
            "BLOCKCHAIN_PROVIDER_ERROR",
            str(exc),
        ) from exc
    except Exception as exc:
        raise APIError(
            500,
            "ENHANCED_SCORING_FAILED",
            "Enhanced wallet analysis failed.",
        ) from exc


from app.demo_wallets import list_demo_wallets
from app.schemas_demo import DemoWalletCatalogResponse
from app.services.enrichment import _demo_mode_enabled


@router.get(
    "/demo_wallets",
    response_model=DemoWalletCatalogResponse,
    summary="List available synthetic demo wallets",
    responses={
        401: {"description": "Invalid or missing API key."},
        429: {"description": "Rate limit exceeded."},
    },
)
def get_demo_wallet_catalog(
    _api_key: str = Depends(enforce_rate_limit),
) -> DemoWalletCatalogResponse:
    """
    Return synthetic scenarios when local demo mode is enabled.

    No live blockchain provider request is made by this endpoint.
    """
    demo_mode_enabled = _demo_mode_enabled()

    return DemoWalletCatalogResponse(
        demo_mode_enabled=demo_mode_enabled,
        wallets=(
            list_demo_wallets()
            if demo_mode_enabled
            else []
        ),
    )
