from datetime import datetime, timedelta, timezone

from app.schemas import (
    GeneratedProofResponse,
    HumanLikelihood,
    TrustResponse,
    TrustTier,
)
from app.services.proof_service import create_signed_proof


VALID_ADDRESS = "0x1111111111111111111111111111111111111111"
TEST_SECRET = (
    "test-proof-signing-secret-that-is-longer-than-32-characters"
)


def build_signed_proof(
    *,
    now: datetime | None = None,
) -> GeneratedProofResponse:
    issued_at = now or datetime.now(timezone.utc)
    trust_result = TrustResponse(
        wallet_address=VALID_ADDRESS,
        human_likelihood=HumanLikelihood.HIGH,
        trust_tier=TrustTier.GOLD,
        confidence_score=0.91,
        risk_flags=[],
        scored_at=issued_at,
    )

    return create_signed_proof(
        trust_result,
        signing_secret=TEST_SECRET,
        now=issued_at,
    )


def test_verify_proof_accepts_a_valid_proof(client, monkeypatch):
    monkeypatch.setenv("PROOF_SIGNING_SECRET", TEST_SECRET)
    signed_proof = build_signed_proof()

    response = client.post(
        "/verify_proof",
        json=signed_proof.model_dump(mode="json"),
    )
    data = response.json()

    assert response.status_code == 200
    assert data["valid"] is True
    assert data["status"] == "valid"
    assert data["proof_id"] == str(signed_proof.proof.proof_id)
    assert datetime.fromisoformat(
        data["expires_at"].replace("Z", "+00:00")
    ) == (
        signed_proof.proof.expires_at
    )


def test_verify_proof_returns_invalid_for_tampering(client, monkeypatch):
    monkeypatch.setenv("PROOF_SIGNING_SECRET", TEST_SECRET)
    signed_proof = build_signed_proof()
    tampered = signed_proof.model_dump(mode="json")
    tampered["signature"] = "0" * 64

    response = client.post("/verify_proof", json=tampered)

    assert response.status_code == 200
    assert response.json()["valid"] is False
    assert response.json()["status"] == "invalid_or_expired"


def test_verify_proof_returns_invalid_for_expired_proof(
    client,
    monkeypatch,
):
    monkeypatch.setenv("PROOF_SIGNING_SECRET", TEST_SECRET)
    signed_proof = build_signed_proof(
        now=datetime.now(timezone.utc) - timedelta(days=2)
    )

    response = client.post(
        "/verify_proof",
        json=signed_proof.model_dump(mode="json"),
    )

    assert response.status_code == 200
    assert response.json()["valid"] is False
    assert response.json()["status"] == "invalid_or_expired"


def test_verify_proof_uses_structured_validation_errors(client):
    response = client.post(
        "/verify_proof",
        json={"proof": {}, "signature": "not-hex"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_verify_proof_requires_configured_signing_secret(
    client,
    monkeypatch,
):
    monkeypatch.delenv("PROOF_SIGNING_SECRET", raising=False)
    signed_proof = build_signed_proof()

    response = client.post(
        "/verify_proof",
        json=signed_proof.model_dump(mode="json"),
    )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == (
        "PROOF_SERVICE_ERROR"
    )
