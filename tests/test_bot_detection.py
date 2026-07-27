from app.services.advanced_features import (
    calculate_advanced_features,
)
from app.services.bot_detection import (
    evaluate_bot_heuristics,
)


WALLET = "0x1111111111111111111111111111111111111111"
CONTRACT = "0x2222222222222222222222222222222222222222"


def _transfer(
    receiver: str,
    timestamp: str,
) -> dict:
    return {
        "from": WALLET,
        "to": receiver,
        "category": "external",
        "asset": "ETH",
        "metadata": {
            "blockTimestamp": timestamp,
        },
    }


def test_suspicious_wallet_triggers_bot_rules():
    transfers = [
        _transfer(CONTRACT, "2026-01-01T00:00:00Z"),
        _transfer(CONTRACT, "2026-01-01T00:00:10Z"),
        _transfer(CONTRACT, "2026-01-01T00:00:20Z"),
        _transfer(CONTRACT, "2026-01-01T00:00:30Z"),
        _transfer(CONTRACT, "2026-01-01T00:00:40Z"),
        _transfer(CONTRACT, "2026-01-01T00:00:50Z"),
    ]

    enriched_data = {
        "address": WALLET,
        "transfers": transfers,
        "nft_transfers": [],
        "contract_addresses": [CONTRACT],
        "activity_range": {
            "first_activity_at": "2026-01-01T00:00:00Z",
            "last_activity_at": "2026-01-01T12:00:00Z",
        },
    }

    features = calculate_advanced_features(enriched_data)
    result = evaluate_bot_heuristics(
        enriched_data,
        features,
    )

    assert result["triggered_rule_count"] == 6
    assert set(result["triggered_rule_ids"]) == {
        "high_burst_activity",
        "repeated_contract_loop",
        "repeated_transaction_loop",
        "short_wallet_lifespan",
        "low_transaction_diversity",
        "highly_repetitive_behavior",
    }


def test_normal_wallet_does_not_trigger_rules():
    counterparties = [
        "0x3000000000000000000000000000000000000001",
        "0x3000000000000000000000000000000000000002",
        "0x3000000000000000000000000000000000000003",
        "0x3000000000000000000000000000000000000004",
        "0x3000000000000000000000000000000000000005",
    ]

    transfers = [
        _transfer(
            address,
            f"2026-01-0{index + 1}T00:00:00Z",
        )
        for index, address in enumerate(counterparties)
    ]

    enriched_data = {
        "address": WALLET,
        "transfers": transfers,
        "nft_transfers": [],
        "contract_addresses": [],
        "activity_range": {
            "first_activity_at": "2025-01-01T00:00:00Z",
            "last_activity_at": "2026-01-05T00:00:00Z",
        },
    }

    result = evaluate_bot_heuristics(enriched_data)

    assert result["triggered_rule_ids"] == []
    assert result["triggered_rule_count"] == 0
    assert all(
        rule["triggered"] is False
        for rule in result["rules"]
    )


def test_empty_data_returns_safe_results():
    enriched_data = {
        "address": WALLET,
        "transfers": [],
        "nft_transfers": [],
        "contract_addresses": [],
        "activity_range": {},
    }

    result = evaluate_bot_heuristics(enriched_data)

    assert result["triggered_rule_ids"] == []
    assert result["triggered_rule_count"] == 0
    assert len(result["rules"]) == 6
