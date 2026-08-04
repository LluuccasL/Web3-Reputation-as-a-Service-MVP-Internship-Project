from dashboard.api_client import (
    TrustAPIClient,
)
from dashboard.operations_view import (
    active_job_count,
    job_rows,
    job_status_counts,
    route_rows,
    terminal_job_rows,
)


ADDRESS = (
    "0x1111111111111111111111111111111111111111"
)


def sample_jobs():
    return [
        {
            "id": "job-1",
            "wallet_address": ADDRESS,
            "job_type": "refresh_score",
            "status": "queued",
            "attempts": 0,
            "created_at": "2026-08-04T00:00:00Z",
            "completed_at": None,
            "error": None,
        },
        {
            "id": "job-2",
            "wallet_address": ADDRESS,
            "job_type": "score_wallet",
            "status": "completed",
            "attempts": 1,
            "created_at": "2026-08-04T00:01:00Z",
            "completed_at": "2026-08-04T00:01:01Z",
            "error": None,
        },
        {
            "id": "job-3",
            "wallet_address": ADDRESS,
            "job_type": "refresh_score",
            "status": "failed",
            "attempts": 1,
            "created_at": "2026-08-04T00:02:00Z",
            "completed_at": "2026-08-04T00:02:01Z",
            "error": "provider unavailable",
        },
    ]


def test_counts_and_identifies_active_jobs():
    jobs = sample_jobs()
    counts = job_status_counts(jobs)

    assert counts == {
        "queued": 1,
        "running": 0,
        "completed": 1,
        "failed": 1,
    }
    assert active_job_count(jobs) == 1


def test_builds_job_rows():
    rows = job_rows(sample_jobs())

    assert rows[0]["Type"] == (
        "Refresh Score"
    )
    assert rows[0]["Status"] == "Queued"
    assert rows[2]["Error"] == (
        "provider unavailable"
    )

    terminal_rows = terminal_job_rows(
        sample_jobs()
    )

    assert len(terminal_rows) == 2
    assert {
        row["Status"]
        for row in terminal_rows
    } == {
        "Completed",
        "Failed",
    }


def test_builds_route_rows():
    metrics = {
        "requests": {
            "routes": [
                {
                    "method": "POST",
                    "path": "/check_wallet",
                    "requests": 4,
                    "errors": 1,
                    "average_latency_ms": 12.5,
                    "max_latency_ms": 20.0,
                }
            ]
        }
    }

    rows = route_rows(metrics)

    assert rows == [
        {
            "Method": "POST",
            "Route": "/check_wallet",
            "Requests": 4,
            "Errors": 1,
            "Average Latency (ms)": 12.5,
            "Maximum Latency (ms)": 20.0,
        }
    ]


def test_client_loads_metrics_and_jobs(
    monkeypatch,
):
    client = TrustAPIClient(
        base_url="http://127.0.0.1:8000",
        api_key="test-key",
    )
    calls = []

    def fake_request(
        method,
        path,
        **kwargs,
    ):
        calls.append(
            (
                method,
                path,
                kwargs,
            )
        )

        if path == "/performance/metrics":
            return {
                "requests": {},
                "cache": {},
                "background_jobs": {},
            }

        return {
            "count": 1,
            "jobs": sample_jobs()[:1],
        }

    monkeypatch.setattr(
        client,
        "_request",
        fake_request,
    )

    metrics = (
        client.get_monitoring_metrics()
    )
    jobs = client.list_jobs(
        limit=10,
        status="queued",
    )

    assert "cache" in metrics
    assert jobs["count"] == 1
    assert calls == [
        (
            "GET",
            "/performance/metrics",
            {},
        ),
        (
            "GET",
            "/jobs",
            {
                "params": {
                    "limit": 10,
                    "status": "queued",
                }
            },
        ),
    ]


def test_client_queues_wallet_refresh(
    monkeypatch,
):
    client = TrustAPIClient(
        base_url="http://127.0.0.1:8000",
        api_key="test-key",
    )

    def fake_request(
        method,
        path,
        **kwargs,
    ):
        assert method == "POST"
        assert path == (
            f"/wallets/{ADDRESS}"
            "/refresh-score"
        )
        assert kwargs == {}

        return {
            "job_id": "job-123",
            "status": "queued",
            "status_url": "/jobs/job-123",
        }

    monkeypatch.setattr(
        client,
        "_request",
        fake_request,
    )

    result = client.refresh_wallet_score(
        ADDRESS
    )

    assert result["job_id"] == "job-123"
    assert result["status"] == "queued"
