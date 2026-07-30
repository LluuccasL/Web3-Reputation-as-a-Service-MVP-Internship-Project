from app.routers import trust
from app.schemas_demo import DemoWalletCatalogResponse


def test_demo_catalog_is_returned_when_enabled(
    monkeypatch,
):
    monkeypatch.setenv("DEMO_MODE", "true")

    result = trust.get_demo_wallet_catalog(
        _api_key="test-key",
    )

    validated = DemoWalletCatalogResponse.model_validate(
        result
    )

    assert validated.demo_mode_enabled is True
    assert len(validated.wallets) == 12
    assert all(
        wallet.synthetic is True
        for wallet in validated.wallets
    )

    scenario_keys = {
        wallet.scenario_key
        for wallet in validated.wallets
    }

    assert "established_human" in scenario_keys
    assert "burst_bot" in scenario_keys
    assert "sybil_alpha" in scenario_keys


def test_demo_catalog_is_hidden_when_disabled(
    monkeypatch,
):
    monkeypatch.setenv("DEMO_MODE", "false")

    result = trust.get_demo_wallet_catalog(
        _api_key="test-key",
    )

    assert result.demo_mode_enabled is False
    assert result.wallets == []


def test_demo_wallet_route_is_registered():
    paths = {
        route.path
        for route in trust.router.routes
    }

    assert "/demo_wallets" in paths
