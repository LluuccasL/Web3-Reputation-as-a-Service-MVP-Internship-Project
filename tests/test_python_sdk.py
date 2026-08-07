import pytest
import requests

from sdks.python.web3_trust import TrustAPIClient, TrustAPIError


class FakeResponse:
    def __init__(
        self,
        payload=None,
        *,
        status_code=200,
        ok=True,
        json_error=False,
    ):
        self.payload = payload
        self.status_code = status_code
        self.ok = ok
        self.json_error = json_error

    def json(self):
        if self.json_error:
            raise ValueError("not JSON")

        return self.payload


class FakeSession:
    def __init__(self, response=None):
        self.headers = {}
        self.trust_env = True
        self.response = response or FakeResponse({"ok": True})
        self.calls = []
        self.closed = False

    def request(self, **kwargs):
        self.calls.append(kwargs)
        return self.response

    def close(self):
        self.closed = True


def make_client(session=None):
    return TrustAPIClient(
        base_url="http://127.0.0.1:8000/",
        api_key="developer-key",
        session=session or FakeSession(),
    )


def test_client_configures_authentication_and_local_session():
    session = FakeSession()
    client = make_client(session)

    assert client.base_url == "http://127.0.0.1:8000"
    assert session.headers["X-API-Key"] == "developer-key"
    assert session.headers["Accept"] == "application/json"
    assert session.trust_env is False


def test_client_rejects_invalid_configuration():
    with pytest.raises(ValueError, match="absolute HTTP"):
        TrustAPIClient(base_url="localhost:8000", api_key="key")

    with pytest.raises(ValueError, match="greater than zero"):
        TrustAPIClient(
            base_url="http://localhost:8000",
            api_key="key",
            timeout=0,
        )


def test_check_wallet_sends_the_public_contract():
    session = FakeSession(FakeResponse({"trust_tier": "gold"}))
    client = make_client(session)
    address = "0x1111111111111111111111111111111111111111"

    result = client.check_wallet(address)

    assert result == {"trust_tier": "gold"}
    assert session.calls == [
        {
            "method": "POST",
            "url": "http://127.0.0.1:8000/check_wallet",
            "timeout": 15.0,
            "json": {"wallet_address": address},
        }
    ]


def test_generate_and_verify_proof_round_trip_payload():
    signed_proof = {
        "proof": {"proof_id": "proof-id"},
        "signature": "a" * 64,
    }
    session = FakeSession(FakeResponse(signed_proof))
    client = make_client(session)
    address = "0x2222222222222222222222222222222222222222"

    generated = client.generate_proof(address, valid_for_hours=48)
    client.verify_proof(generated)

    assert session.calls[0]["json"] == {
        "wallet_address": address,
        "valid_for_hours": 48,
    }
    assert session.calls[1]["url"].endswith("/verify_proof")
    assert session.calls[1]["json"] == signed_proof


def test_analyze_sybil_sends_group_and_timing_window():
    session = FakeSession(FakeResponse({"cluster_count": 1}))
    client = make_client(session)
    addresses = [
        "0x3333333333333333333333333333333333333333",
        "0x4444444444444444444444444444444444444444",
    ]

    client.analyze_sybil(addresses, timing_window_seconds=600)

    assert session.calls[0]["json"] == {
        "wallet_addresses": addresses,
        "timing_window_seconds": 600,
    }


def test_structured_api_error_preserves_debugging_fields():
    session = FakeSession(
        FakeResponse(
            {
                "error": {
                    "code": "INVALID_API_KEY",
                    "message": "Invalid or missing API key.",
                    "request_id": "request-123",
                }
            },
            status_code=401,
            ok=False,
        )
    )
    client = make_client(session)

    with pytest.raises(TrustAPIError) as exc_info:
        client.get_metrics()

    assert exc_info.value.status_code == 401
    assert exc_info.value.code == "INVALID_API_KEY"
    assert exc_info.value.request_id == "request-123"


def test_transport_and_invalid_response_errors_are_normalized():
    timeout_session = FakeSession()

    def raise_timeout(**_kwargs):
        raise requests.Timeout("late")

    timeout_session.request = raise_timeout

    with pytest.raises(TrustAPIError) as timeout_error:
        make_client(timeout_session).version()

    assert timeout_error.value.code == "CLIENT_TIMEOUT"

    invalid_session = FakeSession(
        FakeResponse(status_code=502, ok=False, json_error=True)
    )

    with pytest.raises(TrustAPIError) as invalid_error:
        make_client(invalid_session).version()

    assert invalid_error.value.code == "INVALID_RESPONSE"
    assert invalid_error.value.status_code == 502


def test_context_manager_closes_the_session():
    session = FakeSession()

    with make_client(session) as client:
        assert client.version() == {"ok": True}

    assert session.closed is True
