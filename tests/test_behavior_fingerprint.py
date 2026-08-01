import pytest

from app.demo_wallets import (
    DEMO_ADDRESS_BY_KEY,
    get_demo_enriched_data,
)
from app.services.behavior_fingerprint import (
    calculate_behavior_similarity,
    generate_behavior_fingerprint,
)


def _fingerprint(scenario_key: str) -> dict:
    enriched_data = get_demo_enriched_data(
        DEMO_ADDRESS_BY_KEY[scenario_key]
    )

    assert enriched_data is not None
    return generate_behavior_fingerprint(enriched_data)


def test_generates_deterministic_fingerprint():
    enriched_data = get_demo_enriched_data(
        DEMO_ADDRESS_BY_KEY["sybil_alpha"]
    )

    assert enriched_data is not None

    first = generate_behavior_fingerprint(enriched_data)
    second = generate_behavior_fingerprint(enriched_data)

    assert first == second
    assert len(first["fingerprint_id"]) == 64
    assert first["fingerprint_version"] == "1.0"


def test_sybil_wallets_have_matching_fingerprints():
    alpha = _fingerprint("sybil_alpha")
    beta = _fingerprint("sybil_beta")

    assert alpha["address"] != beta["address"]
    assert alpha["fingerprint_id"] == beta["fingerprint_id"]

    result = calculate_behavior_similarity(alpha, beta)

    assert result["similarity_score"] == 1.0
    assert result["matching_fingerprint"] is True
    assert result["high_behavior_similarity"] is True


def test_different_behavior_has_lower_similarity():
    result = calculate_behavior_similarity(
        _fingerprint("established_human"),
        _fingerprint("burst_bot"),
    )

    assert 0.0 <= result["similarity_score"] < 0.85
    assert result["matching_fingerprint"] is False
    assert result["high_behavior_similarity"] is False


def test_fingerprint_contains_explainable_components():
    fingerprint = _fingerprint("sybil_alpha")
    components = fingerprint["components"]

    assert set(components) == {
        "version",
        "activity",
        "transfer_behavior",
        "timing",
        "diversity",
        "contracts",
        "automation",
    }
    assert components["activity"]["total_transfers"] == 6
    assert components["transfer_behavior"][
        "unique_funder_count"
    ] == 1
    assert components["transfer_behavior"][
        "unique_recipient_count"
    ] == 2
    assert components["timing"]["active_day_count"] == 3


def test_similarity_is_symmetric():
    left = _fingerprint("normal_active")
    right = _fingerprint("contract_heavy")

    forward = calculate_behavior_similarity(left, right)
    reverse = calculate_behavior_similarity(right, left)

    assert forward["similarity_score"] == reverse[
        "similarity_score"
    ]
    assert forward["component_scores"] == reverse[
        "component_scores"
    ]


def test_requires_wallet_address():
    with pytest.raises(
        ValueError,
        match="must contain a wallet address",
    ):
        generate_behavior_fingerprint(
            {
                "transfers": [],
                "nft_transfers": [],
                "contract_addresses": [],
                "activity_range": {},
            }
        )


def test_similarity_requires_components():
    with pytest.raises(
        ValueError,
        match="must contain components",
    ):
        calculate_behavior_similarity(
            {"address": "0x1"},
            {"address": "0x2"},
        )
