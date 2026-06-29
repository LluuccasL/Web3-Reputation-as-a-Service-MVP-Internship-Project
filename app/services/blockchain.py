import os
import re
from typing import Any, Dict

import requests
from dotenv import load_dotenv

load_dotenv()

ETH_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")


class BlockchainServiceError(Exception):
    pass


def is_valid_eth_address(address: str) -> bool:
    if not isinstance(address, str):
        return False
    return bool(ETH_ADDRESS_RE.fullmatch(address.strip()))


def normalize_address(address: str) -> str:
    return address.strip().lower()


def get_alchemy_url() -> str:
    api_key = os.getenv("ALCHEMY_API_KEY")

    if not api_key or api_key == "your_alchemy_api_key_here":
        raise BlockchainServiceError("Missing ALCHEMY_API_KEY in .env")

    return f"https://eth-mainnet.g.alchemy.com/v2/{api_key}"


def get_latest_block_number() -> int:
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_blockNumber",
        "params": []
    }

    try:
        response = requests.post(
            get_alchemy_url(),
            json=payload,
            timeout=10
        )
        response.raise_for_status()
        data: Dict[str, Any] = response.json()

    except requests.RequestException as error:
        raise BlockchainServiceError(f"Alchemy request failed: {error}") from error

    if "error" in data:
        raise BlockchainServiceError(f"Alchemy returned an error: {data['error']}")

    result = data.get("result")

    if not isinstance(result, str) or not result.startswith("0x"):
        raise BlockchainServiceError(f"Unexpected Alchemy response: {data}")

    return int(result, 16)
