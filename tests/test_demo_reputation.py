from app.demo_wallets import DEMO_ADDRESS_BY_KEY
from app.routers import wallets


def _fail_live_request(*args, **kwargs):
    raise AssertionError(
        "A demo wallet must not call the live provider."
    )


def test_demo_wallets_receive_expected_original_scores(
    monkeypatch,
):
    monkeypatch.setenv("DEMO_MODE", "true")

    monkeypatch.setattr(
        wallets,
        "get_wallet_balance",
        _fail_live_request,
    )
    monkeypatch.setattr(
        wallets,
        "get_asset_transfers_for_wallet",
        _fail_live_request,
    )

    expected_scores = {
        "established_human": 85,
        "normal_active": 70,
        "new_wallet": 25,
        "empty_wallet": 0,
        "burst_bot": 45,
        "repetitive_bot": 45,
        "contract_heavy": 85,
        "nft_automation": 60,
        "sybil_alpha": 70,
        "sybil_beta": 70,
        "sybil_gamma": 70,
        "partial_data_control": 50,
    }

    for scenario_key, expected_score in expected_scores.items():
        result = wallets.calculate_wallet_reputation(
            DEMO_ADDRESS_BY_KEY[scenario_key]
        )

        assert result.score == expected_score


def test_established_wallet_has_high_original_reputation(
    monkeypatch,
):
    monkeypatch.setenv("DEMO_MODE", "true")

    result = wallets.calculate_wallet_reputation(
        DEMO_ADDRESS_BY_KEY["established_human"]
    )

    assert result.score == 85
    assert result.level == "high"
    assert result.signals["network"] == "synthetic-demo"


def test_demo_reputation_respects_max_count(
    monkeypatch,
):
    monkeypatch.setenv("DEMO_MODE", "true")

    address = DEMO_ADDRESS_BY_KEY["nft_automation"]

    five_transfer_result = (
        wallets.calculate_wallet_reputation(
            address,
            max_count=5,
        )
    )

    ten_transfer_result = (
        wallets.calculate_wallet_reputation(
            address,
            max_count=10,
        )
    )

    assert five_transfer_result.score == 45
    assert ten_transfer_result.score == 60


def test_live_wallet_still_uses_blockchain_provider(
    monkeypatch,
):
    monkeypatch.setenv("DEMO_MODE", "false")

    monkeypatch.setattr(
        wallets,
        "get_wallet_balance",
        lambda address: {
            "balance_eth": "1.0",
            "network": "test-network",
        },
    )

    monkeypatch.setattr(
        wallets,
        "get_asset_transfers_for_wallet",
        lambda address, max_count: [
            {"hash": str(index)}
            for index in range(10)
        ],
    )

    result = wallets.calculate_wallet_reputation(
        "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    )

    assert result.score == 100
    assert result.signals["network"] == "test-network"
