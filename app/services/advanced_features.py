from collections import Counter
from datetime import datetime, timezone
from math import log2
from typing import Any


def _normalize_address(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None

    return value.lower()


def _get_counterparty(
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


def _normalized_entropy(values: list[str]) -> float:
    """
    Return Shannon entropy normalized to the range 0.0–1.0.
    """
    if not values:
        return 0.0

    counts = Counter(values)

    if len(counts) <= 1:
        return 0.0

    total = len(values)
    entropy = 0.0

    for count in counts.values():
        probability = count / total
        entropy -= probability * log2(probability)

    maximum_entropy = log2(len(counts))

    return round(entropy / maximum_entropy, 4)


def calculate_advanced_features(
    enriched_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Calculate Week 5 behavioral features from enriched wallet data.
    """
    wallet_address = _normalize_address(
        enriched_data.get("address")
    ) or ""

    transfers = enriched_data.get("transfers") or []
    nft_transfers = enriched_data.get("nft_transfers") or []

    contract_addresses = {
        normalized
        for address in enriched_data.get(
            "contract_addresses",
            [],
        )
        if (normalized := _normalize_address(address))
    }

    counterparties: list[str] = []

    for transfer in transfers:
        counterparty = _get_counterparty(
            transfer,
            wallet_address,
        )

        if counterparty and counterparty != wallet_address:
            counterparties.append(counterparty)

    unique_addresses = set(counterparties)

    contract_counterparties = [
        address
        for address in counterparties
        if address in contract_addresses
    ]

    total_transfers = len(transfers)

    transaction_diversity = (
        len(unique_addresses) / total_transfers
        if total_transfers
        else 0.0
    )

    contract_interaction_ratio = (
        len(contract_counterparties) / total_transfers
        if total_transfers
        else 0.0
    )

    activity_range = enriched_data.get(
        "activity_range",
        {},
    )

    first_activity = _parse_timestamp(
        activity_range.get("first_activity_at")
    )
    last_activity = _parse_timestamp(
        activity_range.get("last_activity_at")
    )

    wallet_lifespan_days: float | None = None

    if first_activity and last_activity:
        lifespan_seconds = max(
            0.0,
            (last_activity - first_activity).total_seconds(),
        )
        wallet_lifespan_days = round(
            lifespan_seconds / 86400,
            2,
        )

    return {
        "total_transfers": total_transfers,
        "unique_interaction_addresses": len(
            unique_addresses
        ),
        "transaction_diversity": round(
            transaction_diversity,
            4,
        ),
        "unique_contracts": len(
            set(contract_counterparties)
        ),
        "contract_interaction_count": len(
            contract_counterparties
        ),
        "contract_interaction_ratio": round(
            contract_interaction_ratio,
            4,
        ),
        "transaction_entropy": _normalized_entropy(
            counterparties
        ),
        "wallet_lifespan_days": wallet_lifespan_days,
        "nft_transfer_count": len(nft_transfers),
        "has_nft_activity": bool(nft_transfers),
    }
