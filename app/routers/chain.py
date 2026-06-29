from fastapi import APIRouter, HTTPException

from app.services.blockchain import get_latest_block_number


router = APIRouter(
    prefix="/chain",
    tags=["chain"]
)


@router.get("/latest-block")
def latest_block():
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
