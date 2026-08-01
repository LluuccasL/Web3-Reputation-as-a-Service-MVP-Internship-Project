from fastapi import Request
from fastapi.exception_handlers import (
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


WEEK3_API_PATHS = {
    "/check_wallet",
    "/generate_proof",
    "/sybil/analyze",
}


class APIError(Exception):
    """Controlled error returned by the external API."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        headers: dict[str, str] | None = None,
    ):
        super().__init__(message)

        self.status_code = status_code
        self.code = code
        self.message = message
        self.headers = headers or {}


def get_request_id(request: Request) -> str:
    return getattr(
        request.state,
        "request_id",
        "request-id-unavailable",
    )


async def api_error_handler(
    request: Request,
    exc: APIError,
) -> JSONResponse:
    """
    Return a consistent structured API error response.

    The detail field remains for compatibility with earlier clients.
    """
    return JSONResponse(
        status_code=exc.status_code,
        headers=exc.headers,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "request_id": get_request_id(request),
            },
            "detail": exc.message,
        },
    )


async def validation_error_handler(
    request: Request,
    exc: RequestValidationError,
):
    """
    Use structured errors for protected analysis endpoints while
    preserving FastAPI's original format for older wallet routes.
    """
    if request.url.path not in WEEK3_API_PATHS:
        return await request_validation_exception_handler(
            request,
            exc,
        )

    message = (
        "The request body contains invalid or missing fields."
    )

    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "INVALID_REQUEST",
                "message": message,
                "request_id": get_request_id(request),
            },
            "detail": message,
        },
    )
