import time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.main import app
from app.routers import jobs
from app.services.job_queue import JobQueue


ADDRESS = "0x1111111111111111111111111111111111111111"


@pytest.fixture()
def endpoint_queue(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'endpoint_jobs.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    queue = JobQueue(
        session_factory=session_factory,
        max_workers=1,
    )
    app.dependency_overrides[jobs.get_job_queue] = lambda: queue

    yield queue

    app.dependency_overrides.pop(jobs.get_job_queue, None)
    queue.shutdown()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def wait_for_terminal_status(client, job_id: str) -> dict:
    for _ in range(100):
        response = client.get(f"/jobs/{job_id}")
        assert response.status_code == 200
        job = response.json()

        if job["status"] in {"completed", "failed"}:
            return job

        time.sleep(0.01)

    raise AssertionError("Job did not finish")


def test_submit_score_job_and_read_result(
    client,
    endpoint_queue,
    monkeypatch,
):
    monkeypatch.setattr(
        jobs,
        "calculate_job_result",
        lambda address, refresh: {
            "wallet_address": address,
            "confidence_score": 0.91,
            "refreshed": refresh,
        },
    )

    response = client.post(
        "/jobs/score-wallet",
        json={"wallet_address": ADDRESS},
    )

    assert response.status_code == 202
    accepted = response.json()
    assert accepted["status"] == "queued"

    job = wait_for_terminal_status(
        client,
        accepted["job_id"],
    )

    assert job["status"] == "completed"
    assert job["result"]["confidence_score"] == 0.91
    assert job["result"]["refreshed"] is False


def test_refresh_job_and_list_filter(
    client,
    endpoint_queue,
    monkeypatch,
):
    monkeypatch.setattr(
        jobs,
        "calculate_job_result",
        lambda address, refresh: {
            "wallet_address": address,
            "refreshed": refresh,
        },
    )

    response = client.post(
        f"/wallets/{ADDRESS}/refresh-score"
    )
    assert response.status_code == 202

    job_id = response.json()["job_id"]
    job = wait_for_terminal_status(client, job_id)

    assert job["job_type"] == "refresh_score"
    assert job["result"]["refreshed"] is True

    response = client.get(
        "/jobs",
        params={"status": "completed", "limit": 10},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["jobs"][0]["id"] == job_id


def test_unknown_job_returns_404(client, endpoint_queue):
    response = client.get("/jobs/missing-job")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "JOB_NOT_FOUND"
