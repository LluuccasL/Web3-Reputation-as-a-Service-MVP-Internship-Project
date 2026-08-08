from typing import Any

from app.services import blockchain
from app.services.trust_cache import TTLCache


def _failure_message(error: Exception) -> str:
    message = str(error).strip()
    return message or error.__class__.__name__


def enrich_wallet(
    address: str,
    transfer_limit: int = 25,
    detail_limit: int = 10,
) -> dict[str, Any]:
    """
    Collect enriched blockchain data without allowing one failed lookup
    to break the entire wallet analysis.
    """
    source_status = {
        "balance": "available",
        "transfers": "available",
        "nft_activity": "available",
        "activity_range": "available",
        "transaction_details": "available",
        "contract_lookup": "available",
    }
    errors: dict[str, str] = {}

    balance: dict[str, Any] | None = None
    transfers: list[dict[str, Any]] = []
    nft_transfers: list[dict[str, Any]] = []
    activity_range = {
        "first_activity_at": None,
        "last_activity_at": None,
    }

    try:
        balance = blockchain.get_wallet_balance(address)
    except (RuntimeError, ValueError) as error:
        source_status["balance"] = "unavailable"
        errors["balance"] = _failure_message(error)

    try:
        transfers = blockchain.get_asset_transfers_for_wallet(
            address,
            max_count=transfer_limit,
        )
    except (RuntimeError, ValueError) as error:
        source_status["transfers"] = "unavailable"
        errors["transfers"] = _failure_message(error)

    try:
        nft_transfers = blockchain.get_nft_transfers_for_wallet(
            address,
            max_count=transfer_limit,
        )
    except (RuntimeError, ValueError) as error:
        source_status["nft_activity"] = "unavailable"
        errors["nft_activity"] = _failure_message(error)

    try:
        activity_range = blockchain.get_wallet_activity_range(address)
    except (RuntimeError, ValueError) as error:
        source_status["activity_range"] = "unavailable"
        errors["activity_range"] = _failure_message(error)

    transaction_hashes: list[str] = []
    seen_hashes: set[str] = set()

    for transfer in transfers:
        tx_hash = transfer.get("hash")

        if (
            isinstance(tx_hash, str)
            and tx_hash
            and tx_hash not in seen_hashes
        ):
            seen_hashes.add(tx_hash)
            transaction_hashes.append(tx_hash)

        if len(transaction_hashes) >= detail_limit:
            break

    transaction_details: list[dict[str, Any]] = []
    transaction_failures = 0

    for tx_hash in transaction_hashes:
        try:
            transaction = blockchain.get_transaction_by_hash(tx_hash)
            transaction_details.append(transaction)
        except (RuntimeError, ValueError):
            transaction_failures += 1

    if transaction_failures:
        if transaction_details:
            source_status["transaction_details"] = "partial"
        else:
            source_status["transaction_details"] = "unavailable"

        errors["transaction_details"] = (
            f"{transaction_failures} transaction lookup(s) failed"
        )

    contract_candidates: set[str] = set()

    for transfer in transfers:
        destination = transfer.get("to")

        if isinstance(destination, str) and destination:
            contract_candidates.add(destination.lower())

    for transaction in transaction_details:
        destination = transaction.get("to")

        if isinstance(destination, str) and destination:
            contract_candidates.add(destination.lower())

    contract_addresses: list[str] = []
    contract_failures = 0

    for candidate in sorted(contract_candidates):
        try:
            if blockchain.is_contract_address(candidate):
                contract_addresses.append(candidate)
        except (RuntimeError, ValueError):
            contract_failures += 1

    if contract_failures:
        if contract_addresses:
            source_status["contract_lookup"] = "partial"
        else:
            source_status["contract_lookup"] = "unavailable"

        errors["contract_lookup"] = (
            f"{contract_failures} contract lookup(s) failed"
        )

    return {
        "address": address,
        "balance": balance,
        "transfers": transfers,
        "nft_transfers": nft_transfers,
        "transaction_details": transaction_details,
        "contract_addresses": contract_addresses,
        "activity_range": activity_range,
        "source_status": source_status,
        "errors": errors,
    }


import os as _os

from app.demo_wallets import (
    get_demo_enriched_data as _get_demo_enriched_data,
)


_live_enrich_wallet = enrich_wallet

ENRICHMENT_CACHE_TTL_SECONDS = max(
    1,
    int(
        _os.getenv(
            "ENRICHMENT_CACHE_TTL_SECONDS",
            "300",
        )
    ),
)
ENRICHMENT_CACHE_MAX_SIZE = max(
    1,
    int(
        _os.getenv(
            "ENRICHMENT_CACHE_MAX_SIZE",
            "256",
        )
    ),
)

enrichment_cache: TTLCache[dict[str, Any]] = TTLCache(
    ttl_seconds=ENRICHMENT_CACHE_TTL_SECONDS,
    max_size=ENRICHMENT_CACHE_MAX_SIZE,
)


def clear_enrichment_cache(
    address: str | None = None,
) -> None:
    cache_key = (
        address.strip().lower()
        if isinstance(address, str)
        else None
    )
    enrichment_cache.invalidate(cache_key)


def _demo_mode_enabled() -> bool:
    return _os.getenv(
        "DEMO_MODE",
        "false",
    ).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def enrich_wallet(address: str) -> dict:
    """
    Use deterministic fixtures for recognized demo wallets.

    Live wallets continue through the original enrichment service.
    """
    if _demo_mode_enabled():
        demo_data = _get_demo_enriched_data(address)

        if demo_data is not None:
            return demo_data

    cache_key = address.strip().lower()
    result, _cache_hit = enrichment_cache.get_or_compute(
        cache_key,
        lambda: _live_enrich_wallet(address),
    )
    return result
