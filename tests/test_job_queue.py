import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import BackgroundJob
from app.services.job_queue import JobQueue


@pytest.fixture()
def queue_context(tmp_path):
    database_path = tmp_path / "jobs.db"
    engine = create_engine(
        f"sqlite:///{database_path}",
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

    yield queue, session_factory

    queue.shutdown()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_submit_persists_and_completes_job(queue_context):
    queue, session_factory = queue_context
    address = "0x" + "1" * 40

    job_id = queue.submit(
        wallet_address=address,
        job_type="score_wallet",
        task=lambda: {"score": 91},
    )

    job = queue.wait(job_id, timeout=5)

    assert job is not None
    assert job.status == "completed"
    assert job.wallet_address == address
    assert job.job_type == "score_wallet"
    assert job.attempts == 1
    assert job.result == {"score": 91}
    assert job.error is None
    assert job.started_at is not None
    assert job.completed_at is not None

    with session_factory() as db:
        stored_job = db.get(BackgroundJob, job_id)
        assert stored_job is not None
        assert stored_job.status == "completed"


def test_failure_is_recorded_without_escaping_worker(
    queue_context,
):
    queue, _ = queue_context

    def failing_task():
        raise RuntimeError("Alchemy unavailable")

    job_id = queue.submit(
        wallet_address="0x" + "2" * 40,
        job_type="score_wallet",
        task=failing_task,
    )

    job = queue.wait(job_id, timeout=5)

    assert job is not None
    assert job.status == "failed"
    assert job.attempts == 1
    assert job.error == "Alchemy unavailable"
    assert job.completed_at is not None


def test_list_jobs_returns_newest_first(queue_context):
    queue, _ = queue_context

    first_id = queue.submit(
        wallet_address="0x" + "3" * 40,
        job_type="first",
        task=lambda: None,
    )
    queue.wait(first_id, timeout=5)

    second_id = queue.submit(
        wallet_address="0x" + "4" * 40,
        job_type="second",
        task=lambda: None,
    )
    queue.wait(second_id, timeout=5)

    jobs = queue.list_jobs(limit=2)

    assert [job.id for job in jobs] == [
        second_id,
        first_id,
    ]
