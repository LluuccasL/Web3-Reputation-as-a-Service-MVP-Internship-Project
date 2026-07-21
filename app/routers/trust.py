import os
import time
from functools import lru_cache

from datetime import datetime, timezone

from fastapi import APIRouter, Depends

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
from app.services.proof_service import create_signed_proof


router = APIRouter(tags=["trust"])

TRUST_CACHE_TTL_SECONDS = max(
    1,
    int(os.getenv("TRUST_CACHE_TTL_SECONDS", "300")),
)
TRUST_CACHE_MAX_SIZE = max(
    1,
    int(os.getenv("TRUST_CACHE_MAX_SIZE", "256")),
)


def reputation_to_trust_response(
    reputation: WalletReputationResponse,
) -> TrustResponse:
    """
    Convert the internal Week 2 result into the public Week 3 response.
    """
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
        risk_flags.append("transfer_data_unavailable")
    elif transfer_count == 0:
        risk_flags.append("no_recent_transfers")

    if score < 50:
        risk_flags.append("low_reputation_score")

    return TrustResponse(
        wallet_address=reputation.address,
        human_likelihood=human_likelihood,
        trust_tier=trust_tier,
        confidence_score=round(score / 100, 2),
        risk_flags=risk_flags,
        scored_at=datetime.now(timezone.utc),
    )


@lru_cache(maxsize=TRUST_CACHE_MAX_SIZE)
def _calculate_trust_result_cached(
    address: str,
    cache_window: int,
) -> TrustResponse:
    del cache_window

    reputation = calculate_wallet_reputation(
        address,
        max_count=10,
    )

    return reputation_to_trust_response(reputation)


def calculate_trust_result(
    address: str,
) -> TrustResponse:
    cache_window = int(
        time.monotonic() // TRUST_CACHE_TTL_SECONDS
    )

    return _calculate_trust_result_cached(
        address,
        cache_window,
    )


def clear_trust_cache() -> None:
    _calculate_trust_result_cached.cache_clear()


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
    _api_key: str = Depends(enforce_rate_limit),
):
    address = normalize_address(payload.wallet_address)

    try:
        return calculate_trust_result(address)
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
