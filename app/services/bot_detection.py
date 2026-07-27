from collections import Counter
from datetime import datetime, timezone
from typing import Any

from app.services.advanced_features import (
    calculate_advanced_features,
)


BURST_WINDOW_SECONDS = 60
BURST_TRANSFER_THRESHOLD = 5
REPEATED_CONTRACT_THRESHOLD = 4
REPEATED_PATTERN_THRESHOLD = 3
SHORT_LIFESPAN_DAYS = 1.0
MIN_ACTIVITY_FOR_BEHAVIOR_RULES = 5
LOW_DIVERSITY_THRESHOLD = 0.25
LOW_ENTROPY_THRESHOLD = 0.25


def _normalize_address(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None

    return value.lower()


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None

    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed


def _transfer_timestamp(
    transfer: dict[str, Any],
) -> datetime | None:
    metadata = transfer.get("metadata")

    if isinstance(metadata, dict):
        timestamp = metadata.get("blockTimestamp")

        if timestamp:
            return _parse_timestamp(timestamp)

    return _parse_timestamp(
        transfer.get("blockTimestamp")
        or transfer.get("timestamp")
    )


def _counterparty(
    transfer: dict[str, Any],
    wallet_address: str,
) -> str | None:
    sender = _normalize_address(transfer.get("from"))
    receiver = _normalize_address(transfer.get("to"))

    if sender == wallet_address:
        return receiver

    if receiver == wallet_address:
        return sender

    return receiver or sender


def _maximum_burst(
    transfers: list[dict[str, Any]],
) -> int:
    timestamps = sorted(
        timestamp
        for transfer in transfers
        if (timestamp := _transfer_timestamp(transfer))
    )

    maximum = 0
    left = 0

    for right, timestamp in enumerate(timestamps):
        while (
            timestamp - timestamps[left]
        ).total_seconds() > BURST_WINDOW_SECONDS:
            left += 1

        maximum = max(maximum, right - left + 1)

    return maximum


def _most_repeated_contract_count(
    transfers: list[dict[str, Any]],
    wallet_address: str,
    contract_addresses: set[str],
) -> int:
    counts: Counter[str] = Counter()

    for transfer in transfers:
        counterparty = _counterparty(
            transfer,
            wallet_address,
        )

        if counterparty in contract_addresses:
            counts[counterparty] += 1

    return max(counts.values(), default=0)


def _most_repeated_pattern_count(
    transfers: list[dict[str, Any]],
) -> int:
    patterns: Counter[tuple[Any, ...]] = Counter()

    for transfer in transfers:
        sender = _normalize_address(transfer.get("from"))
        receiver = _normalize_address(transfer.get("to"))

        if not sender and not receiver:
            continue

        pattern = (
            sender,
            receiver,
            transfer.get("category"),
            transfer.get("asset"),
        )
        patterns[pattern] += 1

    return max(patterns.values(), default=0)


def _rule(
    rule_id: str,
    triggered: bool,
    severity: str,
    evidence: str,
    metrics: dict[str, Any],
) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "triggered": triggered,
        "severity": severity,
        "evidence": evidence,
        "metrics": metrics,
    }


def evaluate_bot_heuristics(
    enriched_data: dict[str, Any],
    advanced_features: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Evaluate Week 5 bot-detection rules and return explainable results.
    """
    features = (
        advanced_features
        if advanced_features is not None
        else calculate_advanced_features(enriched_data)
    )

    wallet_address = (
        _normalize_address(enriched_data.get("address"))
        or ""
    )
    transfers = enriched_data.get("transfers") or []

    contract_addresses = {
        normalized
        for address in enriched_data.get(
            "contract_addresses",
            [],
        )
        if (normalized := _normalize_address(address))
    }

    total_transfers = features.get("total_transfers", 0)
    diversity = features.get("transaction_diversity", 0.0)
    entropy = features.get("transaction_entropy", 0.0)
    lifespan = features.get("wallet_lifespan_days")

    maximum_burst = _maximum_burst(transfers)

    repeated_contract_count = (
        _most_repeated_contract_count(
            transfers,
            wallet_address,
            contract_addresses,
        )
    )

    repeated_pattern_count = (
        _most_repeated_pattern_count(transfers)
    )

    enough_activity = (
        total_transfers >= MIN_ACTIVITY_FOR_BEHAVIOR_RULES
    )

    burst_triggered = (
        maximum_burst >= BURST_TRANSFER_THRESHOLD
    )

    contract_loop_triggered = (
        repeated_contract_count
        >= REPEATED_CONTRACT_THRESHOLD
    )

    transaction_loop_triggered = (
        repeated_pattern_count
        >= REPEATED_PATTERN_THRESHOLD
    )

    short_lifespan_triggered = (
        enough_activity
        and lifespan is not None
        and lifespan <= SHORT_LIFESPAN_DAYS
    )

    low_diversity_triggered = (
        enough_activity
        and diversity <= LOW_DIVERSITY_THRESHOLD
    )

    repetitive_behavior_triggered = (
        enough_activity
        and entropy <= LOW_ENTROPY_THRESHOLD
    )

    rules = [
        _rule(
            rule_id="high_burst_activity",
            triggered=burst_triggered,
            severity="high",
            evidence=(
                f"Maximum of {maximum_burst} transfers occurred "
                f"within {BURST_WINDOW_SECONDS} seconds."
            ),
            metrics={
                "maximum_burst": maximum_burst,
                "window_seconds": BURST_WINDOW_SECONDS,
                "threshold": BURST_TRANSFER_THRESHOLD,
            },
        ),
        _rule(
            rule_id="repeated_contract_loop",
            triggered=contract_loop_triggered,
            severity="high",
            evidence=(
                f"The most-used contract received "
                f"{repeated_contract_count} interactions."
            ),
            metrics={
                "maximum_contract_interactions": (
                    repeated_contract_count
                ),
                "threshold": REPEATED_CONTRACT_THRESHOLD,
            },
        ),
        _rule(
            rule_id="repeated_transaction_loop",
            triggered=transaction_loop_triggered,
            severity="high",
            evidence=(
                f"The most common transaction pattern repeated "
                f"{repeated_pattern_count} times."
            ),
            metrics={
                "maximum_pattern_repetitions": (
                    repeated_pattern_count
                ),
                "threshold": REPEATED_PATTERN_THRESHOLD,
            },
        ),
        _rule(
            rule_id="short_wallet_lifespan",
            triggered=short_lifespan_triggered,
            severity="medium",
            evidence=(
                f"Wallet lifespan is {lifespan} days across "
                f"{total_transfers} sampled transfers."
            ),
            metrics={
                "wallet_lifespan_days": lifespan,
                "threshold_days": SHORT_LIFESPAN_DAYS,
                "minimum_transfers": (
                    MIN_ACTIVITY_FOR_BEHAVIOR_RULES
                ),
            },
        ),
        _rule(
            rule_id="low_transaction_diversity",
            triggered=low_diversity_triggered,
            severity="medium",
            evidence=(
                f"Transaction diversity is {diversity:.4f} "
                f"across {total_transfers} sampled transfers."
            ),
            metrics={
                "transaction_diversity": diversity,
                "threshold": LOW_DIVERSITY_THRESHOLD,
                "minimum_transfers": (
                    MIN_ACTIVITY_FOR_BEHAVIOR_RULES
                ),
            },
        ),
        _rule(
            rule_id="highly_repetitive_behavior",
            triggered=repetitive_behavior_triggered,
            severity="medium",
            evidence=(
                f"Transaction entropy is {entropy:.4f} "
                f"across {total_transfers} sampled transfers."
            ),
            metrics={
                "transaction_entropy": entropy,
                "threshold": LOW_ENTROPY_THRESHOLD,
                "minimum_transfers": (
                    MIN_ACTIVITY_FOR_BEHAVIOR_RULES
                ),
            },
        ),
    ]

    triggered_rule_ids = [
        rule["rule_id"]
        for rule in rules
        if rule["triggered"]
    ]

    return {
        "rules": rules,
        "triggered_rule_ids": triggered_rule_ids,
        "triggered_rule_count": len(triggered_rule_ids),
    }
