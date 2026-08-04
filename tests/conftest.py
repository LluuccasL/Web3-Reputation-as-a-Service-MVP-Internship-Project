import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.services.job_queue import get_job_queue


TEST_DATABASE_URL = "sqlite://"
TEST_API_KEY = "week3-test-api-key-that-is-not-used-in-production"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
)


class NoopJobQueue:
    def submit_unique(
        self,
        wallet_address,
        job_type,
        task,
    ):
        return "test-background-job", True


noop_job_queue = NoopJobQueue()


@pytest.fixture()
def client(monkeypatch):
    Base.metadata.create_all(bind=test_engine)

    monkeypatch.setenv(
        "API_KEYS",
        TEST_API_KEY,
    )

    def override_get_db():
        db = TestingSessionLocal()

        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_job_queue] = lambda: noop_job_queue

    with TestClient(app) as test_client:
        test_client.headers.update(
            {"X-API-Key": TEST_API_KEY}
        )

        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(autouse=True)
def reset_rate_limit_state():
    from app.middleware.rate_limit import rate_limiter

    rate_limiter.clear()

    yield

    rate_limiter.clear()


@pytest.fixture(autouse=True)
def reset_trust_cache():
    from app.routers.trust import clear_trust_cache

    clear_trust_cache()
    yield
    clear_trust_cache()
