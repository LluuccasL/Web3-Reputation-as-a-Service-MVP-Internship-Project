from datetime import datetime, timedelta, timezone

import pytest

from app.schemas import (
    HumanLikelihood,
    TrustResponse,
    TrustTier,
)
from app.services.proof_service import (
    create_signed_proof,
    hash_wallet_address,
    verify_signed_proof,
)


VALID_ADDRESS = "0x1111111111111111111111111111111111111111"
SECOND_ADDRESS = "0x2222222222222222222222222222222222222222"

TEST_SECRET = (
    "test-proof-signing-secret-that-is-longer-than-32-characters"
)

FIXED_TIME = datetime(
    2026,
    7,
    11,
    8,
    0,
    0,
    tzinfo=timezone.utc,
)


def build_trust_response(
    wallet_address: str = VALID_ADDRESS,
) -> TrustResponse:
    return TrustResponse(
        wallet_address=wallet_address,
        human_likelihood=HumanLikelihood.HIGH,
        trust_tier=TrustTier.GOLD,
        confidence_score=0.85,
        risk_flags=[],
        scored_at=FIXED_TIME,
    )


def test_create_signed_proof_hides_raw_wallet_address():
    signed_proof = create_signed_proof(
        build_trust_response(),
        signing_secret=TEST_SECRET,
        now=FIXED_TIME,
    )

    serialized_proof = signed_proof.model_dump_json()

    assert VALID_ADDRESS not in serialized_proof

    assert signed_proof.proof.wallet_hash == (
        hash_wallet_address(VALID_ADDRESS)
    )

    assert signed_proof.proof.human_likelihood == (
        HumanLikelihood.HIGH
    )

    assert signed_proof.proof.trust_tier == TrustTier.GOLD
    assert signed_proof.proof.confidence_score == 0.85


def test_valid_proof_signature_verifies():
    signed_proof = create_signed_proof(
        build_trust_response(),
        signing_secret=TEST_SECRET,
        now=FIXED_TIME,
    )

    result = verify_signed_proof(
        signed_proof,
        signing_secret=TEST_SECRET,
        now=FIXED_TIME + timedelta(minutes=30),
    )

    assert result is True


def test_changing_claim_invalidates_signature():
    signed_proof = create_signed_proof(
        build_trust_response(),
        signing_secret=TEST_SECRET,
        now=FIXED_TIME,
    )

    changed_payload = signed_proof.proof.model_copy(
        update={"confidence_score": 0.1}
    )

    tampered_proof = signed_proof.model_copy(
        update={"proof": changed_payload}
    )

    result = verify_signed_proof(
        tampered_proof,
        signing_secret=TEST_SECRET,
        now=FIXED_TIME + timedelta(minutes=30),
    )

    assert result is False


def test_expired_proof_does_not_verify():
    signed_proof = create_signed_proof(
        build_trust_response(),
        valid_for_hours=1,
        signing_secret=TEST_SECRET,
        now=FIXED_TIME,
    )

    result = verify_signed_proof(
        signed_proof,
        signing_secret=TEST_SECRET,
        now=FIXED_TIME + timedelta(hours=2),
    )

    assert result is False


def test_different_wallets_produce_different_hashes():
    first_proof = create_signed_proof(
        build_trust_response(VALID_ADDRESS),
        signing_secret=TEST_SECRET,
        now=FIXED_TIME,
    )

    second_proof = create_signed_proof(
        build_trust_response(SECOND_ADDRESS),
        signing_secret=TEST_SECRET,
        now=FIXED_TIME,
    )

    assert (
        first_proof.proof.wallet_hash
        != second_proof.proof.wallet_hash
    )


def test_wallet_hash_is_case_insensitive():
    lowercase_hash = hash_wallet_address(VALID_ADDRESS)
    uppercase_hash = hash_wallet_address(VALID_ADDRESS.upper())

    assert lowercase_hash == uppercase_hash


def test_invalid_validity_period_is_rejected():
    with pytest.raises(
        ValueError,
        match="valid_for_hours must be between 1 and 168",
    ):
        create_signed_proof(
            build_trust_response(),
            valid_for_hours=169,
            signing_secret=TEST_SECRET,
            now=FIXED_TIME,
        )


def test_missing_signing_secret_is_rejected(monkeypatch):
    monkeypatch.delenv(
        "PROOF_SIGNING_SECRET",
        raising=False,
    )

    with pytest.raises(
        RuntimeError,
        match="Missing PROOF_SIGNING_SECRET",
    ):
        create_signed_proof(
            build_trust_response(),
            now=FIXED_TIME,
        )
