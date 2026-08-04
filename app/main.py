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

app = FastAPI(
    title="Web3 Trust API",
    description=(
        "Proof-of-Human Trust API for wallet reputation scoring"
    ),
    version="0.4.0",
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


@app.get("/")
def root():
    return {"message": "Web3 Trust API is running"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}


app.add_middleware(ObservabilityMiddleware)

app.include_router(chain.router)
app.include_router(wallets.router)
app.include_router(trust.router)
app.include_router(sybil.router)
app.include_router(performance.router)
app.include_router(jobs.router)
