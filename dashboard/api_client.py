from typing import Any

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
