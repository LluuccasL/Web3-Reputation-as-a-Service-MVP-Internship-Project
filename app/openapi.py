"""Reusable OpenAPI response documentation."""

from typing import Any

from app.schemas import ErrorResponse


STANDARD_HEADERS = {
    "X-Request-ID": {
        "description": "Identifier used to correlate logs for this request.",
        "schema": {"type": "string"},
    },
}

PROTECTED_HEADERS = {
    **STANDARD_HEADERS,
    "X-RateLimit-Limit": {
        "description": "Maximum requests allowed in the current window.",
        "schema": {"type": "integer"},
    },
    "X-RateLimit-Remaining": {
        "description": "Requests remaining in the current window.",
        "schema": {"type": "integer"},
    },
    "X-RateLimit-Reset": {
        "description": "Seconds until the current rate-limit window resets.",
        "schema": {"type": "integer"},
    },
}

TRUST_HEADERS = {
    **PROTECTED_HEADERS,
    "X-Trust-Cache": {
        "description": "Trust-cache result: HIT, MISS, or STALE.",
        "schema": {
            "type": "string",
            "enum": ["HIT", "MISS", "STALE"],
        },
    },
    "X-Processing-Time-Ms": {
        "description": "Trust calculation time in milliseconds.",
        "schema": {"type": "number", "format": "float"},
    },
}


def protected_responses(
    *,
    success_status: int = 200,
    success_description: str = "Successful response.",
    success_headers: dict[str, Any] | None = None,
    include_not_found: bool = False,
    include_provider_failure: bool = False,
) -> dict[int, dict[str, Any]]:
    """Build consistent response docs for API-key-protected routes."""
    responses: dict[int, dict[str, Any]] = {
        success_status: {
            "description": success_description,
            "headers": success_headers or PROTECTED_HEADERS,
        },
        401: {
            "model": ErrorResponse,
            "description": "Invalid or missing API key.",
        },
        422: {
            "model": ErrorResponse,
            "description": "Invalid request input.",
        },
        429: {
            "model": ErrorResponse,
            "description": "Rate limit exceeded.",
        },
        500: {
            "model": ErrorResponse,
            "description": "Internal service error.",
        },
    }

    if include_not_found:
        responses[404] = {
            "model": ErrorResponse,
            "description": "Requested resource was not found.",
        }

    if include_provider_failure:
        responses[503] = {
            "model": ErrorResponse,
            "description": "Blockchain provider temporarily unavailable.",
        }

    return responses
