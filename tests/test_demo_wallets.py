import re

from app.demo_wallets import (
    DEMO_ADDRESS_BY_KEY,
    DEMO_WALLETS,
    SHARED_SYBIL_FUNDER,
    get_demo_enriched_data,
    list_demo_wallets,
)


ADDRESS_PATTERN = re.compile(
    r"^0x[a-fA-F0-9]{40}$"
)


def test_demo_catalog_contains_twelve_unique_wallets():
    wallets = list_demo_wallets()
    addresses = [
        wallet["address"]
        for wallet in wallets
    ]

    assert len(wallets) == 12
    assert len(set(addresses)) == 12

    assert all(
        ADDRESS_PATTERN.fullmatch(address)
        for address in addresses
    )

    assert all(
        wallet["synthetic"] is True
        for wallet in wallets
    )


def test_demo_enrichment_returns_independent_copy():
    address = DEMO_ADDRESS_BY_KEY["burst_bot"]

    first_result = get_demo_enriched_data(address)
    second_result = get_demo_enriched_data(address)

    assert first_result is not None
    assert second_result is not None
    assert first_result is not second_result

    first_result["transfers"].clear()

    assert second_result["transfers"]
    assert second_result["is_demo"] is True
    assert second_result["demo_scenario"] == "burst_bot"


def test_sybil_wallets_share_the_same_funder():
    sybil_keys = [
        "sybil_alpha",
        "sybil_beta",
        "sybil_gamma",
    ]

    assert all(
        DEMO_WALLETS[key]["group_id"]
        == "demo_sybil_cluster"
        for key in sybil_keys
    )

    for key in sybil_keys:
        address = DEMO_ADDRESS_BY_KEY[key]
        enriched_data = get_demo_enriched_data(address)

        assert enriched_data is not None

        incoming_funders = {
            transfer["from"]
            for transfer in enriched_data["transfers"]
            if transfer["to"] == address
        }

        assert SHARED_SYBIL_FUNDER in incoming_funders


def test_partial_data_wallet_has_reduced_sources():
    address = DEMO_ADDRESS_BY_KEY[
        "partial_data_control"
    ]

    enriched_data = get_demo_enriched_data(address)

    assert enriched_data is not None
    assert enriched_data["source_status"]["transfers"] == "partial"

    assert (
        enriched_data["source_status"]["nft_activity"]
        == "unavailable"
    )

    assert "nft_activity" in enriched_data["errors"]
