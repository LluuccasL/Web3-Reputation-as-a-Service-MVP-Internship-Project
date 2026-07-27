from app.services.advanced_features import (
    calculate_advanced_features,
)
from app.services.bot_detection import (
    evaluate_bot_heuristics,
)
from app.services.risk_flags import (
    generate_risk_flags,
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


def test_suspicious_wallet_generates_structured_risk_flags():
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
        "nft_transfers": [
            {"category": "erc721"}
            for _ in range(12)
        ],
        "contract_addresses": [CONTRACT],
        "activity_range": {
            "first_activity_at": "2026-01-01T00:00:00Z",
            "last_activity_at": "2026-01-01T12:00:00Z",
        },
    }

    features = calculate_advanced_features(enriched_data)
    heuristics = evaluate_bot_heuristics(
        enriched_data,
        features,
    )
    result = generate_risk_flags(
        enriched_data,
        features,
        heuristics,
    )

    assert result["risk_level"] == "high"
    assert result["risk_flag_count"] == 7
    assert result["informational_flag_count"] == 1

    assert "high_burst_activity" in result["risk_flag_ids"]
    assert "suspicious_nft_activity" in result["risk_flag_ids"]

    assert (
        "high_contract_interaction_ratio"
        in result["informational_flag_ids"]
    )

    assert all(
        flag["signal_type"] == "risk"
        for flag in result["risk_flags"]
    )


def test_contract_usage_alone_is_informational():
    contracts = [
        f"0x300000000000000000000000000000000000000{i}"
        for i in range(1, 6)
    ]

    transfers = [
        _transfer(
            contract,
            f"2026-01-0{index}T00:00:00Z",
        )
        for index, contract in enumerate(
            contracts,
            start=1,
        )
    ]

    enriched_data = {
        "address": WALLET,
        "transfers": transfers,
        "nft_transfers": [],
        "contract_addresses": contracts,
        "activity_range": {
            "first_activity_at": "2025-01-01T00:00:00Z",
            "last_activity_at": "2026-01-05T00:00:00Z",
        },
    }

    result = generate_risk_flags(enriched_data)

    assert result["risk_flag_ids"] == []
    assert result["risk_level"] == "none"
    assert result["risk_points"] == 0

    assert result["informational_flag_ids"] == [
        "high_contract_interaction_ratio"
    ]


def test_empty_data_generates_no_flags():
    enriched_data = {
        "address": WALLET,
        "transfers": [],
        "nft_transfers": [],
        "contract_addresses": [],
        "activity_range": {},
    }

    result = generate_risk_flags(enriched_data)

    assert result["flags"] == []
    assert result["risk_flag_count"] == 0
    assert result["informational_flag_count"] == 0
    assert result["risk_points"] == 0
    assert result["risk_level"] == "none"
