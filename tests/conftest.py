import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


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
