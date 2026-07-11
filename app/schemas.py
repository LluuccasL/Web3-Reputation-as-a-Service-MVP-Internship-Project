from datetime import datetime
from enum import Enum
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


# ---------------------------------------------------------------------------
# Week 1: Wallet ingestion schemas
# ---------------------------------------------------------------------------

class WalletIngestRequest(BaseModel):
    address: str


class WalletIngestResponse(BaseModel):
    status: str
    address: str
    last_seen_block: int | None = None


# ---------------------------------------------------------------------------
# Week 2: Wallet data and reputation schemas
# ---------------------------------------------------------------------------

class WalletResponse(BaseModel):
    id: int
    address: str
    source: str
    last_seen_block: int | None = None
    created_at: datetime | None = None


class WalletBalanceResponse(BaseModel):
    address: str
    balance_wei: str
    balance_eth: str
    network: str


class WalletTransfersResponse(BaseModel):
    address: str
    count: int
    transfers: list[dict[str, Any]]


class WalletReputationResponse(BaseModel):
    address: str
    score: int
    level: str
    signals: dict[str, Any]


# ---------------------------------------------------------------------------
# Week 3: Public trust API schemas
# ---------------------------------------------------------------------------

WalletAddress = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        pattern=r"^0x[a-fA-F0-9]{40}$",
    ),
]

HexDigest = Annotated[
    str,
    StringConstraints(
        pattern=r"^[a-f0-9]{64}$",
    ),
]


class HumanLikelihood(str, Enum):
    """Public estimate of whether a wallet represents normal human activity."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TrustTier(str, Enum):
    """Public reputation tier assigned to a wallet."""

    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"


class CheckWalletRequest(BaseModel):
    """Request body for checking a wallet's public trust signals."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "wallet_address": "0x1234567890abcdef1234567890abcdef12345678"
            }
        },
    )

    wallet_address: WalletAddress = Field(
        description="Ethereum wallet address beginning with 0x."
    )


class TrustResponse(BaseModel):
    """Privacy-safe trust information returned to external applications."""

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
        json_schema_extra={
            "example": {
                "wallet_address": "0x1234567890abcdef1234567890abcdef12345678",
                "human_likelihood": "high",
                "trust_tier": "silver",
                "confidence_score": 0.87,
                "risk_flags": [],
                "scored_at": "2026-07-10T12:00:00Z",
            }
        },
    )

    wallet_address: WalletAddress = Field(
        description="Wallet address whose reputation was evaluated."
    )

    human_likelihood: HumanLikelihood = Field(
        description="Estimated likelihood that the wallet represents human activity."
    )

    trust_tier: TrustTier = Field(
        description="Public reputation tier assigned by the scoring system."
    )

    confidence_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence in the trust result, from 0.0 through 1.0.",
    )

    risk_flags: list[str] = Field(
        default_factory=list,
        description="Privacy-safe explanations of detected risk signals.",
    )

    scored_at: datetime = Field(
        description="UTC date and time when the reputation score was calculated."
    )


# ---------------------------------------------------------------------------
# Week 3: Signed proof schemas
# ---------------------------------------------------------------------------

class GenerateProofRequest(BaseModel):
    """Request body for generating a signed wallet trust proof."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "wallet_address": "0x1234567890abcdef1234567890abcdef12345678",
                "valid_for_hours": 24,
            }
        },
    )

    wallet_address: WalletAddress = Field(
        description="Ethereum wallet address to evaluate."
    )

    valid_for_hours: int = Field(
        default=24,
        ge=1,
        le=168,
        description="Number of hours before the proof expires.",
    )


class ProofPayload(BaseModel):
    """Claims protected by the proof signature."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "proof_id": "550e8400-e29b-41d4-a716-446655440000",
                "wallet_hash": (
                    "1234567890abcdef1234567890abcdef"
                    "1234567890abcdef1234567890abcdef"
                ),
                "human_likelihood": "high",
                "trust_tier": "gold",
                "confidence_score": 0.85,
                "issued_at": "2026-07-11T08:00:00Z",
                "expires_at": "2026-07-12T08:00:00Z",
            }
        },
    )

    proof_id: UUID
    wallet_hash: HexDigest

    human_likelihood: HumanLikelihood
    trust_tier: TrustTier

    confidence_score: float = Field(
        ge=0.0,
        le=1.0,
    )

    issued_at: datetime
    expires_at: datetime


class GeneratedProofResponse(BaseModel):
    """Signed proof returned by the proof-generation service."""

    model_config = ConfigDict(extra="forbid")

    proof: ProofPayload
    signature: HexDigest
