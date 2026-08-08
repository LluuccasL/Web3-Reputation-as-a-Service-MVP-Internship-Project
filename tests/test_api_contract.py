from app.main import app
from app.version import API_NAME, API_VERSION


def test_version_endpoint_exposes_shared_api_version(client):
    response = client.get("/version")

    assert response.status_code == 200
    assert response.json() == {
        "name": API_NAME,
        "version": API_VERSION,
    }


def test_openapi_describes_final_mvp_contract():
    schema = app.openapi()

    assert schema["info"]["title"] == API_NAME
    assert schema["info"]["version"] == API_VERSION
    assert "/verify_proof" in schema["paths"]
    assert "/version" in schema["paths"]

    check_wallet = schema["paths"]["/check_wallet"]["post"]
    verify_proof = schema["paths"]["/verify_proof"]["post"]

    assert check_wallet["security"] == [
        {"Developer API Key": []}
    ]
    assert verify_proof["security"] == [
        {"Developer API Key": []}
    ]

    success_headers = check_wallet["responses"]["200"]["headers"]

    assert "X-Trust-Cache" in success_headers
    assert "X-Processing-Time-Ms" in success_headers
    assert "X-RateLimit-Remaining" in success_headers
    assert "X-Request-ID" in success_headers

    error_schema = check_wallet["responses"]["401"][
        "content"
    ]["application/json"]["schema"]

    assert error_schema["$ref"].endswith("/ErrorResponse")


def test_demo_wallet_schema_contains_a_useful_example():
    schema = app.openapi()
    demo_schema = schema["components"]["schemas"][
        "DemoWalletCatalogResponse"
    ]

    assert demo_schema["example"]["demo_mode_enabled"] is True
    assert demo_schema["example"]["wallets"][0][
        "scenario_key"
    ] == "established_human"


def test_existing_root_and_health_contracts_are_unchanged(client):
    assert client.get("/").json() == {
        "message": "Web3 Trust API is running"
    }
    assert client.get("/health").json() == {
        "status": "healthy"
    }
