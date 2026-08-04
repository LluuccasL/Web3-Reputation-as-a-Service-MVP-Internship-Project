from concurrent.futures import Future, ThreadPoolExecutor
from threading import Lock
from typing import Any, Callable
from uuid import uuid4

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import BackgroundJob, WalletScore, utc_now


JobTask = Callable[[], dict[str, Any] | None]


class JobQueue:
    def __init__(
        self,
        session_factory: Callable[[], Session] = SessionLocal,
        max_workers: int = 2,
    ):
        self.session_factory = session_factory
        self.executor = ThreadPoolExecutor(
            max_workers=max_workers
        )
        self.futures: dict[str, Future] = {}
        self.lock = Lock()

    def submit(
        self,
        wallet_address: str,
        job_type: str,
        task: JobTask,
    ) -> str:
        job_id, _ = self.submit_unique(
            wallet_address,
            job_type,
            task,
        )
        return job_id

    def submit_unique(
        self,
        wallet_address: str,
        job_type: str,
        task: JobTask,
    ) -> tuple[str, bool]:
        address = wallet_address.lower()

        with self.lock:
            db = self.session_factory()

            try:
                active_job = (
                    db.query(BackgroundJob)
                    .filter(
                        BackgroundJob.wallet_address == address,
                        BackgroundJob.status.in_(
                            ["queued", "running"]
                        ),
                    )
                    .order_by(
                        BackgroundJob.created_at.desc()
                    )
                    .first()
                )

                if active_job is not None:
                    return active_job.id, False

                job_id = str(uuid4())

                job = BackgroundJob(
                    id=job_id,
                    wallet_address=address,
                    job_type=job_type,
                    status="queued",
                )

                db.add(job)
                db.commit()
            finally:
                db.close()

            future = self.executor.submit(
                self._run_job,
                job_id,
                task,
            )

            self.futures[job_id] = future

        return job_id, True

    def _run_job(
        self,
        job_id: str,
        task: JobTask,
    ) -> None:
        db = self.session_factory()

        try:
            job = db.get(BackgroundJob, job_id)

            if job is None:
                return

            job.status = "running"
            job.attempts += 1
            job.started_at = utc_now()
            job.error = None
            db.commit()

            result = task()

            job = db.get(BackgroundJob, job_id)

            if job is None:
                return

            job.status = "completed"
            job.result = result
            job.completed_at = utc_now()

            self._store_latest_score(
                db,
                job,
                result,
            )

            db.commit()
        except Exception as exc:
            db.rollback()

            job = db.get(BackgroundJob, job_id)

            if job is not None:
                job.status = "failed"
                job.error = str(exc)
                job.completed_at = utc_now()
                db.commit()
        finally:
            db.close()

    def _store_latest_score(
        self,
        db: Session,
        job: BackgroundJob,
        result: dict[str, Any] | None,
    ) -> None:
        if (
            job.job_type
            not in {"score_wallet", "refresh_score"}
            or not isinstance(result, dict)
        ):
            return

        latest = db.get(
            WalletScore,
            job.wallet_address,
        )

        if latest is None:
            latest = WalletScore(
                wallet_address=job.wallet_address,
                job_id=job.id,
                result=result,
                updated_at=utc_now(),
            )

            db.add(latest)
            return

        latest.job_id = job.id
        latest.result = result
        latest.updated_at = utc_now()

    def get_job(
        self,
        job_id: str,
    ) -> BackgroundJob | None:
        db = self.session_factory()

        try:
            job = db.get(BackgroundJob, job_id)

            if job is not None:
                db.expunge(job)

            return job
        finally:
            db.close()

    def get_latest_score(
        self,
        wallet_address: str,
    ) -> WalletScore | None:
        db = self.session_factory()

        try:
            score = db.get(
                WalletScore,
                wallet_address.lower(),
            )

            if score is not None:
                db.expunge(score)

            return score
        finally:
            db.close()

    def list_jobs(
        self,
        limit: int = 100,
    ) -> list[BackgroundJob]:
        db = self.session_factory()

        try:
            jobs = (
                db.query(BackgroundJob)
                .order_by(
                    BackgroundJob.created_at.desc()
                )
                .limit(limit)
                .all()
            )

            for job in jobs:
                db.expunge(job)

            return jobs
        finally:
            db.close()

    def wait(
        self,
        job_id: str,
        timeout: float | None = None,
    ) -> BackgroundJob | None:
        with self.lock:
            future = self.futures.get(job_id)

        if future is not None:
            future.result(timeout=timeout)

        return self.get_job(job_id)

    def shutdown(
        self,
        wait: bool = True,
    ) -> None:
        self.executor.shutdown(wait=wait)


job_queue = JobQueue()


def get_job_queue() -> JobQueue:
    return job_queue
