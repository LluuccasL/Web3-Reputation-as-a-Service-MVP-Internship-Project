from app.services.enhanced_scoring import (
    calculate_enhanced_trust_result,
)


def _base_result(score: int) -> dict:
    return {
        "human_likelihood": "medium",
        "trust_tier": "silver",
        "confidence_score": score / 100,
        "risk_flags": ["legacy_example"],
    }


def _no_risk_flags() -> dict:
    return {
        "risk_flags": [],
        "informational_flags": [],
        "risk_points": 0,
        "risk_level": "none",
    }


def test_positive_behavior_increases_enhanced_score():
    features = {
        "total_transfers": 5,
        "transaction_diversity": 1.0,
        "transaction_entropy": 1.0,
        "wallet_lifespan_days": 400.0,
    }

    enriched_data = {
        "source_status": {
            "balance": "available",
            "transfers": "available",
            "activity_range": "available",
        }
    }

    result = calculate_enhanced_trust_result(
        _base_result(70),
        enriched_data,
        features,
        _no_risk_flags(),
    )

    assert result["base_score"] == 70
    assert result["positive_points"] == 16
    assert result["enhanced_score"] == 86
    assert result["human_likelihood"] == "high"
    assert result["trust_tier"] == "gold"
    assert result["confidence_score"] == 0.86
    assert result["data_coverage"] == 1.0
    assert result["legacy_risk_flags"] == [
        "legacy_example"
    ]


def test_high_risk_level_limits_enhanced_score():
    features = {
        "total_transfers": 6,
        "transaction_diversity": 0.1,
        "transaction_entropy": 0.0,
        "wallet_lifespan_days": 0.5,
    }

    risk_results = {
        "risk_flags": [
            {
                "flag_id": "high_burst_activity",
                "severity": "high",
            }
        ],
        "informational_flags": [],
        "risk_points": 9,
        "risk_level": "high",
    }

    result = calculate_enhanced_trust_result(
        _base_result(95),
        {"source_status": {}},
        features,
        risk_results,
    )

    assert result["risk_penalty"] == 27
    assert result["enhanced_score"] == 49
    assert result["score_adjustment"] == -46
    assert result["human_likelihood"] == "low"
    assert result["trust_tier"] == "bronze"

    factor_ids = {
        factor["factor_id"]
        for factor in result["score_factors"]
    }

    assert "behavioral_risk_penalty" in factor_ids
    assert "risk_level_score_ceiling" in factor_ids


def test_partial_sources_reduce_data_coverage():
    features = {
        "total_transfers": 0,
        "transaction_diversity": 0.0,
        "transaction_entropy": 0.0,
        "wallet_lifespan_days": None,
    }

    enriched_data = {
        "source_status": {
            "balance": "available",
            "transfers": "partial",
            "nft_activity": "unavailable",
        }
    }

    result = calculate_enhanced_trust_result(
        _base_result(60),
        enriched_data,
        features,
        _no_risk_flags(),
    )

    assert result["enhanced_score"] == 60
    assert result["data_coverage"] == 0.5
    assert result["positive_points"] == 0
    assert result["risk_penalty"] == 0
