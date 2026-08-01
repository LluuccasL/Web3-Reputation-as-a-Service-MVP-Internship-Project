from datetime import datetime, timezone
from typing import Any


DEFAULT_TIMING_WINDOW_SECONDS = 300


def _normalize_address(value: Any) -> str | None:
    if not isinstance(value, str):
        return None

    normalized = value.strip().lower()
    return normalized or None


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
        timestamp = _parse_timestamp(
            metadata.get("blockTimestamp")
        )

        if timestamp is not None:
            return timestamp

    return _parse_timestamp(
        transfer.get("blockTimestamp")
        or transfer.get("timestamp")
    )


def _iso_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace(
        "+00:00",
        "Z",
    )


def extract_wallet_relationships(
    enriched_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Extract normalized relationship evidence from one enriched wallet.
    """
    wallet_address = _normalize_address(
        enriched_data.get("address")
    )

    if wallet_address is None:
        raise ValueError(
            "enriched_data must contain a wallet address"
        )

    funders: set[str] = set()
    recipients: set[str] = set()
    counterparties: set[str] = set()
    incoming_timestamps: list[datetime] = []
    outgoing_timestamps: list[datetime] = []
    incoming_transfer_count = 0
    outgoing_transfer_count = 0

    transfers = enriched_data.get("transfers") or []

    for transfer in transfers:
        if not isinstance(transfer, dict):
            continue

        sender = _normalize_address(transfer.get("from"))
        receiver = _normalize_address(transfer.get("to"))
        timestamp = _transfer_timestamp(transfer)

        if receiver == wallet_address and sender:
            funders.add(sender)
            counterparties.add(sender)
            incoming_transfer_count += 1

            if timestamp is not None:
                incoming_timestamps.append(timestamp)

        if sender == wallet_address and receiver:
            recipients.add(receiver)
            counterparties.add(receiver)
            outgoing_transfer_count += 1

            if timestamp is not None:
                outgoing_timestamps.append(timestamp)

    contracts = {
        normalized
        for address in enriched_data.get(
            "contract_addresses",
            [],
        )
        if (normalized := _normalize_address(address))
    }

    counterparties.update(contracts)

    return {
        "address": wallet_address,
        "funders": sorted(funders),
        "recipients": sorted(recipients),
        "contracts": sorted(contracts),
        "counterparties": sorted(counterparties),
        "incoming_transfer_count": incoming_transfer_count,
        "outgoing_transfer_count": outgoing_transfer_count,
        "incoming_timestamps": [
            _iso_timestamp(timestamp)
            for timestamp in sorted(incoming_timestamps)
        ],
        "outgoing_timestamps": [
            _iso_timestamp(timestamp)
            for timestamp in sorted(outgoing_timestamps)
        ],
    }


def _count_coordinated_timestamps(
    left_values: list[str],
    right_values: list[str],
    timing_window_seconds: int,
) -> int:
    left_timestamps = sorted(
        parsed
        for value in left_values
        if (parsed := _parse_timestamp(value))
    )
    right_timestamps = sorted(
        parsed
        for value in right_values
        if (parsed := _parse_timestamp(value))
    )

    matched_right_indexes: set[int] = set()
    match_count = 0

    for left_timestamp in left_timestamps:
        best_index: int | None = None
        best_difference: float | None = None

        for index, right_timestamp in enumerate(
            right_timestamps
        ):
            if index in matched_right_indexes:
                continue

            difference = abs(
                (
                    left_timestamp - right_timestamp
                ).total_seconds()
            )

            if difference > timing_window_seconds:
                continue

            if (
                best_difference is None
                or difference < best_difference
            ):
                best_index = index
                best_difference = difference

        if best_index is not None:
            matched_right_indexes.add(best_index)
            match_count += 1

    return match_count


def compare_wallet_relationships(
    left: dict[str, Any],
    right: dict[str, Any],
    timing_window_seconds: int = (
        DEFAULT_TIMING_WINDOW_SECONDS
    ),
) -> dict[str, Any]:
    """
    Compare two extracted profiles and return shared evidence.
    """
    if timing_window_seconds < 0:
        raise ValueError(
            "timing_window_seconds must be non-negative"
        )

    shared_funders = sorted(
        set(left.get("funders") or [])
        & set(right.get("funders") or [])
    )
    shared_recipients = sorted(
        set(left.get("recipients") or [])
        & set(right.get("recipients") or [])
    )
    shared_contracts = sorted(
        set(left.get("contracts") or [])
        & set(right.get("contracts") or [])
    )
    shared_counterparties = sorted(
        set(left.get("counterparties") or [])
        & set(right.get("counterparties") or [])
    )

    coordinated_outgoing_transfers = (
        _count_coordinated_timestamps(
            left.get("outgoing_timestamps") or [],
            right.get("outgoing_timestamps") or [],
            timing_window_seconds,
        )
    )

    evidence_types: list[str] = []

    if shared_funders:
        evidence_types.append("shared_funder")

    if shared_recipients:
        evidence_types.append("shared_recipient")

    if shared_contracts:
        evidence_types.append("shared_contract")

    if coordinated_outgoing_transfers:
        evidence_types.append("coordinated_timing")

    return {
        "wallet_a": left.get("address"),
        "wallet_b": right.get("address"),
        "shared_funders": shared_funders,
        "shared_recipients": shared_recipients,
        "shared_contracts": shared_contracts,
        "shared_counterparties": shared_counterparties,
        "coordinated_outgoing_transfers": (
            coordinated_outgoing_transfers
        ),
        "timing_window_seconds": timing_window_seconds,
        "evidence_types": evidence_types,
        "has_relationship": bool(evidence_types),
    }
