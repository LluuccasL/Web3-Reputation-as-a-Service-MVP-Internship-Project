import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from dotenv import load_dotenv

from app.schemas import (
    GeneratedProofResponse,
    ProofPayload,
    TrustResponse,
)

load_dotenv()

MINIMUM_SECRET_LENGTH = 32
MAX_PROOF_HOURS = 168


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    """
    Convert a datetime to timezone-aware UTC.

    Naive datetime values are treated as UTC.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def get_signing_secret(
    signing_secret: str | None = None,
) -> bytes:
    """
    Return the proof signing secret as bytes.

    An explicit secret is useful for tests. In normal application use, the
    secret comes from PROOF_SIGNING_SECRET in the environment.
    """
    secret = signing_secret or os.getenv("PROOF_SIGNING_SECRET")

    if not secret:
        raise RuntimeError(
            "Missing PROOF_SIGNING_SECRET in the environment."
        )

    if len(secret) < MINIMUM_SECRET_LENGTH:
        raise RuntimeError(
            "PROOF_SIGNING_SECRET must contain at least 32 characters."
        )

    return secret.encode("utf-8")


def hash_wallet_address(wallet_address: str) -> str:
    """
    Hash a normalized wallet address so the proof does not expose it.
    """
    normalized_address = wallet_address.strip().lower()

    return hashlib.sha256(
        normalized_address.encode("utf-8")
    ).hexdigest()


def canonical_proof_bytes(proof: ProofPayload) -> bytes:
    """
    Serialize proof claims deterministically before signing.
    """
    proof_data = proof.model_dump(mode="json")

    canonical_json = json.dumps(
        proof_data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    return canonical_json.encode("utf-8")


def sign_proof_payload(
    proof: ProofPayload,
    signing_secret: str | None = None,
) -> str:
    """
    Sign the canonical proof payload using HMAC-SHA256.
    """
    secret_bytes = get_signing_secret(signing_secret)

    return hmac.new(
        secret_bytes,
        canonical_proof_bytes(proof),
        hashlib.sha256,
    ).hexdigest()


def create_signed_proof(
    trust_result: TrustResponse,
    valid_for_hours: int = 24,
    signing_secret: str | None = None,
    now: datetime | None = None,
) -> GeneratedProofResponse:
    """
    Create a signed, expiring proof from a wallet trust result.
    """
    if valid_for_hours < 1 or valid_for_hours > MAX_PROOF_HOURS:
        raise ValueError(
            "valid_for_hours must be between 1 and 168."
        )

    issued_at = as_utc(now or utc_now())
    expires_at = issued_at + timedelta(hours=valid_for_hours)

    proof = ProofPayload(
        proof_id=uuid4(),
        wallet_hash=hash_wallet_address(
            trust_result.wallet_address
        ),
        human_likelihood=trust_result.human_likelihood,
        trust_tier=trust_result.trust_tier,
        confidence_score=trust_result.confidence_score,
        issued_at=issued_at,
        expires_at=expires_at,
    )

    signature = sign_proof_payload(
        proof,
        signing_secret=signing_secret,
    )

    return GeneratedProofResponse(
        proof=proof,
        signature=signature,
    )


def verify_signed_proof(
    signed_proof: GeneratedProofResponse,
    signing_secret: str | None = None,
    now: datetime | None = None,
) -> bool:
    """
    Verify both the signature and the proof validity period.
    """
    expected_signature = sign_proof_payload(
        signed_proof.proof,
        signing_secret=signing_secret,
    )

    if not hmac.compare_digest(
        expected_signature,
        signed_proof.signature,
    ):
        return False

    current_time = as_utc(now or utc_now())
    issued_at = as_utc(signed_proof.proof.issued_at)
    expires_at = as_utc(signed_proof.proof.expires_at)

    if expires_at <= issued_at:
        return False

    if current_time < issued_at:
        return False

    if current_time >= expires_at:
        return False

    return True
