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
