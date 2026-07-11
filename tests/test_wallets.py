VALID_ADDRESS = "0x1111111111111111111111111111111111111111"


def test_list_wallets_empty(client):
    response = client.get("/wallets")

    assert response.status_code == 200
    assert response.json() == []


def test_ingest_wallet(client, monkeypatch):
    def fake_latest_block():
        return 999999

    monkeypatch.setattr(
        "app.routers.wallets.get_latest_block_number",
        fake_latest_block,
    )

    response = client.post(
        "/wallets/ingest",
        json={"address": VALID_ADDRESS},
    )

    data = response.json()

    assert response.status_code == 200
    assert data["status"] == "ingested"
    assert data["address"] == VALID_ADDRESS.lower()
    assert data["last_seen_block"] == 999999


def test_ingest_existing_wallet(client, monkeypatch):
    def fake_latest_block_first():
        return 111111

    def fake_latest_block_second():
        return 222222

    monkeypatch.setattr(
        "app.routers.wallets.get_latest_block_number",
        fake_latest_block_first,
    )

    first_response = client.post(
        "/wallets/ingest",
        json={"address": VALID_ADDRESS},
    )

    assert first_response.status_code == 200
    assert first_response.json()["status"] == "ingested"

    monkeypatch.setattr(
        "app.routers.wallets.get_latest_block_number",
        fake_latest_block_second,
    )

    second_response = client.post(
        "/wallets/ingest",
        json={"address": VALID_ADDRESS},
    )

    data = second_response.json()

    assert second_response.status_code == 200
    assert data["status"] == "already_exists"
    assert data["last_seen_block"] == 222222


def test_get_wallet(client, monkeypatch):
    def fake_latest_block():
        return 999999

    monkeypatch.setattr(
        "app.routers.wallets.get_latest_block_number",
        fake_latest_block,
    )

    client.post("/wallets/ingest", json={"address": VALID_ADDRESS})

    response = client.get(f"/wallets/{VALID_ADDRESS}")

    data = response.json()

    assert response.status_code == 200
    assert data["address"] == VALID_ADDRESS.lower()
    assert data["source"] == "alchemy"


def test_get_missing_wallet(client):
    response = client.get(f"/wallets/{VALID_ADDRESS}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Wallet not found"


def test_delete_wallet(client, monkeypatch):
    def fake_latest_block():
        return 999999

    monkeypatch.setattr(
        "app.routers.wallets.get_latest_block_number",
        fake_latest_block,
    )

    client.post("/wallets/ingest", json={"address": VALID_ADDRESS})

    response = client.delete(f"/wallets/{VALID_ADDRESS}")

    assert response.status_code == 200
    assert response.json() == {
        "status": "deleted",
        "address": VALID_ADDRESS.lower(),
    }


def test_wallet_balance(client, monkeypatch):
    def fake_wallet_balance(address):
        return {
            "address": address,
            "balance_wei": "1000000000000000000",
            "balance_eth": "1",
            "network": "eth-mainnet",
        }

    monkeypatch.setattr(
        "app.routers.wallets.get_wallet_balance",
        fake_wallet_balance,
    )

    response = client.get(f"/wallets/{VALID_ADDRESS}/balance")

    data = response.json()

    assert response.status_code == 200
    assert data["address"] == VALID_ADDRESS.lower()
    assert data["balance_eth"] == "1"
    assert data["network"] == "eth-mainnet"


def test_wallet_transfers(client, monkeypatch):
    def fake_transfers(address, max_count=10):
        return [
            {
                "hash": "0xtesthash",
                "from": address,
                "to": "0x2222222222222222222222222222222222222222",
                "value": 1,
                "asset": "ETH",
                "category": "external",
                "direction": "outgoing",
                "metadata": {
                    "blockTimestamp": "2026-01-01T00:00:00.000Z",
                },
            }
        ]

    monkeypatch.setattr(
        "app.routers.wallets.get_asset_transfers_for_wallet",
        fake_transfers,
    )

    response = client.get(f"/wallets/{VALID_ADDRESS}/transfers?max_count=1")

    data = response.json()

    assert response.status_code == 200
    assert data["address"] == VALID_ADDRESS.lower()
    assert data["count"] == 1
    assert data["transfers"][0]["hash"] == "0xtesthash"


def test_wallet_reputation_full_data(client, monkeypatch):
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

    response = client.get(f"/wallets/{VALID_ADDRESS}/reputation?max_count=5")

    data = response.json()

    assert response.status_code == 200
    assert data["address"] == VALID_ADDRESS.lower()
    assert data["score"] == 85
    assert data["level"] == "high"
    assert data["signals"]["transfer_status"] == "available"


def test_wallet_reputation_partial_data(client, monkeypatch):
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

    response = client.get(f"/wallets/{VALID_ADDRESS}/reputation?max_count=5")

    data = response.json()

    assert response.status_code == 200
    assert data["score"] == 50
    assert data["level"] == "medium"
    assert data["signals"]["transfer_status"] == "unavailable"
    assert data["signals"]["transfer_error"] == "Alchemy rate limit reached"


def test_invalid_wallet_balance_address(client):
    response = client.get("/wallets/not-a-wallet/balance")

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid Ethereum wallet address"
