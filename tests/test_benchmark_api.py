import pytest

from scripts.benchmark_api import (
    demo_address,
    percentile,
    summarize,
)


def test_demo_address_has_valid_ethereum_shape():
    address = demo_address(1)

    assert address.startswith("0x")
    assert len(address) == 42


def test_percentile_interpolates_measurements():
    assert percentile(
        [10.0, 20.0, 30.0],
        0.50,
    ) == 20.0

    assert percentile(
        [10.0, 20.0],
        0.50,
    ) == 15.0


def test_summarize_returns_latency_statistics():
    result = summarize(
        [10.0, 20.0, 30.0, 40.0]
    )

    assert result == {
        "min": 10.0,
        "average": 25.0,
        "p50": 25.0,
        "p95": 38.5,
        "max": 40.0,
    }


def test_percentile_rejects_empty_input():
    with pytest.raises(ValueError):
        percentile([], 0.95)
