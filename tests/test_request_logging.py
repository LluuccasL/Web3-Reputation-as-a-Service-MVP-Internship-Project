import json
import logging


def test_request_log_contains_required_fields(
    client,
    caplog,
):
    caplog.set_level(
        logging.INFO,
        logger="web3_trust.request",
    )

    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["X-Request-ID"]

    request_records = [
        record
        for record in caplog.records
        if record.name == "web3_trust.request"
    ]

    assert request_records

    log_data = json.loads(
        request_records[-1].getMessage()
    )

    assert log_data["request_id"] == (
        response.headers["X-Request-ID"]
    )

    assert log_data["method"] == "GET"
    assert log_data["endpoint"] == "/health"
    assert log_data["status_code"] == 200
    assert log_data["duration_ms"] >= 0
    assert log_data["timestamp"]
    assert log_data["api_key_hash"]


def test_request_log_does_not_contain_raw_api_key(
    client,
    caplog,
):
    caplog.set_level(
        logging.INFO,
        logger="web3_trust.request",
    )

    raw_api_key = client.headers["X-API-Key"]

    response = client.get("/health")

    assert response.status_code == 200

    request_records = [
        record
        for record in caplog.records
        if record.name == "web3_trust.request"
    ]

    serialized_logs = "\n".join(
        record.getMessage()
        for record in request_records
    )

    assert raw_api_key not in serialized_logs
