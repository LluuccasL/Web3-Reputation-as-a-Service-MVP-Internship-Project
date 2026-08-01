import pytest

from app.demo_wallets import (
    DEMO_ADDRESS_BY_KEY,
    get_demo_enriched_data,
)
from app.services.sybil_detection import (
    analyze_sybil_clusters,
    sybil_risk_level,
)


def _wallet(scenario_key: str) -> dict:
    enriched_data = get_demo_enriched_data(
        DEMO_ADDRESS_BY_KEY[scenario_key]
    )

    assert enriched_data is not None
    return enriched_data


def _sybil_wallets() -> list[dict]:
    return [
        _wallet("sybil_alpha"),
        _wallet("sybil_beta"),
        _wallet("sybil_gamma"),
    ]


def test_detects_high_risk_sybil_cluster():
    result = analyze_sybil_clusters(
        _sybil_wallets()
    )

    assert result["analyzed_wallet_count"] == 3
    assert result["cluster_count"] == 1

    cluster = result["clusters"][0]

    assert cluster["cluster_size"] == 3
    assert cluster["density"] == 1.0
    assert cluster["sybil_risk_score"] == 90
    assert cluster["sybil_risk_level"] == "critical"
    assert cluster["risk_flags"] == [
        "shared_funding_source",
        "coordinated_timing",
        "high_behavior_similarity",
        "repeated_shared_recipients",
        "dense_wallet_connections",
    ]


def test_returns_explainable_wallet_results():
    result = analyze_sybil_clusters(
        _sybil_wallets()
    )

    for wallet_result in result["wallet_results"]:
        assert wallet_result["sybil_risk_score"] == 90
        assert wallet_result["sybil_risk_level"] == (
            "critical"
        )
        assert wallet_result["cluster_size"] == 3
        assert len(wallet_result["related_wallets"]) == 2
        assert len(wallet_result["explanations"]) == 5

        for related in wallet_result["related_wallets"]:
            assert related[
                "relationship_strength"
            ] == 0.8
            assert related["behavior_similarity"] == 1.0
            assert related["matching_fingerprint"] is True


def test_cluster_id_is_deterministic():
    forward = analyze_sybil_clusters(
        _sybil_wallets()
    )
    reverse = analyze_sybil_clusters(
        list(reversed(_sybil_wallets()))
    )

    assert forward["clusters"][0]["cluster_id"] == (
        reverse["clusters"][0]["cluster_id"]
    )
    assert forward["wallet_results"] == reverse[
        "wallet_results"
    ]


def test_independent_wallets_remain_low_risk():
    result = analyze_sybil_clusters(
        [
            _wallet("established_human"),
            _wallet("normal_active"),
        ]
    )

    assert result["cluster_count"] == 0
    assert result["relationship_graph"]["edge_count"] == 0

    for wallet_result in result["wallet_results"]:
        assert wallet_result["sybil_risk_score"] == 0
        assert wallet_result["sybil_risk_level"] == "low"
        assert wallet_result["cluster_id"] is None
        assert wallet_result["cluster_size"] == 1
        assert wallet_result["related_wallets"] == []
        assert wallet_result["risk_flags"] == []


def test_mixed_group_only_clusters_related_wallets():
    result = analyze_sybil_clusters(
        _sybil_wallets()
        + [_wallet("established_human")]
    )

    assert result["analyzed_wallet_count"] == 4
    assert result["cluster_count"] == 1
    assert result["clusters"][0]["cluster_size"] == 3

    established = next(
        wallet
        for wallet in result["wallet_results"]
        if wallet["address"]
        == DEMO_ADDRESS_BY_KEY["established_human"]
    )

    assert established["cluster_id"] is None
    assert established["sybil_risk_score"] == 0


@pytest.mark.parametrize(
    ("score", "expected_level"),
    [
        (0, "low"),
        (29, "low"),
        (30, "medium"),
        (59, "medium"),
        (60, "high"),
        (79, "high"),
        (80, "critical"),
        (100, "critical"),
    ],
)
def test_maps_score_to_risk_level(
    score: int,
    expected_level: str,
):
    assert sybil_risk_level(score) == expected_level


def test_requires_at_least_two_wallets():
    with pytest.raises(
        ValueError,
        match="at least two enriched wallets",
    ):
        analyze_sybil_clusters(
            [_wallet("sybil_alpha")]
        )


def test_rejects_duplicate_wallets():
    wallet = _wallet("sybil_alpha")

    with pytest.raises(
        ValueError,
        match="duplicate enriched wallet",
    ):
        analyze_sybil_clusters([wallet, wallet])


def test_rejects_negative_timing_window():
    with pytest.raises(
        ValueError,
        match="must be non-negative",
    ):
        analyze_sybil_clusters(
            [
                _wallet("sybil_alpha"),
                _wallet("sybil_beta"),
            ],
            timing_window_seconds=-1,
        )
