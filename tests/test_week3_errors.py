VALID_ADDRESS = "0x1111111111111111111111111111111111111111"


def test_missing_key_returns_structured_error(client):
    client.headers.pop("X-API-Key", None)

    response = client.post(
        "/check_wallet",
        json={"wallet_address": VALID_ADDRESS},
    )

    data = response.json()

    assert response.status_code == 401
    assert data["error"]["code"] == "INVALID_API_KEY"
    assert data["error"]["message"] == (
        "Invalid or missing API key."
    )

    assert data["error"]["request_id"] == (
        response.headers["X-Request-ID"]
    )


def test_validation_error_is_structured(client):
    response = client.post(
        "/check_wallet",
        json={"wallet_address": "invalid-wallet"},
    )

    data = response.json()

    assert response.status_code == 422
    assert data["error"]["code"] == "INVALID_REQUEST"
    assert data["error"]["request_id"] == (
        response.headers["X-Request-ID"]
    )


def test_provider_error_is_structured(
    client,
    monkeypatch,
):
    def fake_wallet_balance(address):
        raise RuntimeError("Provider timed out")

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
    assert data["error"]["code"] == (
        "BLOCKCHAIN_PROVIDER_ERROR"
    )

    assert data["error"]["request_id"] == (
        response.headers["X-Request-ID"]
    )
