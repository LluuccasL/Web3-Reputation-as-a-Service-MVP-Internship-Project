VALID_ADDRESS = "0x1111111111111111111111111111111111111111"


def mock_wallet_data(monkeypatch):
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


def test_requests_below_limit_succeed(
    client,
    monkeypatch,
):
    monkeypatch.setenv("RATE_LIMIT_REQUESTS", "2")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "60")

    mock_wallet_data(monkeypatch)

    first_response = client.post(
        "/check_wallet",
        json={"wallet_address": VALID_ADDRESS},
    )

    second_response = client.post(
        "/check_wallet",
        json={"wallet_address": VALID_ADDRESS},
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    assert first_response.headers["X-RateLimit-Limit"] == "2"
    assert first_response.headers["X-RateLimit-Remaining"] == "1"

    assert second_response.headers["X-RateLimit-Remaining"] == "0"


def test_request_above_limit_returns_429(
    client,
    monkeypatch,
):
    monkeypatch.setenv("RATE_LIMIT_REQUESTS", "2")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "60")

    mock_wallet_data(monkeypatch)

    for _ in range(2):
        response = client.post(
            "/check_wallet",
            json={"wallet_address": VALID_ADDRESS},
        )

        assert response.status_code == 200

    blocked_response = client.post(
        "/check_wallet",
        json={"wallet_address": VALID_ADDRESS},
    )

    data = blocked_response.json()

    assert blocked_response.status_code == 429
    assert data["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert data["error"]["request_id"]
    assert blocked_response.headers["Retry-After"]


def test_different_api_keys_have_separate_limits(
    client,
    monkeypatch,
):
    monkeypatch.setenv("RATE_LIMIT_REQUESTS", "1")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "60")
    monkeypatch.setenv("API_KEYS", "key-one,key-two")

    mock_wallet_data(monkeypatch)

    client.headers["X-API-Key"] = "key-one"

    first_key_response = client.post(
        "/check_wallet",
        json={"wallet_address": VALID_ADDRESS},
    )

    client.headers["X-API-Key"] = "key-two"

    second_key_response = client.post(
        "/check_wallet",
        json={"wallet_address": VALID_ADDRESS},
    )

    assert first_key_response.status_code == 200
    assert second_key_response.status_code == 200

    client.headers["X-API-Key"] = "key-one"

    blocked_response = client.post(
        "/check_wallet",
        json={"wallet_address": VALID_ADDRESS},
    )

    assert blocked_response.status_code == 429
