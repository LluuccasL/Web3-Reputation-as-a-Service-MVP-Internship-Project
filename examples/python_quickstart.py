import os

from web3_trust import TrustAPIClient, TrustAPIError


API_URL = os.getenv(
    "WEB3_TRUST_API_URL",
    "http://127.0.0.1:8000",
)
API_KEY = os.getenv("WEB3_TRUST_API_KEY", "")
DEMO_WALLET = "0xd000000000000000000000000000000000000001"


def main() -> None:
    if not API_KEY:
        raise SystemExit("Set WEB3_TRUST_API_KEY before running this example.")

    try:
        with TrustAPIClient(
            base_url=API_URL,
            api_key=API_KEY,
        ) as client:
            version = client.version()
            trust = client.check_wallet(DEMO_WALLET)
            signed_proof = client.generate_proof(DEMO_WALLET)
            verification = client.verify_proof(signed_proof)

        print(f"API version: {version['version']}")
        print(f"Trust tier: {trust['trust_tier']}")
        print(f"Human likelihood: {trust['human_likelihood']}")
        print(f"Proof valid: {verification['valid']}")
    except TrustAPIError as exc:
        print(
            "Request failed: "
            f"code={exc.code} status={exc.status_code} "
            f"request_id={exc.request_id} message={exc.message}"
        )
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
