import os
import requests
from dotenv import load_dotenv

load_dotenv()


ALCHEMY_API_KEY = os.getenv("ALCHEMY_API_KEY")
ALCHEMY_NETWORK = os.getenv("ALCHEMY_NETWORK", "eth-mainnet")


def get_latest_block_number() -> int:
    if not ALCHEMY_API_KEY:
        raise RuntimeError("Missing ALCHEMY_API_KEY in .env")

    url = f"https://{ALCHEMY_NETWORK}.g.alchemy.com/v2/{ALCHEMY_API_KEY}"

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_blockNumber",
        "params": []
    }

    response = requests.post(url, json=payload, timeout=10)
    response.raise_for_status()

    data = response.json()

    if "result" not in data:
        raise RuntimeError(f"Alchemy response missing result: {data}")

    return int(data["result"], 16)