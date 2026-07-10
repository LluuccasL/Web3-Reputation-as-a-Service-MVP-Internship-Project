from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas import (
    CheckWalletRequest,
    HumanLikelihood,
    TrustResponse,
    TrustTier,
)


VALID_WALLET = "0x1234567890abcdef1234567890abcdef12345678"


def test_check_wallet_request_accepts_valid_wallet():
    request = CheckWalletRequest(wallet_address=VALID_WALLET)

    assert request.wallet_address == VALID_WALLET


@pytest.mark.parametrize(
    "invalid_wallet",
    [
        "",
        "1234567890abcdef1234567890abcdef12345678",
        "0x1234",
        "0x1234567890abcdef1234567890abcdef123456789",
        "0x1234567890abcdef1234567890abcdef1234567g",
    ],
)
def test_check_wallet_request_rejects_invalid_wallet(invalid_wallet):
    with pytest.raises(ValidationError):
        CheckWalletRequest(wallet_address=invalid_wallet)


def test_check_wallet_request_removes_surrounding_spaces():
    request = CheckWalletRequest(
        wallet_address=f"  {VALID_WALLET}  "
    )

    assert request.wallet_address == VALID_WALLET


def test_trust_response_accepts_valid_data():
    response = TrustResponse(
        wallet_address=VALID_WALLET,
        human_likelihood=HumanLikelihood.HIGH,
        trust_tier=TrustTier.SILVER,
        confidence_score=0.87,
        scored_at=datetime.now(timezone.utc),
    )

    assert response.wallet_address == VALID_WALLET
    assert response.human_likelihood == HumanLikelihood.HIGH
    assert response.trust_tier == TrustTier.SILVER
    assert response.confidence_score == 0.87
    assert response.risk_flags == []


@pytest.mark.parametrize(
    "invalid_score",
    [
        -0.01,
        1.01,
        -5,
        100,
    ],
)
def test_trust_response_rejects_out_of_range_confidence(invalid_score):
    with pytest.raises(ValidationError):
        TrustResponse(
            wallet_address=VALID_WALLET,
            human_likelihood=HumanLikelihood.MEDIUM,
            trust_tier=TrustTier.BRONZE,
            confidence_score=invalid_score,
            risk_flags=[],
            scored_at=datetime.now(timezone.utc),
        )


def test_trust_response_rejects_invalid_enum_values():
    with pytest.raises(ValidationError):
        TrustResponse(
            wallet_address=VALID_WALLET,
            human_likelihood="very_high",
            trust_tier="platinum",
            confidence_score=0.9,
            risk_flags=[],
            scored_at=datetime.now(timezone.utc),
        )


def test_check_wallet_request_rejects_extra_fields():
    with pytest.raises(ValidationError):
        CheckWalletRequest(
            wallet_address=VALID_WALLET,
            private_key="this-must-never-be-accepted",
        )
