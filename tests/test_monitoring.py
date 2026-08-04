import json
import logging
from uuid import UUID

from app.services.monitoring import (
    JSONLogFormatter,
    request_metrics,
)


def test_request_id_and_metrics_endpoint(
    client,
):
    request_metrics.reset()

    response = client.get(
        "/performance/cache"
    )

    assert response.status_code == 200

    request_id = response.headers[
        "X-Request-ID"
    ]

    parsed_request_id = UUID(request_id)

    assert parsed_request_id.hex == (
        request_id.replace("-", "").lower()
    )

    metrics_response = client.get(
        "/performance/metrics"
    )

    assert metrics_response.status_code == 200

    metrics = metrics_response.json()

    assert metrics["requests"][
        "total_requests"
    ] == 1

    assert metrics["requests"][
        "active_requests"
    ] == 0

    route = next(
        item
        for item in metrics["requests"][
            "routes"
        ]
        if item["path"]
        == "/performance/cache"
    )

    assert route["method"] == "GET"
    assert route["requests"] == 1
    assert route["errors"] == 0

    assert "cache" in metrics
    assert "background_jobs" in metrics


def test_missing_route_is_recorded_as_error(
    client,
):
    request_metrics.reset()

    response = client.get(
        "/route-that-does-not-exist"
    )

    assert response.status_code == 404
    assert "X-Request-ID" in response.headers

    metrics = client.get(
        "/performance/metrics"
    ).json()

    assert metrics["requests"]["errors"] == 1

    route = next(
        item
        for item in metrics["requests"][
            "routes"
        ]
        if item["path"] == "unmatched"
    )

    assert route["requests"] == 1
    assert route["errors"] == 1


def test_json_log_formatter():
    formatter = JSONLogFormatter()

    record = logging.LogRecord(
        name="web3_trust.monitoring",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="request_completed",
        args=(),
        exc_info=None,
    )

    record.event_name = "request_completed"
    record.event_data = {
        "request_id": "test-request",
        "method": "POST",
        "path": "/check_wallet",
        "status_code": 200,
        "duration_ms": 12.5,
    }

    payload = json.loads(
        formatter.format(record)
    )

    assert payload["event"] == (
        "request_completed"
    )
    assert payload["request_id"] == (
        "test-request"
    )
    assert payload["path"] == (
        "/check_wallet"
    )
    assert payload["status_code"] == 200
