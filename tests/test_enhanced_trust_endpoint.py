import pytest

from app.errors import APIError
from app.routers import trust
from app.schemas import CheckWalletRequest
from app.schemas_enhanced import EnhancedTrustResponse


ADDRESS = "0x1111111111111111111111111111111111111111"


def _base_result() -> dict:
    return {
        "human_likelihood": "medium",
        "trust_tier": "silver",
        "confidence_score": 0.70,
        "risk_flags": [],
    }


def _enriched_data(address: str) -> dict:
    return {
        "address": address,
        "balance": None,
        "transfers": [],
        "nft_transfers": [],
        "transaction_details": [],
        "contract_addresses": [],
        "activity_range": {},
        "source_status": {
            "balance": "available",
            "transfers": "partial",
            "nft_activity": "unavailable",
        },
        "errors": {
            "transfers": "One transfer source was unavailable."
        },
    }


def test_enhanced_endpoint_returns_structured_response(
    monkeypatch,
):
    monkeypatch.setattr(
        trust,
        "calculate_trust_result",
        lambda address: _base_result(),
    )
    monkeypatch.setattr(
        trust,
        "enrich_wallet",
        _enriched_data,
    )

    payload = CheckWalletRequest(
        wallet_address=ADDRESS
    )

    result = trust.check_wallet_enhanced(
        payload,
        _api_key="test-key",
    )

    validated = EnhancedTrustResponse.model_validate(result)

    assert validated.wallet_address == ADDRESS
    assert validated.base_score == 70
    assert validated.enhanced_score == 70
    assert validated.data_coverage == 0.5
    assert validated.risk_level == "none"
    assert validated.risk_flags == []

    assert validated.source_status["transfers"] == "partial"
    assert "transfers" in validated.data_errors


def test_enhanced_endpoint_maps_provider_errors(
    monkeypatch,
):
    def unavailable(address: str):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(
        trust,
        "calculate_trust_result",
        unavailable,
    )

    payload = CheckWalletRequest(
        wallet_address=ADDRESS
    )

    with pytest.raises(APIError) as error:
        trust.check_wallet_enhanced(
            payload,
            _api_key="test-key",
        )

    assert error.value.status_code == 503


def test_original_and_enhanced_routes_are_registered():
    paths = {
        route.path
        for route in trust.router.routes
    }

    assert "/check_wallet" in paths
    assert "/check_wallet/enhanced" in paths
