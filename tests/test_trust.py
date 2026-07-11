VALID_ADDRESS = "0x1111111111111111111111111111111111111111"


def test_check_wallet_with_full_data(client, monkeypatch):
    def fake_wallet_balance(address):
        return {
            "address": address,
            "balance_wei": "1000000000000000000",
            "balance_eth": "1",
            "network": "eth-mainnet",
        }

    def fake_transfers(address, max_count=10):
        return [
            {"hash": "0x1"},
            {"hash": "0x2"},
            {"hash": "0x3"},
            {"hash": "0x4"},
            {"hash": "0x5"},
        ]

    monkeypatch.setattr(
        "app.routers.wallets.get_wallet_balance",
        fake_wallet_balance,
    )
    monkeypatch.setattr(
        "app.routers.wallets.get_asset_transfers_for_wallet",
        fake_transfers,
    )

    response = client.post(
        "/check_wallet",
        json={"wallet_address": VALID_ADDRESS},
    )

    data = response.json()

    assert response.status_code == 200
    assert data["wallet_address"] == VALID_ADDRESS
    assert data["human_likelihood"] == "high"
    assert data["trust_tier"] == "gold"
    assert data["confidence_score"] == 0.85
    assert data["risk_flags"] == []
    assert "scored_at" in data
    assert "signals" not in data
    assert "transfers" not in data


def test_check_wallet_with_partial_transfer_data(
    client,
    monkeypatch,
):
    def fake_wallet_balance(address):
        return {
            "address": address,
            "balance_wei": "1000000000000000000",
            "balance_eth": "1",
            "network": "eth-mainnet",
        }

    def fake_transfers(address, max_count=10):
        raise RuntimeError("Alchemy rate limit reached")

    monkeypatch.setattr(
        "app.routers.wallets.get_wallet_balance",
        fake_wallet_balance,
    )
    monkeypatch.setattr(
        "app.routers.wallets.get_asset_transfers_for_wallet",
        fake_transfers,
    )

    response = client.post(
        "/check_wallet",
        json={"wallet_address": VALID_ADDRESS},
    )

    data = response.json()

    assert response.status_code == 200
    assert data["human_likelihood"] == "medium"
    assert data["trust_tier"] == "silver"
    assert data["confidence_score"] == 0.5
    assert "transfer_data_unavailable" in data["risk_flags"]


def test_check_wallet_with_low_activity(client, monkeypatch):
    def fake_wallet_balance(address):
        return {
            "address": address,
            "balance_wei": "0",
            "balance_eth": "0",
            "network": "eth-mainnet",
        }

    def fake_transfers(address, max_count=10):
        return []

    monkeypatch.setattr(
        "app.routers.wallets.get_wallet_balance",
        fake_wallet_balance,
    )
    monkeypatch.setattr(
        "app.routers.wallets.get_asset_transfers_for_wallet",
        fake_transfers,
    )

    response = client.post(
        "/check_wallet",
        json={"wallet_address": VALID_ADDRESS},
    )

    data = response.json()

    assert response.status_code == 200
    assert data["human_likelihood"] == "low"
    assert data["trust_tier"] == "bronze"
    assert data["confidence_score"] == 0.0
    assert "zero_balance" in data["risk_flags"]
    assert "no_recent_transfers" in data["risk_flags"]
    assert "low_reputation_score" in data["risk_flags"]


def test_check_wallet_rejects_invalid_address(client):
    response = client.post(
        "/check_wallet",
        json={"wallet_address": "not-a-wallet"},
    )

    assert response.status_code == 422


def test_check_wallet_returns_503_when_provider_fails(
    client,
    monkeypatch,
):
    def fake_wallet_balance(address):
        raise RuntimeError("Alchemy request timed out")

    monkeypatch.setattr(
        "app.routers.wallets.get_wallet_balance",
        fake_wallet_balance,
    )

    response = client.post(
        "/check_wallet",
        json={"wallet_address": VALID_ADDRESS},
    )

    data = response.json()

    assert response.status_code == 503
    assert "Blockchain provider unavailable" in data["detail"]
