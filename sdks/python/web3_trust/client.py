from collections.abc import Mapping
from typing import Any
from urllib.parse import quote, urlparse

import requests


class TrustAPIError(Exception):
    """Structured API or transport error returned by the SDK."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        code: str | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.request_id = request_id


class TrustAPIClient:
    """Synchronous developer client for Web3 Trust API v1."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout: float = 15.0,
        session: requests.Session | None = None,
    ) -> None:
        parsed_url = urlparse(base_url)

        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ValueError("base_url must be an absolute HTTP(S) URL")

        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")

        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )

        if api_key:
            self.session.headers["X-API-Key"] = api_key

        if parsed_url.hostname in {"127.0.0.1", "localhost", "::1"}:
            self.session.trust_env = False

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> "TrustAPIClient":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> Any:
        try:
            response = self.session.request(
                method=method,
                url=f"{self.base_url}{path}",
                timeout=self.timeout,
                **kwargs,
            )
        except requests.Timeout as exc:
            raise TrustAPIError(
                "The Web3 Trust API request timed out.",
                code="CLIENT_TIMEOUT",
            ) from exc
        except requests.RequestException as exc:
            raise TrustAPIError(
                "Could not connect to the Web3 Trust API.",
                code="CONNECTION_ERROR",
            ) from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise TrustAPIError(
                "The Web3 Trust API returned an unreadable response.",
                status_code=response.status_code,
                code="INVALID_RESPONSE",
            ) from exc

        if response.ok:
            return data

        error = data.get("error", {}) if isinstance(data, Mapping) else {}
        message = (
            error.get("message")
            or (data.get("detail") if isinstance(data, Mapping) else None)
            or f"API request failed with status {response.status_code}."
        )

        raise TrustAPIError(
            str(message),
            status_code=response.status_code,
            code=error.get("code"),
            request_id=error.get("request_id"),
        )

    def version(self) -> dict[str, Any]:
        return self._request("GET", "/version")

    def list_demo_wallets(self) -> dict[str, Any]:
        return self._request("GET", "/demo_wallets")

    def check_wallet(self, wallet_address: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/check_wallet",
            json={"wallet_address": wallet_address},
        )

    def check_wallet_enhanced(self, wallet_address: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/check_wallet/enhanced",
            json={"wallet_address": wallet_address},
        )

    def generate_proof(
        self,
        wallet_address: str,
        *,
        valid_for_hours: int = 24,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/generate_proof",
            json={
                "wallet_address": wallet_address,
                "valid_for_hours": valid_for_hours,
            },
        )

    def verify_proof(self, signed_proof: Mapping[str, Any]) -> dict[str, Any]:
        return self._request(
            "POST",
            "/verify_proof",
            json=dict(signed_proof),
        )

    def analyze_sybil(
        self,
        wallet_addresses: list[str],
        *,
        timing_window_seconds: int = 300,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/sybil/analyze",
            json={
                "wallet_addresses": wallet_addresses,
                "timing_window_seconds": timing_window_seconds,
            },
        )

    def submit_score_job(self, wallet_address: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/jobs/score-wallet",
            json={"wallet_address": wallet_address},
        )

    def refresh_score(self, wallet_address: str) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/wallets/{quote(wallet_address, safe='')}/refresh-score",
        )

    def get_job(self, job_id: str) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/jobs/{quote(job_id, safe='')}",
        )

    def list_jobs(
        self,
        *,
        limit: int = 20,
        status: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit}

        if status is not None:
            params["status"] = status

        return self._request("GET", "/jobs", params=params)

    def get_latest_score(self, wallet_address: str) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/wallets/{quote(wallet_address, safe='')}/latest-score",
        )

    def get_metrics(self) -> dict[str, Any]:
        return self._request("GET", "/performance/metrics")
