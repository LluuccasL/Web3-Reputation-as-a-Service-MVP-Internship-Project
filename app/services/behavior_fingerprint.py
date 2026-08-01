import hashlib
import json
from datetime import datetime, timezone
from statistics import median
from typing import Any

from app.services.advanced_features import calculate_advanced_features
from app.services.bot_detection import evaluate_bot_heuristics
from app.services.wallet_relationships import extract_wallet_relationships


FINGERPRINT_VERSION = "1.0"
HIGH_SIMILARITY_THRESHOLD = 0.85

COMPONENT_WEIGHTS = {
    "activity": 0.20,
    "transfer_behavior": 0.25,
    "timing": 0.20,
    "diversity": 0.15,
    "contracts": 0.10,
    "automation": 0.10,
}


def _normalize_address(value: Any) -> str | None:
    if not isinstance(value, str):
        return None

    normalized = value.strip().lower()
    return normalized or None


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def _transfer_timestamp(transfer: dict[str, Any]) -> datetime | None:
    metadata = transfer.get("metadata")

    if isinstance(metadata, dict):
        timestamp = _parse_timestamp(metadata.get("blockTimestamp"))

        if timestamp is not None:
            return timestamp

    return _parse_timestamp(
        transfer.get("blockTimestamp") or transfer.get("timestamp")
    )


def _lifespan_bucket(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "unknown"

    for maximum, label in (
        (1, "one_day_or_less"),
        (7, "one_week_or_less"),
        (30, "one_month_or_less"),
        (365, "one_year_or_less"),
    ):
        if value <= maximum:
            return label

    return "over_one_year"


def _interval_bucket(value: float | None) -> str:
    if value is None:
        return "unknown"

    for maximum, label in (
        (60, "one_minute_or_less"),
        (3600, "one_hour_or_less"),
        (86400, "one_day_or_less"),
        (604800, "one_week_or_less"),
    ):
        if value <= maximum:
            return label

    return "over_one_week"


def _timing_components(
    transfers: list[dict[str, Any]],
) -> dict[str, Any]:
    timestamps = sorted(
        timestamp
        for transfer in transfers
        if (timestamp := _transfer_timestamp(transfer))
    )
    active_dates = {timestamp.date() for timestamp in timestamps}
    intervals = [
        (right - left).total_seconds()
        for left, right in zip(timestamps, timestamps[1:])
    ]
    median_interval = float(median(intervals)) if intervals else None

    return {
        "active_day_count": len(active_dates),
        "active_hours_utc": sorted(
            {timestamp.hour for timestamp in timestamps}
        ),
        "active_weekdays_utc": sorted(
            {timestamp.weekday() for timestamp in timestamps}
        ),
        "median_interval_bucket": _interval_bucket(median_interval),
    }


def _fingerprint_id(components: dict[str, Any]) -> str:
    canonical = json.dumps(
        components,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def generate_behavior_fingerprint(
    enriched_data: dict[str, Any],
    relationship_profile: dict[str, Any] | None = None,
    advanced_features: dict[str, Any] | None = None,
    bot_analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Create a deterministic, address-independent behavior fingerprint.
    """
    wallet_address = _normalize_address(enriched_data.get("address"))

    if wallet_address is None:
        raise ValueError(
            "enriched_data must contain a wallet address"
        )

    relationships = relationship_profile or extract_wallet_relationships(
        enriched_data
    )
    features = advanced_features or calculate_advanced_features(
        enriched_data
    )
    bot_result = bot_analysis or evaluate_bot_heuristics(
        enriched_data,
        features,
    )
    transfers = [
        transfer
        for transfer in enriched_data.get("transfers") or []
        if isinstance(transfer, dict)
    ]

    total = int(features.get("total_transfers", 0) or 0)
    incoming = int(
        relationships.get("incoming_transfer_count", 0) or 0
    )
    outgoing = int(
        relationships.get("outgoing_transfer_count", 0) or 0
    )
    timing = _timing_components(transfers)
    active_days = timing["active_day_count"]

    components = {
        "version": FINGERPRINT_VERSION,
        "activity": {
            "total_transfers": total,
            "active_day_count": active_days,
            "transfers_per_active_day": (
                round(total / active_days, 4) if active_days else 0.0
            ),
            "wallet_lifespan_bucket": _lifespan_bucket(
                features.get("wallet_lifespan_days")
            ),
        },
        "transfer_behavior": {
            "incoming_ratio": (
                round(incoming / total, 4) if total else 0.0
            ),
            "outgoing_ratio": (
                round(outgoing / total, 4) if total else 0.0
            ),
            "unique_funder_count": len(
                relationships.get("funders") or []
            ),
            "unique_recipient_count": len(
                relationships.get("recipients") or []
            ),
            "recipient_reuse_ratio": (
                round(
                    len(relationships.get("recipients") or [])
                    / outgoing,
                    4,
                )
                if outgoing
                else 0.0
            ),
        },
        "timing": timing,
        "diversity": {
            "transaction_diversity": round(
                float(features.get("transaction_diversity", 0.0) or 0.0),
                4,
            ),
            "transaction_entropy": round(
                float(features.get("transaction_entropy", 0.0) or 0.0),
                4,
            ),
            "contract_interaction_ratio": round(
                float(
                    features.get("contract_interaction_ratio", 0.0)
                    or 0.0
                ),
                4,
            ),
        },
        "contracts": {
            "addresses": sorted(
                {
                    address
                    for value in relationships.get("contracts") or []
                    if (address := _normalize_address(value))
                }
            ),
            "unique_contract_count": int(
                features.get("unique_contracts", 0) or 0
            ),
        },
        "automation": {
            "triggered_bot_rules": sorted(
                {
                    rule_id
                    for rule_id in (
                        bot_result.get("triggered_rule_ids") or []
                    )
                    if isinstance(rule_id, str)
                }
            ),
            "nft_transfer_count": int(
                features.get("nft_transfer_count", 0) or 0
            ),
            "has_nft_activity": bool(
                features.get("has_nft_activity", False)
            ),
        },
    }

    return {
        "address": wallet_address,
        "fingerprint_version": FINGERPRINT_VERSION,
        "fingerprint_id": _fingerprint_id(components),
        "components": components,
    }


def _numeric_similarity(left: Any, right: Any) -> float:
    left_number = float(left or 0.0)
    right_number = float(right or 0.0)
    scale = max(abs(left_number), abs(right_number), 1.0)
    return max(
        0.0,
        1.0 - abs(left_number - right_number) / scale,
    )


def _set_similarity(left: Any, right: Any) -> float:
    left_set = set(left or [])
    right_set = set(right or [])
    union = left_set | right_set
    return len(left_set & right_set) / len(union) if union else 1.0


def _component_score(
    left: dict[str, Any],
    right: dict[str, Any],
    numeric_fields: tuple[str, ...] = (),
    set_fields: tuple[str, ...] = (),
    exact_fields: tuple[str, ...] = (),
) -> float:
    scores = [
        _numeric_similarity(left.get(field), right.get(field))
        for field in numeric_fields
    ]
    scores.extend(
        _set_similarity(left.get(field), right.get(field))
        for field in set_fields
    )
    scores.extend(
        float(left.get(field) == right.get(field))
        for field in exact_fields
    )
    return sum(scores) / len(scores) if scores else 0.0


def calculate_behavior_similarity(
    left: dict[str, Any],
    right: dict[str, Any],
) -> dict[str, Any]:
    """
    Compare two generated fingerprints on a normalized 0-to-1 scale.
    """
    left_components = left.get("components")
    right_components = right.get("components")

    if not isinstance(left_components, dict) or not isinstance(
        right_components,
        dict,
    ):
        raise ValueError(
            "both fingerprints must contain components"
        )

    comparison_rules = {
        "activity": {
            "numeric_fields": (
                "total_transfers",
                "active_day_count",
                "transfers_per_active_day",
            ),
            "exact_fields": ("wallet_lifespan_bucket",),
        },
        "transfer_behavior": {
            "numeric_fields": (
                "incoming_ratio",
                "outgoing_ratio",
                "unique_funder_count",
                "unique_recipient_count",
                "recipient_reuse_ratio",
            ),
        },
        "timing": {
            "numeric_fields": ("active_day_count",),
            "set_fields": (
                "active_hours_utc",
                "active_weekdays_utc",
            ),
            "exact_fields": ("median_interval_bucket",),
        },
        "diversity": {
            "numeric_fields": (
                "transaction_diversity",
                "transaction_entropy",
                "contract_interaction_ratio",
            ),
        },
        "contracts": {
            "numeric_fields": ("unique_contract_count",),
            "set_fields": ("addresses",),
        },
        "automation": {
            "numeric_fields": ("nft_transfer_count",),
            "set_fields": ("triggered_bot_rules",),
            "exact_fields": ("has_nft_activity",),
        },
    }

    component_scores = {
        name: round(
            _component_score(
                left_components.get(name) or {},
                right_components.get(name) or {},
                **rules,
            ),
            4,
        )
        for name, rules in comparison_rules.items()
    }
    similarity_score = round(
        sum(
            component_scores[name] * weight
            for name, weight in COMPONENT_WEIGHTS.items()
        ),
        4,
    )

    return {
        "wallet_a": left.get("address"),
        "wallet_b": right.get("address"),
        "similarity_score": similarity_score,
        "component_scores": component_scores,
        "matching_fingerprint": (
            left.get("fingerprint_id")
            == right.get("fingerprint_id")
        ),
        "high_behavior_similarity": (
            similarity_score >= HIGH_SIMILARITY_THRESHOLD
        ),
        "high_similarity_threshold": HIGH_SIMILARITY_THRESHOLD,
    }
