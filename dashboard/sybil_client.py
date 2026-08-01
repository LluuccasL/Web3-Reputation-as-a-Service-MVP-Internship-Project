from typing import Any

from dashboard.api_client import TrustAPIClient


class SybilAPIClient(TrustAPIClient):
    def analyze_sybil_wallets(
        self,
        wallet_addresses: list[str],
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
