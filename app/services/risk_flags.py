from typing import Any

from app.services.advanced_features import (
    calculate_advanced_features,
)
from app.services.bot_detection import (
    evaluate_bot_heuristics,
)


HIGH_CONTRACT_RATIO_THRESHOLD = 0.8
MIN_ACTIVITY_FOR_INFORMATIONAL_FLAGS = 5
SUSPICIOUS_NFT_TRANSFER_THRESHOLD = 10

SEVERITY_POINTS = {
    "high": 3,
    "medium": 2,
    "low": 1,
    "informational": 0,
}

RULE_CATEGORIES = {
    "high_burst_activity": "velocity",
    "repeated_contract_loop": "contract_behavior",
    "repeated_transaction_loop": "transaction_pattern",
    "short_wallet_lifespan": "wallet_age",
    "low_transaction_diversity": "interaction_diversity",
    "highly_repetitive_behavior": "behavior_repetition",
}

NFT_AUTOMATION_RULES = {
    "high_burst_activity",
    "repeated_transaction_loop",
    "highly_repetitive_behavior",
}


def _create_flag(
    flag_id: str,
    severity: str,
    signal_type: str,
    category: str,
    evidence: str,
    metrics: dict[str, Any],
) -> dict[str, Any]:
    return {
        "flag_id": flag_id,
        "severity": severity,
        "signal_type": signal_type,
        "category": category,
        "evidence": evidence,
        "metrics": metrics,
    }


def _risk_level(risk_points: int) -> str:
    if risk_points == 0:
        return "none"

    if risk_points <= 2:
        return "low"

    if risk_points <= 5:
        return "medium"

    return "high"


def generate_risk_flags(
    enriched_data: dict[str, Any],
    advanced_features: dict[str, Any] | None = None,
    heuristic_results: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Convert Week 5 heuristic results into structured risk flags.

    Informational signals describe wallet behavior but do not increase
    the bot-risk level by themselves.
    """
    features = (
        advanced_features
        if advanced_features is not None
        else calculate_advanced_features(enriched_data)
    )

    heuristics = (
        heuristic_results
        if heuristic_results is not None
        else evaluate_bot_heuristics(
            enriched_data,
            features,
        )
    )

    risk_flags: list[dict[str, Any]] = []
    informational_flags: list[dict[str, Any]] = []

    for rule in heuristics.get("rules", []):
        if not rule.get("triggered"):
            continue

        rule_id = rule["rule_id"]

        risk_flags.append(
            _create_flag(
                flag_id=rule_id,
                severity=rule["severity"],
                signal_type="risk",
                category=RULE_CATEGORIES.get(
                    rule_id,
                    "behavior",
                ),
                evidence=rule["evidence"],
                metrics=rule.get("metrics", {}),
            )
        )

    total_transfers = features.get("total_transfers", 0)
    contract_ratio = features.get(
        "contract_interaction_ratio",
        0.0,
    )
    nft_transfer_count = features.get(
        "nft_transfer_count",
        0,
    )

    if (
        total_transfers
        >= MIN_ACTIVITY_FOR_INFORMATIONAL_FLAGS
        and contract_ratio
        >= HIGH_CONTRACT_RATIO_THRESHOLD
    ):
        informational_flags.append(
            _create_flag(
                flag_id="high_contract_interaction_ratio",
                severity="informational",
                signal_type="informational",
                category="contract_behavior",
                evidence=(
                    f"{contract_ratio:.1%} of sampled transfers "
                    "involved known contracts. Contract usage alone "
                    "does not indicate bot activity."
                ),
                metrics={
                    "contract_interaction_ratio": (
                        contract_ratio
                    ),
                    "threshold": (
                        HIGH_CONTRACT_RATIO_THRESHOLD
                    ),
                    "total_transfers": total_transfers,
                },
            )
        )

    triggered_rule_ids = set(
        heuristics.get("triggered_rule_ids", [])
    )

    suspicious_nft_rules = sorted(
        triggered_rule_ids & NFT_AUTOMATION_RULES
    )

    if (
        nft_transfer_count
        >= SUSPICIOUS_NFT_TRANSFER_THRESHOLD
        and suspicious_nft_rules
    ):
        risk_flags.append(
            _create_flag(
                flag_id="suspicious_nft_activity",
                severity="medium",
                signal_type="risk",
                category="nft_behavior",
                evidence=(
                    f"{nft_transfer_count} NFT transfers were found "
                    "together with automated or repetitive behavior."
                ),
                metrics={
                    "nft_transfer_count": nft_transfer_count,
                    "threshold": (
                        SUSPICIOUS_NFT_TRANSFER_THRESHOLD
                    ),
                    "supporting_rules": suspicious_nft_rules,
                },
            )
        )

    risk_points = sum(
        SEVERITY_POINTS.get(flag["severity"], 0)
        for flag in risk_flags
    )

    all_flags = risk_flags + informational_flags

    return {
        "flags": all_flags,
        "risk_flags": risk_flags,
        "informational_flags": informational_flags,
        "risk_flag_ids": [
            flag["flag_id"]
            for flag in risk_flags
        ],
        "informational_flag_ids": [
            flag["flag_id"]
            for flag in informational_flags
        ],
        "risk_flag_count": len(risk_flags),
        "informational_flag_count": len(
            informational_flags
        ),
        "risk_points": risk_points,
        "risk_level": _risk_level(risk_points),
    }
