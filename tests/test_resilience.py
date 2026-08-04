import pytest

from app.routers import trust
from app.schemas import WalletReputationResponse
from app.services.resilience import retry_operation


ADDRESS = "0x1111111111111111111111111111111111111111"


def fake_reputation(
    address: str,
    max_count: int = 10,
) -> WalletReputationResponse:
    return WalletReputationResponse(
        address=address,
        score=82,
        level="high",
        signals={
            "balance_eth": "1",
            "transfer_count": max_count,
            "transfer_status": "available",
        },
    )


def test_retry_recovers_from_transient_failure():
    call_count = 0
    delays = []

    def operation():
        nonlocal call_count
        call_count += 1

        if call_count < 3:
            raise RuntimeError(
                "temporary provider failure"
            )

        return "recovered"

    result = retry_operation(
        operation,
        operation_name="test_operation",
        attempts=3,
        base_delay_seconds=0.1,
        max_delay_seconds=1.0,
        sleep_fn=delays.append,
    )

    assert result == "recovered"
    assert call_count == 3
    assert delays == [0.1, 0.2]


def test_stale_score_is_returned_after_retries_fail(
    client,
    monkeypatch,
):
    trust.clear_trust_cache()

    monkeypatch.setattr(
        trust,
        "calculate_wallet_reputation",
        fake_reputation,
    )

    first = client.post(
        "/check_wallet",
        json={"wallet_address": ADDRESS},
    )

    assert first.status_code == 200
    assert first.headers["X-Trust-Cache"] == "MISS"

    for entry in trust.trust_cache.entries.values():
        entry.expires_at = 0.0

    monkeypatch.setattr(
        trust,
        "ALCHEMY_MAX_ATTEMPTS",
        1,
    )

    def unavailable_provider(
        address: str,
        max_count: int = 10,
    ):
        raise RuntimeError(
            "provider unavailable"
        )

    monkeypatch.setattr(
        trust,
        "calculate_wallet_reputation",
        unavailable_provider,
    )

    second = client.post(
        "/check_wallet",
        json={"wallet_address": ADDRESS},
    )

    assert second.status_code == 200
    assert second.headers["X-Trust-Cache"] == "STALE"
    assert "Stale wallet score" in (
        second.headers["Warning"]
    )
    assert second.json() == first.json()


def test_failed_refresh_preserves_last_score(
    monkeypatch,
):
    trust.clear_trust_cache()

    monkeypatch.setattr(
        trust,
        "calculate_wallet_reputation",
        fake_reputation,
    )

    original = trust.refresh_trust_result(
        ADDRESS
    )

    monkeypatch.setattr(
        trust,
        "ALCHEMY_MAX_ATTEMPTS",
        1,
    )

    def unavailable_provider(
        address: str,
        max_count: int = 10,
    ):
        raise RuntimeError(
            "provider unavailable"
        )

    monkeypatch.setattr(
        trust,
        "calculate_wallet_reputation",
        unavailable_provider,
    )

    with pytest.raises(RuntimeError):
        trust.refresh_trust_result(ADDRESS)

    preserved = trust.trust_cache.get_stale(
        ADDRESS
    )

    assert preserved == original
