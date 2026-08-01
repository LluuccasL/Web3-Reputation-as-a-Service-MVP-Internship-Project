from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)

from app.schemas import HexDigest, WalletAddress


SybilRiskLevel = Literal[
    "low",
    "medium",
    "high",
    "critical",
]

ClusterId = Annotated[
    str,
    StringConstraints(pattern=r"^sybil-[a-f0-9]{12}$"),
]


class SybilAnalyzeRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "wallet_addresses": [
                    "0x1111111111111111111111111111111111111111",
                    "0x2222222222222222222222222222222222222222",
                ],
                "timing_window_seconds": 300,
            }
        },
    )

    wallet_addresses: list[WalletAddress] = Field(
        min_length=2,
        max_length=25,
        description="Two through 25 Ethereum wallets to compare.",
    )

    timing_window_seconds: int = Field(
        default=300,
        ge=0,
        le=86400,
        description=(
            "Maximum timing difference used for coordinated activity."
        ),
    )

    @field_validator("wallet_addresses")
    @classmethod
    def normalize_unique_addresses(
        cls,
        addresses: list[str],
    ) -> list[str]:
        normalized = [
            address.lower()
            for address in addresses
        ]

        if len(set(normalized)) != len(normalized):
            raise ValueError(
                "wallet_addresses must not contain duplicates"
            )

        return normalized


class RelatedWalletResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    address: WalletAddress
    relationship_strength: float = Field(
        ge=0.0,
        le=1.0,
    )
    behavior_similarity: float = Field(
        ge=0.0,
        le=1.0,
    )
    matching_fingerprint: bool
    evidence_types: list[str]
    shared_funders: list[WalletAddress]
    shared_recipients: list[WalletAddress]
    shared_contracts: list[WalletAddress]
    coordinated_outgoing_transfers: int = Field(ge=0)


class SybilWalletResultResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    address: WalletAddress
    sybil_risk_score: int = Field(ge=0, le=100)
    sybil_risk_level: SybilRiskLevel
    cluster_id: ClusterId | None
    cluster_size: int = Field(ge=1)
    cluster_density: float = Field(
        ge=0.0,
        le=1.0,
    )
    related_wallets: list[RelatedWalletResponse]
    risk_flags: list[str]
    explanations: list[str]
    fingerprint_id: HexDigest


class SybilClusterResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cluster_id: ClusterId
    cluster_size: int = Field(ge=2)
    wallet_addresses: list[WalletAddress]
    density: float = Field(
        ge=0.0,
        le=1.0,
    )
    sybil_risk_score: int = Field(ge=0, le=100)
    sybil_risk_level: SybilRiskLevel
    risk_flags: list[str]
    explanations: list[str]


class RelationshipGraphNodeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: WalletAddress
    node_type: Literal["wallet"]


class RelationshipGraphEdgeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: WalletAddress
    target: WalletAddress
    relationship_strength: float = Field(
        ge=0.0,
        le=1.0,
    )
    behavior_similarity: float = Field(
        ge=0.0,
        le=1.0,
    )
    matching_fingerprint: bool
    evidence_types: list[str]
    shared_funders: list[WalletAddress]
    shared_recipients: list[WalletAddress]
    shared_contracts: list[WalletAddress]
    coordinated_outgoing_transfers: int = Field(ge=0)


class RelationshipGraphResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    directed: bool
    nodes: list[RelationshipGraphNodeResponse]
    edges: list[RelationshipGraphEdgeResponse]
    node_count: int = Field(ge=0)
    edge_count: int = Field(ge=0)


class SybilThresholdsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    minimum_relationship_strength: float = Field(
        ge=0.0,
        le=1.0,
    )
    high_behavior_similarity: float = Field(
        ge=0.0,
        le=1.0,
    )
    timing_window_seconds: int = Field(ge=0)


class SybilAnalyzeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analyzed_wallet_count: int = Field(ge=2)
    cluster_count: int = Field(ge=0)
    clusters: list[SybilClusterResponse]
    wallet_results: list[SybilWalletResultResponse]
    relationship_graph: RelationshipGraphResponse
    thresholds: SybilThresholdsResponse
