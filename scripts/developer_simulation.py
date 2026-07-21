import os
import time
from typing import Any
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv


load_dotenv()

API_BASE_URL = os.getenv(
    "DASHBOARD_API_URL",
    "http://127.0.0.1:8000",
).rstrip("/")
API_KEY = os.getenv("DASHBOARD_API_KEY", "")
TIMEOUT = 15


def make_session(api_key: str = "") -> requests.Session:
    session = requests.Session()

    hostname = urlparse(API_BASE_URL).hostname
    if hostname in {"127.0.0.1", "localhost", "::1"}:
        session.trust_env = False

    session.headers.update(
        {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
    )

    if api_key:
        session.headers["X-API-Key"] = api_key

    return session


def run_request(
    name: str,
    session: requests.Session,
    method: str,
    path: str,
    expected_status: int,
    **kwargs: Any,
) -> tuple[bool, Any]:
    start_time = time.perf_counter()

    try:
        response = session.request(
            method=method,
            url=f"{API_BASE_URL}{path}",
            timeout=TIMEOUT,
            **kwargs,
        )
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        try:
            data = response.json()
        except ValueError:
            data = response.text

        passed = response.status_code == expected_status
        result = "PASS" if passed else "FAIL"

        print(
            f"{result:<4} | {name:<30} | "
            f"HTTP {response.status_code:<3} | "
            f"{elapsed_ms:8.2f} ms"
        )

        if not passed:
            print(f"       Response: {data}")

        return passed, data

    except requests.RequestException as exc:
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        print(
            f"FAIL | {name:<30} | "
            f"CONNECTION ERROR | {elapsed_ms:8.2f} ms"
        )
        print(f"       Error: {exc}")

        return False, None


def get_wallet_address(
    session: requests.Session,
) -> tuple[bool, str | None]:
    passed, wallets = run_request(
        name="List stored wallets",
        session=session,
        method="GET",
        path="/wallets",
        expected_status=200,
    )

    if not passed or not isinstance(wallets, list) or not wallets:
        return False, None

    first_wallet = wallets[0]
    wallet_address = (
        first_wallet.get("wallet_address")
        or first_wallet.get("address")
    )

    if not wallet_address:
        print("FAIL | Select wallet                 | Missing address")
        return False, None

    print(
        f"INFO | Selected wallet              | "
        f"{wallet_address[:10]}...{wallet_address[-6:]}"
    )

    return True, wallet_address


def main() -> None:
    print("\nDeveloper API Simulation")
    print(f"API: {API_BASE_URL}")
    print("-" * 76)

    if not API_KEY:
        print(
            "ERROR: DASHBOARD_API_KEY is missing from the .env file."
        )
        raise SystemExit(1)

    results: list[bool] = []

    public_session = make_session()
    authenticated_session = make_session(API_KEY)
    invalid_session = make_session("invalid-developer-key")

    passed, _ = run_request(
        name="Health check",
        session=public_session,
        method="GET",
        path="/health",
        expected_status=200,
    )
    results.append(passed)

    passed, _ = run_request(
        name="Reject invalid API key",
        session=invalid_session,
        method="POST",
        path="/check_wallet",
        expected_status=401,
        json={
            "wallet_address":
                "0x1111111111111111111111111111111111111111"
        },
    )
    results.append(passed)

    wallet_found, wallet_address = get_wallet_address(
        authenticated_session
    )
    results.append(wallet_found)

    if wallet_address:
        passed, _ = run_request(
            name="Check wallet trust",
            session=authenticated_session,
            method="POST",
            path="/check_wallet",
            expected_status=200,
            json={"wallet_address": wallet_address},
        )
        results.append(passed)

        passed, _ = run_request(
            name="Generate signed proof",
            session=authenticated_session,
            method="POST",
            path="/generate_proof",
            expected_status=200,
            json={
                "wallet_address": wallet_address,
                "valid_for_hours": 24,
            },
        )
        results.append(passed)

    passed, _ = run_request(
        name="Reject invalid wallet",
        session=authenticated_session,
        method="POST",
        path="/check_wallet",
        expected_status=422,
        json={"wallet_address": "not-a-wallet"},
    )
    results.append(passed)

    passed_count = sum(results)
    total_count = len(results)
    failed_count = total_count - passed_count

    print("-" * 76)
    print(
        f"Simulation complete: {passed_count}/{total_count} passed, "
        f"{failed_count} failed."
    )

    if failed_count:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
