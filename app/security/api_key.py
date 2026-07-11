import os
import secrets

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader


API_KEY_HEADER_NAME = "X-API-Key"

api_key_header = APIKeyHeader(
    name=API_KEY_HEADER_NAME,
    scheme_name="Developer API Key",
    description="API key required for protected trust and proof endpoints.",
    auto_error=False,
)


def get_configured_api_keys() -> list[str]:
    """
    Read comma-separated API keys from the API_KEYS environment variable.
    """
    raw_api_keys = os.getenv("API_KEYS", "")

    api_keys = [
        key.strip()
        for key in raw_api_keys.split(",")
        if key.strip()
    ]

    if not api_keys:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API key authentication is not configured.",
        )

    return api_keys


def require_api_key(
    supplied_api_key: str | None = Security(api_key_header),
) -> str:
    """
    Require a valid X-API-Key request header.
    """
    if not supplied_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
        )

    configured_api_keys = get_configured_api_keys()

    for configured_key in configured_api_keys:
        if secrets.compare_digest(
            supplied_api_key,
            configured_key,
        ):
            return supplied_api_key

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API key.",
    )
