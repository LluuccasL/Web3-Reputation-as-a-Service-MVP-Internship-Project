from datetime import datetime, timedelta, timezone

from app.schemas import GeneratedProofResponse
from app.services.proof_service import verify_signed_proof


VALID_ADDRESS = "0x1111111111111111111111111111111111111111"

TEST_SECRET = (
    "test-proof-signing-secret-that-is-longer-than-32-characters"
)


def set_test_secret(monkeypatch):
    monkeypatch.setenv(
        "PROOF_SIGNING_SECRET",
        TEST_SECRET,
    )


def mock_high_reputation_data(monkeypatch):
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


def test_generate_proof_success(
    client,
    monkeypatch,
):
    set_test_secret(monkeypatch)
    mock_high_reputation_data(monkeypatch)

    response = client.post(
        "/generate_proof",
        json={
            "wallet_address": VALID_ADDRESS,
            "valid_for_hours": 24,
        },
    )

    data = response.json()

    assert response.status_code == 200

    assert "proof" in data
    assert "signature" in data

    assert "proof_id" in data["proof"]
    assert "wallet_hash" in data["proof"]

    assert data["proof"]["human_likelihood"] == "high"
    assert data["proof"]["trust_tier"] == "gold"
    assert data["proof"]["confidence_score"] == 0.85

    assert len(data["proof"]["wallet_hash"]) == 64
    assert len(data["signature"]) == 64

    assert VALID_ADDRESS not in response.text


def test_generated_proof_signature_is_valid(
    client,
    monkeypatch,
):
    set_test_secret(monkeypatch)
    mock_high_reputation_data(monkeypatch)

    response = client.post(
        "/generate_proof",
        json={
            "wallet_address": VALID_ADDRESS,
            "valid_for_hours": 24,
        },
    )

    assert response.status_code == 200

    signed_proof = GeneratedProofResponse.model_validate(
        response.json()
    )

    verification_time = (
        signed_proof.proof.issued_at
        + timedelta(minutes=1)
    )

    assert verify_signed_proof(
        signed_proof,
        signing_secret=TEST_SECRET,
        now=verification_time,
    )


def test_generate_proof_uses_requested_expiration(
    client,
    monkeypatch,
):
    set_test_secret(monkeypatch)
    mock_high_reputation_data(monkeypatch)

    response = client.post(
        "/generate_proof",
        json={
            "wallet_address": VALID_ADDRESS,
            "valid_for_hours": 12,
        },
    )

    assert response.status_code == 200

    data = response.json()

    issued_at = datetime.fromisoformat(
        data["proof"]["issued_at"].replace("Z", "+00:00")
    )

    expires_at = datetime.fromisoformat(
        data["proof"]["expires_at"].replace("Z", "+00:00")
    )

    assert expires_at - issued_at == timedelta(hours=12)


def test_generate_proof_uses_default_expiration(
    client,
    monkeypatch,
):
    set_test_secret(monkeypatch)
    mock_high_reputation_data(monkeypatch)

    response = client.post(
        "/generate_proof",
        json={
            "wallet_address": VALID_ADDRESS,
        },
    )

    assert response.status_code == 200

    data = response.json()

    issued_at = datetime.fromisoformat(
        data["proof"]["issued_at"].replace("Z", "+00:00")
    )

    expires_at = datetime.fromisoformat(
        data["proof"]["expires_at"].replace("Z", "+00:00")
    )

    assert expires_at - issued_at == timedelta(hours=24)


def test_generate_proof_rejects_invalid_wallet(client):
    response = client.post(
        "/generate_proof",
        json={
            "wallet_address": "not-a-wallet",
            "valid_for_hours": 24,
        },
    )

    assert response.status_code == 422


def test_generate_proof_rejects_too_short_validity(client):
    response = client.post(
        "/generate_proof",
        json={
            "wallet_address": VALID_ADDRESS,
            "valid_for_hours": 0,
        },
    )

    assert response.status_code == 422


def test_generate_proof_rejects_too_long_validity(client):
    response = client.post(
        "/generate_proof",
        json={
            "wallet_address": VALID_ADDRESS,
            "valid_for_hours": 169,
        },
    )

    assert response.status_code == 422


def test_generate_proof_returns_503_for_provider_failure(
    client,
    monkeypatch,
):
    set_test_secret(monkeypatch)

    def fake_wallet_balance(address):
        raise RuntimeError("Alchemy request timed out")

    monkeypatch.setattr(
        "app.routers.wallets.get_wallet_balance",
        fake_wallet_balance,
    )

    response = client.post(
        "/generate_proof",
        json={
            "wallet_address": VALID_ADDRESS,
            "valid_for_hours": 24,
        },
    )

    data = response.json()

    assert response.status_code == 503
    assert data["error"]["code"] == "BLOCKCHAIN_PROVIDER_ERROR"
    assert data["error"]["message"] == (
        "The blockchain provider is temporarily unavailable."
    )
    assert data["detail"] == data["error"]["message"]


def test_generate_proof_fails_without_signing_secret(
    client,
    monkeypatch,
):
    monkeypatch.delenv(
        "PROOF_SIGNING_SECRET",
        raising=False,
    )

    mock_high_reputation_data(monkeypatch)

    response = client.post(
        "/generate_proof",
        json={
            "wallet_address": VALID_ADDRESS,
            "valid_for_hours": 24,
        },
    )

    data = response.json()

    assert response.status_code == 500
    assert data["error"]["code"] == "PROOF_SERVICE_ERROR"
    assert data["error"]["message"] == (
        "The proof service is not configured correctly."
    )
    assert data["detail"] == data["error"]["message"]
