import pytest
from pydantic import ValidationError

from app.demo_wallets import (
    DEMO_ADDRESS_BY_KEY,
    get_demo_enriched_data,
)
from app.schemas_sybil import SybilAnalyzeRequest


def _addresses(*scenario_keys: str) -> list[str]:
    return [
        DEMO_ADDRESS_BY_KEY[scenario_key]
        for scenario_key in scenario_keys
    ]


def test_request_normalizes_addresses():
    addresses = _addresses(
        "sybil_alpha",
        "sybil_beta",
    )

    payload = SybilAnalyzeRequest(
        wallet_addresses=[
            addresses[0].upper().replace("0X", "0x"),
            addresses[1],
        ]
    )

    assert payload.wallet_addresses == [
        address.lower()
        for address in addresses
    ]


def test_request_rejects_duplicate_addresses():
    address = DEMO_ADDRESS_BY_KEY["sybil_alpha"]

    with pytest.raises(
        ValidationError,
        match="must not contain duplicates",
    ):
        SybilAnalyzeRequest(
            wallet_addresses=[
                address,
                address.upper().replace("0X", "0x"),
            ]
        )


def test_sybil_endpoint_detects_demo_cluster(
    client,
    monkeypatch,
):
    monkeypatch.setenv("DEMO_MODE", "true")

    response = client.post(
        "/sybil/analyze",
        json={
            "wallet_addresses": _addresses(
                "sybil_alpha",
                "sybil_beta",
                "sybil_gamma",
            )
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["analyzed_wallet_count"] == 3
    assert data["cluster_count"] == 1
    assert data["clusters"][0]["cluster_size"] == 3
    assert data["clusters"][0][
        "sybil_risk_level"
    ] == "critical"
    assert data["relationship_graph"]["node_count"] == 3
    assert data["relationship_graph"]["edge_count"] == 3


def test_sybil_endpoint_keeps_independent_wallets_separate(
    client,
    monkeypatch,
):
    monkeypatch.setenv("DEMO_MODE", "true")

    response = client.post(
        "/sybil/analyze",
        json={
            "wallet_addresses": _addresses(
                "established_human",
                "normal_active",
            ),
            "timing_window_seconds": 600,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["cluster_count"] == 0
    assert data["relationship_graph"]["edge_count"] == 0

    assert all(
        result["sybil_risk_score"] == 0
        for result in data["wallet_results"]
    )

    assert data["thresholds"][
        "timing_window_seconds"
    ] == 600


@pytest.mark.parametrize(
    "body",
    [
        {"wallet_addresses": []},
        {
            "wallet_addresses": _addresses(
                "sybil_alpha",
            )
        },
        {
            "wallet_addresses": [
                "not-a-wallet",
                DEMO_ADDRESS_BY_KEY["sybil_beta"],
            ]
        },
        {
            "wallet_addresses": _addresses(
                "sybil_alpha",
                "sybil_alpha",
            )
        },
        {
            "wallet_addresses": _addresses(
                "sybil_alpha",
                "sybil_beta",
            ),
            "timing_window_seconds": -1,
        },
    ],
)
def test_sybil_endpoint_rejects_invalid_requests(
    client,
    body,
):
    response = client.post(
        "/sybil/analyze",
        json=body,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == (
        "INVALID_REQUEST"
    )


def test_sybil_endpoint_requires_api_key(client):
    client.headers.pop("X-API-Key", None)

    response = client.post(
        "/sybil/analyze",
        json={
            "wallet_addresses": _addresses(
                "sybil_alpha",
                "sybil_beta",
            )
        },
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == (
        "INVALID_API_KEY"
    )


def test_sybil_endpoint_maps_provider_error(
    client,
    monkeypatch,
):
    def unavailable(address: str):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(
        "app.routers.sybil.enrich_wallet",
        unavailable,
    )

    response = client.post(
        "/sybil/analyze",
        json={
            "wallet_addresses": _addresses(
                "sybil_alpha",
                "sybil_beta",
            )
        },
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == (
        "BLOCKCHAIN_PROVIDER_ERROR"
    )


def test_sybil_route_is_registered(client):
    paths = client.get(
        "/openapi.json"
    ).json()["paths"]

    assert "/sybil/analyze" in paths


def test_demo_fixture_shape_still_matches_endpoint_schema():
    for address in _addresses(
        "sybil_alpha",
        "sybil_beta",
        "sybil_gamma",
    ):
        assert get_demo_enriched_data(address) is not None
