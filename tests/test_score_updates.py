from threading import Event

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.services.job_queue import JobQueue


ADDRESS = "0x1111111111111111111111111111111111111111"


@pytest.fixture()
def score_queue(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'scores.db'}",
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

    yield queue

    queue.shutdown()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_active_wallet_job_is_deduplicated(
    score_queue,
):
    release = Event()
    started = Event()

    def waiting_task():
        started.set()
        release.wait(5)
        return {"confidence_score": 0.70}

    first_id, first_created = (
        score_queue.submit_unique(
            wallet_address=ADDRESS,
            job_type="score_wallet",
            task=waiting_task,
        )
    )

    assert started.wait(5)

    second_id, second_created = (
        score_queue.submit_unique(
            wallet_address=ADDRESS,
            job_type="refresh_score",
            task=lambda: {
                "confidence_score": 0.80
            },
        )
    )

    assert first_created is True
    assert second_created is False
    assert second_id == first_id

    release.set()
    score_queue.wait(first_id, timeout=5)


def test_failure_does_not_replace_latest_score(
    score_queue,
):
    completed_id = score_queue.submit(
        wallet_address=ADDRESS,
        job_type="score_wallet",
        task=lambda: {
            "confidence_score": 0.82
        },
    )

    score_queue.wait(
        completed_id,
        timeout=5,
    )

    latest = score_queue.get_latest_score(
        ADDRESS
    )

    assert latest is not None
    assert latest.job_id == completed_id
    assert latest.result == {
        "confidence_score": 0.82
    }

    def failing_task():
        raise RuntimeError("temporary failure")

    failed_id = score_queue.submit(
        wallet_address=ADDRESS,
        job_type="refresh_score",
        task=failing_task,
    )

    score_queue.wait(
        failed_id,
        timeout=5,
    )

    latest = score_queue.get_latest_score(
        ADDRESS
    )

    assert latest is not None
    assert latest.job_id == completed_id
    assert latest.result == {
        "confidence_score": 0.82
    }


def test_wallet_ingestion_queues_refresh(
    client,
    monkeypatch,
):
    queued_addresses = []

    monkeypatch.setattr(
        "app.routers.wallets.get_latest_block_number",
        lambda: 123456,
    )

    monkeypatch.setattr(
        "app.routers.wallets.queue_wallet_rescore",
        lambda queue, address: (
            queued_addresses.append(address)
            or ("test-job", True)
        ),
    )

    response = client.post(
        "/wallets/ingest",
        json={"address": ADDRESS},
    )

    assert response.status_code == 200
    assert queued_addresses == [
        ADDRESS.lower()
    ]
