def test_root(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {"message": "Web3 Trust API is running"}


def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_latest_block(client, monkeypatch):
    def fake_latest_block():
        return 123456

    monkeypatch.setattr(
        "app.routers.chain.get_latest_block_number",
        fake_latest_block,
    )

    response = client.get("/chain/latest-block")

    assert response.status_code == 200
    assert response.json() == {"latest_block": 123456}
