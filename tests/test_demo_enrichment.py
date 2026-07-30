from app.demo_wallets import DEMO_ADDRESS_BY_KEY
from app.services import enrichment


LIVE_ADDRESS = (
    "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
)


def test_demo_wallet_uses_fixture_when_enabled(
    monkeypatch,
):
    monkeypatch.setenv("DEMO_MODE", "true")

    def should_not_call_live(address: str):
        raise AssertionError(
            "Live enrichment should not be called."
        )

    monkeypatch.setattr(
        enrichment,
        "_live_enrich_wallet",
        should_not_call_live,
    )

    address = DEMO_ADDRESS_BY_KEY["burst_bot"]
    result = enrichment.enrich_wallet(address)

    assert result["address"] == address
    assert result["is_demo"] is True
    assert result["demo_scenario"] == "burst_bot"
    assert len(result["transfers"]) == 8


def test_demo_wallet_uses_live_path_when_disabled(
    monkeypatch,
):
    monkeypatch.setenv("DEMO_MODE", "false")

    live_result = {
        "address": DEMO_ADDRESS_BY_KEY["normal_active"],
        "source": "live",
    }

    monkeypatch.setattr(
        enrichment,
        "_live_enrich_wallet",
        lambda address: live_result,
    )

    result = enrichment.enrich_wallet(
        DEMO_ADDRESS_BY_KEY["normal_active"]
    )

    assert result is live_result
    assert result["source"] == "live"


def test_regular_wallet_stays_on_live_path(
    monkeypatch,
):
    monkeypatch.setenv("DEMO_MODE", "true")

    live_result = {
        "address": LIVE_ADDRESS,
        "source": "live",
    }

    monkeypatch.setattr(
        enrichment,
        "_live_enrich_wallet",
        lambda address: live_result,
    )

    result = enrichment.enrich_wallet(LIVE_ADDRESS)

    assert result is live_result
    assert result["source"] == "live"
