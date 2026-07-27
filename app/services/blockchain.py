import os
from decimal import Decimal
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

ALCHEMY_API_KEY = os.getenv("ALCHEMY_API_KEY")
ALCHEMY_NETWORK = os.getenv("ALCHEMY_NETWORK", "eth-mainnet")


def get_alchemy_url() -> str:
    if not ALCHEMY_API_KEY:
        raise RuntimeError("Missing ALCHEMY_API_KEY in .env")

    return f"https://{ALCHEMY_NETWORK}.g.alchemy.com/v2/{ALCHEMY_API_KEY}"


def call_alchemy(method: str, params: list[Any]) -> dict[str, Any]:
    url = get_alchemy_url()

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params,
    }

    try:
        response = requests.post(url, json=payload, timeout=15)

        if response.status_code == 429:
            raise RuntimeError(
                "Alchemy rate limit reached. Wait a minute and try again, or use a less active wallet address."
            )

        response.raise_for_status()

    except requests.exceptions.Timeout:
        raise RuntimeError("Alchemy request timed out")

    except requests.exceptions.RequestException:
        raise RuntimeError("Alchemy request failed")

    data = response.json()

    if "error" in data:
        raise RuntimeError(f"Alchemy error: {data['error']}")

    if "result" not in data:
        raise RuntimeError("Alchemy response missing result")

    return data


def get_latest_block_number() -> int:
    data = call_alchemy("eth_blockNumber", [])
    return int(data["result"], 16)


def wei_to_eth_string(wei_value: int) -> str:
    eth_value = Decimal(wei_value) / Decimal(10**18)
    return format(eth_value, "f")


def get_wallet_balance(address: str) -> dict[str, str]:
    data = call_alchemy("eth_getBalance", [address, "latest"])

    balance_wei = int(data["result"], 16)

    return {
        "address": address,
        "balance_wei": str(balance_wei),
        "balance_eth": wei_to_eth_string(balance_wei),
        "network": ALCHEMY_NETWORK,
    }


def get_asset_transfers_for_wallet(address: str, max_count: int = 10) -> list[dict[str, Any]]:
    max_count_hex = hex(max_count)

    base_params = {
        "fromBlock": "0x0",
        "toBlock": "latest",
        "category": ["external", "erc20", "erc721", "erc1155"],
        "withMetadata": True,
        "excludeZeroValue": False,
        "maxCount": max_count_hex,
        "order": "desc",
    }

    outgoing_params = dict(base_params)
    outgoing_params["fromAddress"] = address

    incoming_params = dict(base_params)
    incoming_params["toAddress"] = address

    outgoing_data = call_alchemy("alchemy_getAssetTransfers", [outgoing_params])
    incoming_data = call_alchemy("alchemy_getAssetTransfers", [incoming_params])

    outgoing_transfers = outgoing_data["result"].get("transfers", [])
    incoming_transfers = incoming_data["result"].get("transfers", [])

    for transfer in outgoing_transfers:
        transfer["direction"] = "outgoing"

    for transfer in incoming_transfers:
        transfer["direction"] = "incoming"

    combined = outgoing_transfers + incoming_transfers

    combined.sort(
        key=lambda item: item.get("metadata", {}).get("blockTimestamp", ""),
        reverse=True,
    )

    return combined[:max_count]


# ---------------------------------------------------------------------------
# Week 5: Blockchain data enrichment
# ---------------------------------------------------------------------------

def get_transaction_by_hash(tx_hash: str) -> dict[str, Any]:
    """
    Retrieve detailed information for one blockchain transaction.
    """
    data = call_alchemy("eth_getTransactionByHash", [tx_hash])
    transaction = data["result"]

    if transaction is None:
        raise RuntimeError("Alchemy transaction not found")

    return transaction


def get_contract_code(address: str) -> str:
    """
    Retrieve the deployed bytecode for an address.
    """
    data = call_alchemy("eth_getCode", [address, "latest"])
    code = data["result"]

    if not isinstance(code, str):
        raise RuntimeError("Alchemy response missing contract code")

    return code


def is_contract_address(address: str) -> bool:
    """
    Return True when an address contains deployed contract code.
    """
    return get_contract_code(address) not in {"", "0x", "0x0"}


def _get_transfer_page(
    address: str,
    address_field: str,
    categories: list[str],
    max_count: int,
    order: str,
) -> list[dict[str, Any]]:
    """
    Retrieve one incoming or outgoing transfer page.
    """
    params = {
        "fromBlock": "0x0",
        "toBlock": "latest",
        "category": categories,
        "withMetadata": True,
        "excludeZeroValue": False,
        "maxCount": hex(max_count),
        "order": order,
        address_field: address,
    }

    data = call_alchemy(
        "alchemy_getAssetTransfers",
        [params],
    )

    transfers = data["result"].get("transfers", [])

    direction = (
        "outgoing"
        if address_field == "fromAddress"
        else "incoming"
    )

    for transfer in transfers:
        transfer["direction"] = direction

    return transfers


def get_nft_transfers_for_wallet(
    address: str,
    max_count: int = 50,
) -> list[dict[str, Any]]:
    """
    Retrieve recent ERC-721 and ERC-1155 wallet activity.
    """
    if max_count < 1 or max_count > 1000:
        raise ValueError("max_count must be between 1 and 1000")

    categories = ["erc721", "erc1155"]

    outgoing = _get_transfer_page(
        address=address,
        address_field="fromAddress",
        categories=categories,
        max_count=max_count,
        order="desc",
    )

    incoming = _get_transfer_page(
        address=address,
        address_field="toAddress",
        categories=categories,
        max_count=max_count,
        order="desc",
    )

    combined = outgoing + incoming

    combined.sort(
        key=lambda item: item.get(
            "metadata",
            {},
        ).get(
            "blockTimestamp",
            "",
        ),
        reverse=True,
    )

    return combined[:max_count]


def get_wallet_activity_range(
    address: str,
) -> dict[str, str | None]:
    """
    Find the wallet's earliest and latest recorded transfer timestamps.
    """
    categories = [
        "external",
        "erc20",
        "erc721",
        "erc1155",
    ]

    first_timestamps: list[str] = []
    latest_timestamps: list[str] = []

    for address_field in ("fromAddress", "toAddress"):
        first_transfers = _get_transfer_page(
            address=address,
            address_field=address_field,
            categories=categories,
            max_count=1,
            order="asc",
        )

        latest_transfers = _get_transfer_page(
            address=address,
            address_field=address_field,
            categories=categories,
            max_count=1,
            order="desc",
        )

        if first_transfers:
            timestamp = first_transfers[0].get(
                "metadata",
                {},
            ).get("blockTimestamp")

            if timestamp:
                first_timestamps.append(timestamp)

        if latest_transfers:
            timestamp = latest_transfers[0].get(
                "metadata",
                {},
            ).get("blockTimestamp")

            if timestamp:
                latest_timestamps.append(timestamp)

    return {
        "first_activity_at": (
            min(first_timestamps)
            if first_timestamps
            else None
        ),
        "last_activity_at": (
            max(latest_timestamps)
            if latest_timestamps
            else None
        ),
    }
