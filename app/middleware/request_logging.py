import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import Request


logger = logging.getLogger("web3_trust.request")


def api_key_fingerprint(
    api_key: str | None,
) -> str | None:
    """
    Return a short fingerprint without logging the raw API key.
    """
    if not api_key:
        return None

    return hashlib.sha256(
        api_key.encode("utf-8")
    ).hexdigest()[:12]


def write_request_log(
    request: Request,
    status_code: int,
    duration_ms: float,
) -> None:
    log_record = {
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
        "request_id": request.state.request_id,
        "method": request.method,
        "endpoint": request.url.path,
        "status_code": status_code,
        "duration_ms": round(duration_ms, 2),
        "api_key_hash": api_key_fingerprint(
            request.headers.get("X-API-Key")
        ),
    }

    logger.info(
        json.dumps(
            log_record,
            separators=(",", ":"),
        )
    )


async def request_logging_middleware(
    request: Request,
    call_next,
):
    request_id = uuid4().hex
    request.state.request_id = request_id

    started_at = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (
            time.perf_counter() - started_at
        ) * 1000

        write_request_log(
            request=request,
            status_code=500,
            duration_ms=duration_ms,
        )

        raise

    duration_ms = (
        time.perf_counter() - started_at
    ) * 1000

    response.headers["X-Request-ID"] = request_id

    write_request_log(
        request=request,
        status_code=response.status_code,
        duration_ms=duration_ms,
    )

    return response
