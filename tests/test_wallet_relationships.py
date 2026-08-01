import pytest

from app.demo_wallets import (
    COMMON_SYBIL_RECIPIENTS,
    DEMO_ADDRESS_BY_KEY,
    SHARED_SYBIL_FUNDER,
    get_demo_enriched_data,
)
from app.services.wallet_relationships import (
    compare_wallet_relationships,
    extract_wallet_relationships,
)


def _profile(scenario_key: str) -> dict:
    enriched_data = get_demo_enriched_data(
        DEMO_ADDRESS_BY_KEY[scenario_key]
    )

    assert enriched_data is not None
    return extract_wallet_relationships(enriched_data)


def test_extracts_sybil_relationship_data():
    profile = _profile("sybil_alpha")

    assert profile["funders"] == [SHARED_SYBIL_FUNDER]
    assert profile["recipients"] == sorted(
        COMMON_SYBIL_RECIPIENTS
    )
    assert profile["incoming_transfer_count"] == 1
    assert profile["outgoing_transfer_count"] == 5
    assert len(profile["outgoing_timestamps"]) == 5


def test_detects_shared_sybil_evidence():
    result = compare_wallet_relationships(
        _profile("sybil_alpha"),
        _profile("sybil_beta"),
    )

    assert result["shared_funders"] == [
        SHARED_SYBIL_FUNDER
    ]
    assert result["shared_recipients"] == sorted(
        COMMON_SYBIL_RECIPIENTS
    )
    assert result["coordinated_outgoing_transfers"] == 5
    assert result["evidence_types"] == [
        "shared_funder",
        "shared_recipient",
        "coordinated_timing",
    ]
    assert result["has_relationship"] is True


def test_independent_wallets_have_no_relationship():
    result = compare_wallet_relationships(
        _profile("established_human"),
        _profile("normal_active"),
    )

    assert result["shared_funders"] == []
    assert result["shared_recipients"] == []
    assert result["shared_contracts"] == []
    assert result["coordinated_outgoing_transfers"] == 0
    assert result["evidence_types"] == []
    assert result["has_relationship"] is False


def test_extract_requires_wallet_address():
    with pytest.raises(
        ValueError,
        match="must contain a wallet address",
    ):
        extract_wallet_relationships({"transfers": []})


def test_rejects_negative_timing_window():
    with pytest.raises(
        ValueError,
        match="must be non-negative",
    ):
        compare_wallet_relationships(
            _profile("sybil_alpha"),
            _profile("sybil_beta"),
            timing_window_seconds=-1,
        )
