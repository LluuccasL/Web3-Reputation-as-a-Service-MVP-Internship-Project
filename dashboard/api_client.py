from typing import Any
from urllib.parse import urlparse
import requests


class DashboardAPIError(Exception):
    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        error_code: str | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code


class TrustAPIClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: int = 15,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

        hostname = urlparse(self.base_url).hostname

        if hostname in {"127.0.0.1", "localhost", "::1"}:
            self.session.trust_env = False

        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )

        if api_key:
            self.session.headers.update({"X-API-Key": api_key})

    def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> Any:
        url = f"{self.base_url}{path}"

        try:
            response = self.session.request(
                method=method,
                url=url,
                timeout=self.timeout,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise DashboardAPIError(
                "Could not connect to the local Trust API."
            ) from exc

        try:
            data = response.json()
        except ValueError:
            data = {
                "detail": response.text
                or "The API returned an unreadable response."
            }

        if not response.ok:
            error_data = data.get("error", {}) if isinstance(data, dict) else {}

            message = (
                error_data.get("message")
                or (
                    data.get("detail")
                    if isinstance(data, dict)
                    else None
                )
                or f"API request failed with status {response.status_code}."
            )

            raise DashboardAPIError(
                message=message,
                status_code=response.status_code,
                error_code=error_data.get("code"),
            )

        return data

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def list_wallets(self) -> list[dict[str, Any]]:
        data = self._request("GET", "/wallets")

        if not isinstance(data, list):
            raise DashboardAPIError(
                "The wallet endpoint returned an unexpected response."
            )

        return data

    def check_wallet(self, wallet_address: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/check_wallet",
            json={"wallet_address": wallet_address},
        )

    def generate_proof(
        self,
        wallet_address: str,
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

    def check_wallet_enhanced(
        self,
        wallet_address: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/check_wallet/enhanced",
            json={
                "wallet_address": wallet_address,
            },
        )


    def submit_score_job(
        self,
        wallet_address: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/jobs/score-wallet",
            json={"wallet_address": wallet_address},
        )

    def refresh_wallet_score(
        self,
        wallet_address: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/wallets/{wallet_address}/refresh-score",
        )

    def get_job(
        self,
        job_id: str,
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/jobs/{job_id}",
        )

    def get_latest_score(
        self,
        wallet_address: str,
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/wallets/{wallet_address}/latest-score",
        )

    def get_demo_wallets(self) -> dict[str, Any]:
        return self._request(
            "GET",
            "/demo_wallets",
        )


    def get_monitoring_metrics(self) -> dict:
        data = self._request(
            "GET",
            "/performance/metrics",
        )

        if not isinstance(data, dict):
            raise DashboardAPIError(
                "The monitoring endpoint returned "
                "an unexpected response."
            )

        return data


    def list_jobs(
        self,
        limit: int = 20,
        status: str | None = None,
    ) -> dict:
        params = {"limit": limit}

        if status:
            params["status"] = status

        data = self._request(
            "GET",
            "/jobs",
            params=params,
        )

        if (
            not isinstance(data, dict)
            or not isinstance(data.get("jobs"), list)
        ):
            raise DashboardAPIError(
                "The jobs endpoint returned "
                "an unexpected response."
            )

        return data


    def submit_score_wallet_job(
        self,
        wallet_address: str,
    ) -> dict:
        return self._request(
            "POST",
            "/jobs/score-wallet",
            json={
                "wallet_address": wallet_address,
            },
        )
