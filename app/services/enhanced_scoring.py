from typing import Any

from app.services.advanced_features import (
    calculate_advanced_features,
)
from app.services.risk_flags import (
    generate_risk_flags,
)


RISK_POINT_MULTIPLIER = 3
MAX_RISK_PENALTY = 45

RISK_LEVEL_SCORE_CEILINGS = {
    "none": 100,
    "low": 89,
    "medium": 79,
    "high": 49,
}

SOURCE_COVERAGE_WEIGHTS = {
    "available": 1.0,
    "partial": 0.5,
    "unavailable": 0.0,
}


def _get_field(
    value: Any,
    field_name: str,
    default: Any = None,
) -> Any:
    if isinstance(value, dict):
        return value.get(field_name, default)

    return getattr(value, field_name, default)


def _enum_value(value: Any) -> Any:
    return getattr(value, "value", value)


def _clamp_score(score: int) -> int:
    return max(0, min(100, score))


def _score_classification(
    score: int,
) -> tuple[str, str]:
    """
    Preserve the existing Week 3–4 trust-tier thresholds.
    """
    if score >= 80:
        return "high", "gold"

    if score >= 50:
        return "medium", "silver"

    return "low", "bronze"


def _calculate_data_coverage(
    source_status: dict[str, str],
) -> float:
    if not source_status:
        return 1.0

    total_weight = sum(
        SOURCE_COVERAGE_WEIGHTS.get(status, 0.0)
        for status in source_status.values()
    )

    return round(
        total_weight / len(source_status),
        2,
    )


def _positive_score_factors(
    features: dict[str, Any],
) -> list[dict[str, Any]]:
    factors: list[dict[str, Any]] = []

    total_transfers = features.get("total_transfers", 0)
    lifespan = features.get("wallet_lifespan_days")
    diversity = features.get("transaction_diversity", 0.0)
    entropy = features.get("transaction_entropy", 0.0)

    if lifespan is not None and lifespan >= 365:
        factors.append(
            {
                "factor_id": "established_wallet",
                "direction": "positive",
                "points": 6,
                "evidence": (
                    f"Wallet activity spans {lifespan} days."
                ),
            }
        )
    elif lifespan is not None and lifespan >= 90:
        factors.append(
            {
                "factor_id": "mature_wallet",
                "direction": "positive",
                "points": 3,
                "evidence": (
                    f"Wallet activity spans {lifespan} days."
                ),
            }
        )

    if total_transfers >= 5 and diversity >= 0.75:
        factors.append(
            {
                "factor_id": "high_transaction_diversity",
                "direction": "positive",
                "points": 5,
                "evidence": (
                    f"Transaction diversity is {diversity:.4f}."
                ),
            }
        )
    elif total_transfers >= 5 and diversity >= 0.5:
        factors.append(
            {
                "factor_id": "moderate_transaction_diversity",
                "direction": "positive",
                "points": 3,
                "evidence": (
                    f"Transaction diversity is {diversity:.4f}."
                ),
            }
        )

    if total_transfers >= 5 and entropy >= 0.75:
        factors.append(
            {
                "factor_id": "high_transaction_entropy",
                "direction": "positive",
                "points": 5,
                "evidence": (
                    f"Transaction entropy is {entropy:.4f}."
                ),
            }
        )
    elif total_transfers >= 5 and entropy >= 0.5:
        factors.append(
            {
                "factor_id": "moderate_transaction_entropy",
                "direction": "positive",
                "points": 3,
                "evidence": (
                    f"Transaction entropy is {entropy:.4f}."
                ),
            }
        )

    return factors


def calculate_enhanced_trust_result(
    base_trust_result: Any,
    enriched_data: dict[str, Any],
    advanced_features: dict[str, Any] | None = None,
    risk_flag_results: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Enhance the existing trust result without changing its implementation.
    """
    base_confidence = float(
        _get_field(
            base_trust_result,
            "confidence_score",
            0.0,
        )
    )

    if not 0.0 <= base_confidence <= 1.0:
        raise ValueError(
            "base confidence_score must be between 0.0 and 1.0"
        )

    base_score = round(base_confidence * 100)

    features = (
        advanced_features
        if advanced_features is not None
        else calculate_advanced_features(enriched_data)
    )

    flag_results = (
        risk_flag_results
        if risk_flag_results is not None
        else generate_risk_flags(
            enriched_data,
            features,
        )
    )

    risk_points = max(
        0,
        int(flag_results.get("risk_points", 0)),
    )

    risk_penalty = min(
        risk_points * RISK_POINT_MULTIPLIER,
        MAX_RISK_PENALTY,
    )

    score_factors = _positive_score_factors(features)

    positive_points = sum(
        factor["points"]
        for factor in score_factors
    )

    if risk_penalty:
        score_factors.append(
            {
                "factor_id": "behavioral_risk_penalty",
                "direction": "negative",
                "points": risk_penalty,
                "evidence": (
                    f"{risk_points} risk points produced a "
                    f"{risk_penalty}-point score penalty."
                ),
            }
        )

    calculated_score = _clamp_score(
        base_score + positive_points - risk_penalty
    )

    risk_level = flag_results.get(
        "risk_level",
        "none",
    )

    score_ceiling = RISK_LEVEL_SCORE_CEILINGS.get(
        risk_level,
        100,
    )

    enhanced_score = min(
        calculated_score,
        score_ceiling,
    )

    if enhanced_score < calculated_score:
        score_factors.append(
            {
                "factor_id": "risk_level_score_ceiling",
                "direction": "negative",
                "points": calculated_score - enhanced_score,
                "evidence": (
                    f"The {risk_level} risk level limits the "
                    f"enhanced score to {score_ceiling}."
                ),
            }
        )

    human_likelihood, trust_tier = (
        _score_classification(enhanced_score)
    )

    source_status = enriched_data.get(
        "source_status",
        {},
    )

    return {
        "base_score": base_score,
        "enhanced_score": enhanced_score,
        "score_adjustment": enhanced_score - base_score,
        "human_likelihood": human_likelihood,
        "trust_tier": trust_tier,
        "confidence_score": round(
            enhanced_score / 100,
            2,
        ),
        "data_coverage": _calculate_data_coverage(
            source_status
        ),
        "risk_level": risk_level,
        "risk_points": risk_points,
        "risk_penalty": risk_penalty,
        "positive_points": positive_points,
        "advanced_features": features,
        "risk_flags": flag_results.get(
            "risk_flags",
            [],
        ),
        "informational_flags": flag_results.get(
            "informational_flags",
            [],
        ),
        "legacy_risk_flags": list(
            _get_field(
                base_trust_result,
                "risk_flags",
                [],
            )
        ),
        "score_factors": score_factors,
        "base_human_likelihood": _enum_value(
            _get_field(
                base_trust_result,
                "human_likelihood",
            )
        ),
        "base_trust_tier": _enum_value(
            _get_field(
                base_trust_result,
                "trust_tier",
            )
        ),
    }
