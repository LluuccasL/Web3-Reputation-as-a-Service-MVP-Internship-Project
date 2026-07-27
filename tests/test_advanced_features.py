import pytest

from app.services.advanced_features import (
    calculate_advanced_features,
)


WALLET = "0x1111111111111111111111111111111111111111"
ADDRESS_A = "0x2222222222222222222222222222222222222222"
ADDRESS_B = "0x3333333333333333333333333333333333333333"
CONTRACT = "0x4444444444444444444444444444444444444444"


def test_calculate_advanced_features():
    enriched_data = {
        "address": WALLET,
        "transfers": [
            {"from": WALLET, "to": ADDRESS_A},
            {"from": WALLET, "to": ADDRESS_A},
            {"from": ADDRESS_B, "to": WALLET},
            {"from": WALLET, "to": CONTRACT},
        ],
        "nft_transfers": [
            {"category": "erc721"},
            {"category": "erc1155"},
        ],
        "contract_addresses": [CONTRACT],
        "activity_range": {
            "first_activity_at": "2025-01-01T00:00:00Z",
            "last_activity_at": "2025-01-11T00:00:00Z",
        },
    }

    features = calculate_advanced_features(enriched_data)

    assert features["total_transfers"] == 4
    assert features["unique_interaction_addresses"] == 3
    assert features["transaction_diversity"] == 0.75
    assert features["unique_contracts"] == 1
    assert features["contract_interaction_count"] == 1
    assert features["contract_interaction_ratio"] == 0.25
    assert features["transaction_entropy"] == pytest.approx(
        0.9464
    )
    assert features["wallet_lifespan_days"] == 10.0
    assert features["nft_transfer_count"] == 2
    assert features["has_nft_activity"] is True


def test_repetitive_activity_has_low_diversity_and_entropy():
    enriched_data = {
        "address": WALLET,
        "transfers": [
            {"from": WALLET, "to": CONTRACT},
            {"from": WALLET, "to": CONTRACT},
            {"from": WALLET, "to": CONTRACT},
        ],
        "nft_transfers": [],
        "contract_addresses": [CONTRACT],
        "activity_range": {},
    }

    features = calculate_advanced_features(enriched_data)

    assert features["transaction_diversity"] == pytest.approx(
        1 / 3,
        abs=0.0001,
    )
    assert features["transaction_entropy"] == 0.0
    assert features["contract_interaction_ratio"] == 1.0
    assert features["wallet_lifespan_days"] is None


def test_empty_enrichment_returns_safe_defaults():
    features = calculate_advanced_features(
        {
            "address": WALLET,
            "transfers": [],
            "nft_transfers": [],
            "contract_addresses": [],
            "activity_range": {
                "first_activity_at": None,
                "last_activity_at": None,
            },
        }
    )

    assert features["total_transfers"] == 0
    assert features["unique_interaction_addresses"] == 0
    assert features["transaction_diversity"] == 0.0
    assert features["contract_interaction_ratio"] == 0.0
    assert features["transaction_entropy"] == 0.0
    assert features["wallet_lifespan_days"] is None
    assert features["nft_transfer_count"] == 0
    assert features["has_nft_activity"] is False
