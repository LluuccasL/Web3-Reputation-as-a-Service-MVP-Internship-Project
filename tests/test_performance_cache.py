from concurrent.futures import ThreadPoolExecutor
from threading import Lock
import time

from app.routers import trust
from app.schemas import WalletReputationResponse


ADDRESS_ONE = (
    "0x1111111111111111111111111111111111111111"
)
ADDRESS_TWO = (
    "0x2222222222222222222222222222222222222222"
)


def fake_reputation(
    address: str,
    max_count: int = 10,
) -> WalletReputationResponse:
    return WalletReputationResponse(
        address=address,
        score=80,
        level="high",
        signals={
            "balance_eth": "1",
            "transfer_count": max_count,
            "transfer_status": "available",
        },
    )


def test_check_wallet_reports_cache_and_latency(
    client,
    monkeypatch,
):
    monkeypatch.setattr(
        trust,
        "calculate_wallet_reputation",
        fake_reputation,
    )

    first = client.post(
        "/check_wallet",
        json={"wallet_address": ADDRESS_ONE},
    )

    second = client.post(
        "/check_wallet",
        json={"wallet_address": ADDRESS_ONE},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.headers["X-Trust-Cache"] == "MISS"
    assert second.headers["X-Trust-Cache"] == "HIT"
    assert (
        float(
            first.headers["X-Processing-Time-Ms"]
        )
        >= 0
    )

    response = client.get("/performance/cache")

    assert response.status_code == 200

    stats = response.json()

    assert stats["size"] == 1
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["hit_rate"] == 0.5


def test_targeted_invalidation_preserves_other_wallets(
    monkeypatch,
):
    calls = {
        ADDRESS_ONE: 0,
        ADDRESS_TWO: 0,
    }

    def counting_reputation(
        address: str,
        max_count: int = 10,
    ) -> WalletReputationResponse:
        calls[address] += 1
        return fake_reputation(
            address,
            max_count,
        )

    monkeypatch.setattr(
        trust,
        "calculate_wallet_reputation",
        counting_reputation,
    )

    trust.clear_trust_cache()

    trust.calculate_trust_result(ADDRESS_ONE)
    trust.calculate_trust_result(ADDRESS_TWO)

    trust.clear_trust_cache(ADDRESS_ONE)

    trust.calculate_trust_result(ADDRESS_ONE)
    trust.calculate_trust_result(ADDRESS_TWO)

    assert calls[ADDRESS_ONE] == 2
    assert calls[ADDRESS_TWO] == 1


def test_concurrent_requests_share_one_calculation(
    monkeypatch,
):
    call_lock = Lock()
    call_count = 0

    def slow_reputation(
        address: str,
        max_count: int = 10,
    ) -> WalletReputationResponse:
        nonlocal call_count

        with call_lock:
            call_count += 1

        time.sleep(0.05)

        return fake_reputation(
            address,
            max_count,
        )

    monkeypatch.setattr(
        trust,
        "calculate_wallet_reputation",
        slow_reputation,
    )

    trust.clear_trust_cache()

    with ThreadPoolExecutor(
        max_workers=2
    ) as executor:
        results = list(
            executor.map(
                lambda _: (
                    trust.calculate_trust_result(
                        ADDRESS_ONE
                    )
                ),
                range(2),
            )
        )

    assert call_count == 1
    assert len(results) == 2
    assert results[0] == results[1]
