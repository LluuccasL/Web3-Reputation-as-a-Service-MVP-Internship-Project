from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.routers.wallets import (
    calculate_wallet_reputation,
    normalize_address,
)
from app.schemas import (
    CheckWalletRequest,
    HumanLikelihood,
    TrustResponse,
    TrustTier,
    WalletReputationResponse,
)

router = APIRouter(tags=["trust"])


def reputation_to_trust_response(
    reputation: WalletReputationResponse,
) -> TrustResponse:
    """
    Convert the internal Week 2 reputation result into the privacy-safe
    public response used by the Week 3 API.
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
        balance_eth = float(signals.get("balance_eth", 0))
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


@router.post(
    "/check_wallet",
    response_model=TrustResponse,
    summary="Check a wallet's public trust signals",
    responses={
        503: {
            "description": (
                "The blockchain provider is temporarily unavailable."
            )
        }
    },
)
def check_wallet(payload: CheckWalletRequest):
    address = normalize_address(payload.wallet_address)

    try:
        reputation = calculate_wallet_reputation(
            address,
            max_count=10,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Blockchain provider unavailable: {str(exc)}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Failed to calculate wallet trust.",
        ) from exc

    return reputation_to_trust_response(reputation)
