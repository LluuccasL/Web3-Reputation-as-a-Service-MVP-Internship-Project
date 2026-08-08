from fastapi import APIRouter, HTTPException

from app.schemas import LatestBlockResponse
from app.services.blockchain import get_latest_block_number


router = APIRouter(
    prefix="/chain",
    tags=["chain"]
)


@router.get(
    "/latest-block",
    response_model=LatestBlockResponse,
    summary="Get the latest Ethereum block",
    description=(
        "Returns the latest block number reported by the configured "
        "blockchain provider."
    ),
)
def latest_block() -> LatestBlockResponse:
    try:
        block_number = get_latest_block_number()
        return {
            "latest_block": block_number
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch latest block: {str(e)}"
        )
