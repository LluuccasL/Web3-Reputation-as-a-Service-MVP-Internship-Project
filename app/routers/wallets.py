from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Wallet
from app.schemas import WalletIngestRequest, WalletIngestResponse
from app.services.blockchain import get_latest_block_number


router = APIRouter(
    prefix="/wallets",
    tags=["wallets"]
)


def is_valid_eth_address(address: str) -> bool:
    return (
        isinstance(address, str)
        and address.startswith("0x")
        and len(address) == 42
    )


@router.post("/ingest", response_model=WalletIngestResponse)
def ingest_wallet(payload: WalletIngestRequest, db: Session = Depends(get_db)):
    address = payload.address.lower().strip()

    if not is_valid_eth_address(address):
        raise HTTPException(
            status_code=400,
            detail="Invalid Ethereum wallet address. Address must start with 0x and be 42 characters long."
        )

    try:
        latest_block = get_latest_block_number()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch latest block from Alchemy: {str(e)}"
        )

    existing_wallet = (
        db.query(Wallet)
        .filter(Wallet.wallet_address == address)
        .first()
    )

    if existing_wallet:
        existing_wallet.last_seen_block = latest_block
        db.commit()
        db.refresh(existing_wallet)

        return {
            "status": "already_exists",
            "address": existing_wallet.wallet_address,
            "last_seen_block": existing_wallet.last_seen_block
        }

    new_wallet = Wallet(
        wallet_address=address,
        source="alchemy",
        last_seen_block=latest_block
    )

    db.add(new_wallet)
    db.commit()
    db.refresh(new_wallet)

    return {
        "status": "ingested",
        "address": new_wallet.wallet_address,
        "last_seen_block": new_wallet.last_seen_block
    }