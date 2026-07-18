import pytest
import requests

from dashboard.api_client import DashboardAPIError, TrustAPIClient


class FakeResponse:
    def __init__(
        self,
        payload,
        status_code=200,
        ok=True,
        text="",
    ):
        self.payload = payload
        self.status_code = status_code
        self.ok = ok
        self.text = text

    def json(self):
        return self.payload


def test_client_adds_api_key_header():
    client = TrustAPIClient(
        base_url="http://127.0.0.1:8000",
        api_key="test-api-key",
    )

    assert client.session.headers["X-API-Key"] == "test-api-key"


def test_health_returns_api_response(monkeypatch):
    client = TrustAPIClient(
        base_url="http://127.0.0.1:8000",
        api_key="test-api-key",
    )

    def fake_request(method, url, timeout, **kwargs):
        assert method == "GET"
        assert url == "http://127.0.0.1:8000/health"
        assert timeout == 15

        return FakeResponse({"status": "healthy"})

    monkeypatch.setattr(client.session, "request", fake_request)

    assert client.health() == {"status": "healthy"}


def test_check_wallet_sends_wallet_address(monkeypatch):
    client = TrustAPIClient(
        base_url="http://127.0.0.1:8000",
        api_key="test-api-key",
    )

    wallet_address = "0x1111111111111111111111111111111111111111"

    def fake_request(method, url, timeout, **kwargs):
        assert method == "POST"
        assert url.endswith("/check_wallet")
        assert kwargs["json"] == {"wallet_address": wallet_address}

        return FakeResponse(
            {
                "wallet_address": wallet_address,
                "trust_tier": "medium",
            }
        )

    monkeypatch.setattr(client.session, "request", fake_request)

    result = client.check_wallet(wallet_address)

    assert result["wallet_address"] == wallet_address
    assert result["trust_tier"] == "medium"


def test_generate_proof_sends_validity_period(monkeypatch):
    client = TrustAPIClient(
        base_url="http://127.0.0.1:8000",
        api_key="test-api-key",
    )

    wallet_address = "0x2222222222222222222222222222222222222222"

    def fake_request(method, url, timeout, **kwargs):
        assert method == "POST"
        assert url.endswith("/generate_proof")
        assert kwargs["json"] == {
            "wallet_address": wallet_address,
            "valid_for_hours": 48,
        }

        return FakeResponse({"proof": "signed-proof"})

    monkeypatch.setattr(client.session, "request", fake_request)

    result = client.generate_proof(
        wallet_address=wallet_address,
        valid_for_hours=48,
    )

    assert result["proof"] == "signed-proof"


def test_structured_api_error_is_exposed(monkeypatch):
    client = TrustAPIClient(
        base_url="http://127.0.0.1:8000",
        api_key="invalid-key",
    )

    response_data = {
        "error": {
            "code": "INVALID_API_KEY",
            "message": "Invalid or missing API key.",
        },
        "detail": "Invalid or missing API key.",
    }

    monkeypatch.setattr(
        client.session,
        "request",
        lambda *args, **kwargs: FakeResponse(
            payload=response_data,
            status_code=401,
            ok=False,
        ),
    )

    with pytest.raises(DashboardAPIError) as exc_info:
        client.check_wallet(
            "0x3333333333333333333333333333333333333333"
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.error_code == "INVALID_API_KEY"
    assert exc_info.value.message == "Invalid or missing API key."


def test_connection_error_is_converted_to_dashboard_error(monkeypatch):
    client = TrustAPIClient(
        base_url="http://127.0.0.1:8000",
        api_key="test-api-key",
    )

    def raise_connection_error(*args, **kwargs):
        raise requests.ConnectionError("Connection refused")

    monkeypatch.setattr(
        client.session,
        "request",
        raise_connection_error,
    )

    with pytest.raises(DashboardAPIError) as exc_info:
        client.health()

    assert (
        exc_info.value.message
        == "Could not connect to the local Trust API."
    )
