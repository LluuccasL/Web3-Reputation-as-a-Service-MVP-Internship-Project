import logging
import os

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from app.database import Base, engine
from app.errors import (
    APIError,
    api_error_handler,
    validation_error_handler,
)
from app.middleware.request_logging import (
    request_logging_middleware,
)
from app.middleware.observability import ObservabilityMiddleware
from app.routers import chain, jobs, performance, sybil, trust, wallets
from app.schemas import (
    APIStatusResponse,
    HealthResponse,
    VersionResponse,
)
from app.version import API_NAME, API_VERSION


log_level_name = os.getenv(
    "LOG_LEVEL",
    "INFO",
).upper()

log_level = getattr(
    logging,
    log_level_name,
    logging.INFO,
)

logging.basicConfig(
    level=log_level,
    format="%(message)s",
)

Base.metadata.create_all(bind=engine)

OPENAPI_TAGS = [
    {
        "name": "service",
        "description": "Service discovery, health, and version information.",
    },
    {
        "name": "chain",
        "description": "Current Ethereum provider information.",
    },
    {
        "name": "wallets",
        "description": "Wallet ingestion, retrieval, and base reputation.",
    },
    {
        "name": "trust",
        "description": "API-key-protected trust checks and signed proofs.",
    },
    {
        "name": "sybil",
        "description": "Relationship-based analysis of wallet groups.",
    },
    {
        "name": "background jobs",
        "description": "Asynchronous scoring and refresh workflows.",
    },
    {
        "name": "performance",
        "description": "Cache, request, and background-job metrics.",
    },
]


app = FastAPI(
    title=API_NAME,
    description=(
        "Developer-facing proof-of-human service for wallet reputation, "
        "behavior analysis, Sybil detection, and privacy-safe proofs. "
        "Use the synthetic demo catalog for deterministic evaluation."
    ),
    version=API_VERSION,
    openapi_tags=OPENAPI_TAGS,
    contact={
        "name": "Web3 Trust API project",
        "url": (
            "https://github.com/LluuccasL/"
            "Web3-Reputation-as-a-Service-MVP-Internship-Project"
        ),
    },
)

app.add_exception_handler(
    APIError,
    api_error_handler,
)

app.add_exception_handler(
    RequestValidationError,
    validation_error_handler,
)

app.middleware("http")(
    request_logging_middleware
)


@app.get(
    "/",
    response_model=APIStatusResponse,
    tags=["service"],
    summary="Confirm that the API is running",
)
def root() -> APIStatusResponse:
    return APIStatusResponse(
        message="Web3 Trust API is running"
    )


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["service"],
    summary="Check service health",
)
def health_check() -> HealthResponse:
    return HealthResponse(status="healthy")


@app.get(
    "/version",
    response_model=VersionResponse,
    tags=["service"],
    summary="Get the public API version",
)
def version() -> VersionResponse:
    return VersionResponse(
        name=API_NAME,
        version=API_VERSION,
    )


app.add_middleware(ObservabilityMiddleware)

app.include_router(chain.router)
app.include_router(wallets.router)
app.include_router(trust.router)
app.include_router(sybil.router)
app.include_router(performance.router)
app.include_router(jobs.router)
