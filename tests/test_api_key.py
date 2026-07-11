VALID_ADDRESS = "0x1111111111111111111111111111111111111111"


def test_check_wallet_rejects_missing_api_key(client):
    client.headers.pop("X-API-Key", None)

    response = client.post(
        "/check_wallet",
        json={"wallet_address": VALID_ADDRESS},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Invalid or missing API key."
    )


def test_check_wallet_rejects_invalid_api_key(client):
    client.headers["X-API-Key"] = "incorrect-api-key"

    response = client.post(
        "/check_wallet",
        json={"wallet_address": VALID_ADDRESS},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Invalid or missing API key."
    )


def test_check_wallet_accepts_valid_api_key(
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
        return [{"hash": "0x1"}]

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

    assert response.status_code == 200


def test_generate_proof_rejects_missing_api_key(client):
    client.headers.pop("X-API-Key", None)

    response = client.post(
        "/generate_proof",
        json={
            "wallet_address": VALID_ADDRESS,
            "valid_for_hours": 24,
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Invalid or missing API key."
    )


def test_health_remains_public(client):
    client.headers.pop("X-API-Key", None)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_wallet_routes_remain_public(client):
    client.headers.pop("X-API-Key", None)

    response = client.get("/wallets")

    assert response.status_code == 200


def test_missing_server_api_key_configuration(
    client,
    monkeypatch,
):
    monkeypatch.delenv(
        "API_KEYS",
        raising=False,
    )

    client.headers["X-API-Key"] = "some-supplied-key"

    response = client.post(
        "/check_wallet",
        json={"wallet_address": VALID_ADDRESS},
    )

    assert response.status_code == 500
    assert response.json()["detail"] == (
        "API key authentication is not configured."
    )


def test_second_configured_api_key_is_accepted(
    client,
    monkeypatch,
):
    monkeypatch.setenv(
        "API_KEYS",
        "first-valid-key,second-valid-key",
    )

    client.headers["X-API-Key"] = "second-valid-key"

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

    assert response.status_code == 200
