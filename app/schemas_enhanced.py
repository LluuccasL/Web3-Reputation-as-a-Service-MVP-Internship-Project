from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas import WalletAddress


class AdvancedFeaturesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_transfers: int
    unique_interaction_addresses: int
    transaction_diversity: float
    unique_contracts: int
    contract_interaction_count: int
    contract_interaction_ratio: float
    transaction_entropy: float
    wallet_lifespan_days: float | None
    nft_transfer_count: int
    has_nft_activity: bool


class RiskFlagResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    flag_id: str
    severity: str
    signal_type: str
    category: str
    evidence: str
    metrics: dict[str, Any] = Field(default_factory=dict)


class ScoreFactorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    factor_id: str
    direction: str
    points: int
    evidence: str


class EnhancedTrustResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    wallet_address: WalletAddress

    base_score: int
    enhanced_score: int
    score_adjustment: int

    human_likelihood: str
    trust_tier: str
    confidence_score: float

    data_coverage: float
    source_status: dict[str, str]
    data_errors: dict[str, str]

    risk_level: str
    risk_points: int
    risk_penalty: int
    positive_points: int

    advanced_features: AdvancedFeaturesResponse

    risk_flags: list[RiskFlagResponse]
    informational_flags: list[RiskFlagResponse]
    legacy_risk_flags: list[str]
    score_factors: list[ScoreFactorResponse]

    base_human_likelihood: str
    base_trust_tier: str
