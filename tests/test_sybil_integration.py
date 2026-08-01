import pytest

from dashboard.sybil_integration import (
    flagged_wallet_rows,
    is_flagged_wallet,
    merge_trust_and_sybil_results,
    stored_wallet_addresses,
    sybil_context_for_wallet,
)


ADDRESSES = [
    f"0x{number:040x}"
    for number in range(1, 27)
]


def _trust_results():
    return [
        {
            "wallet_address": ADDRESSES[0],
            "trust_tier": "silver",
            "human_likelihood": "medium",
            "confidence_score": 0.7,
            "risk_flags": [],
        },
        {
            "wallet_address": ADDRESSES[1],
            "trust_tier": "gold",
            "human_likelihood": "high",
            "confidence_score": 0.9,
            "risk_flags": [],
        },
    ]


def _sybil_analysis():
    return {
        "cluster_count": 1,
        "wallet_results": [
            {
                "address": ADDRESSES[0],
                "sybil_risk_score": 90,
                "sybil_risk_level": "critical",
                "cluster_id": "sybil-123456789abc",
                "cluster_size": 2,
                "related_wallets": [
                    {"address": ADDRESSES[1]}
                ],
                "risk_flags": [
                    "shared_funding_source",
                ],
            },
            {
                "address": ADDRESSES[1],
                "sybil_risk_score": 90,
                "sybil_risk_level": "critical",
                "cluster_id": "sybil-123456789abc",
                "cluster_size": 2,
                "related_wallets": [
                    {"address": ADDRESSES[0]}
                ],
                "risk_flags": [
                    "shared_funding_source",
                ],
            },
        ],
    }


def test_extracts_normalized_unique_stored_addresses():
    results = [
        {"wallet_address": ADDRESSES[0].upper().replace("0X", "0x")},
        {"address": ADDRESSES[1]},
        {"wallet_address": ADDRESSES[0]},
        {},
    ]

    assert stored_wallet_addresses(results) == (
        ADDRESSES[:2]
    )


def test_rejects_invalid_stored_address():
    with pytest.raises(
        ValueError,
        match="Invalid stored wallet address",
    ):
        stored_wallet_addresses(
            [{"wallet_address": "not-a-wallet"}]
        )


def test_rejects_more_than_endpoint_limit():
    with pytest.raises(
        ValueError,
        match="no more than 25",
    ):
        stored_wallet_addresses(
            [
                {"wallet_address": address}
                for address in ADDRESSES
            ]
        )


def test_merges_sybil_context_without_losing_trust_data():
    merged = merge_trust_and_sybil_results(
        _trust_results(),
        _sybil_analysis(),
    )

    assert merged[0]["trust_tier"] == "silver"
    assert merged[0]["sybil_risk_score"] == 90
    assert merged[0]["sybil_risk_level"] == "critical"
    assert merged[0]["sybil_cluster_id"] == (
        "sybil-123456789abc"
    )
    assert merged[0]["sybil_related_wallet_count"] == 1


def test_missing_sybil_context_uses_low_risk_defaults():
    merged = merge_trust_and_sybil_results(
        _trust_results(),
        None,
    )

    assert merged[0]["sybil_risk_score"] == 0
    assert merged[0]["sybil_risk_level"] == "low"
    assert merged[0]["sybil_cluster_id"] is None
    assert merged[0]["sybil_risk_flags"] == []


def test_clustered_wallet_is_flagged_despite_acceptable_trust():
    merged = merge_trust_and_sybil_results(
        _trust_results(),
        _sybil_analysis(),
    )

    assert is_flagged_wallet(merged[0]) is True


def test_independent_gold_wallet_is_not_flagged():
    result = {
        **_trust_results()[1],
        "sybil_risk_score": 0,
        "sybil_risk_level": "low",
        "sybil_cluster_id": None,
        "sybil_risk_flags": [],
    }

    assert is_flagged_wallet(result) is False


def test_flagged_rows_include_explainable_sybil_fields():
    merged = merge_trust_and_sybil_results(
        _trust_results(),
        _sybil_analysis(),
    )
    rows = flagged_wallet_rows(merged)

    assert len(rows) == 2
    assert rows[0]["sybil_risk_score"] == 90
    assert rows[0]["sybil_risk_level"] == "critical"
    assert rows[0]["sybil_cluster"] == (
        "sybil-123456789abc"
    )
    assert rows[0]["related_wallets"] == 1
    assert "Sybil: Shared Funding Source" in (
        rows[0]["risk_flags"]
    )


def test_finds_single_wallet_context_case_insensitively():
    context = sybil_context_for_wallet(
        _sybil_analysis(),
        ADDRESSES[0].upper().replace("0X", "0x"),
    )

    assert context is not None
    assert context["sybil_risk_level"] == "critical"
