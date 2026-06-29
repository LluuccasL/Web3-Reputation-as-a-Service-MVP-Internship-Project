from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app.models import Wallet
from app.schemas import WalletIngestRequest, WalletResponse
from app.services.blockchain import (
    BlockchainServiceError,
    get_latest_block_number,
    is_valid_eth_address,
    normalize_address,
)

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Web3 Trust API",
    description="Proof-of-Human Trust API backend",
    version="0.1.0"
)


@app.get("/")
def root():
    return {
        "message": "Web3 Trust API is running"
    }


@app.get("/health")
def health_check():
    return {
        "status": "ok"
    }


@app.get("/chain/latest-block")
def latest_block():
    try:
        block_number = get_latest_block_number()

    except BlockchainServiceError as error:
        raise HTTPException(
            status_code=502,
            detail=str(error)
        )

    return {
        "latest_block": block_number
    }


@app.post("/wallets/ingest", response_model=WalletResponse)
def ingest_wallet(
    payload: WalletIngestRequest,
    db: Session = Depends(get_db)
):
    if not is_valid_eth_address(payload.address):
        raise HTTPException(
            status_code=400,
            detail="Invalid Ethereum wallet address"
        )

    address = normalize_address(payload.address)

    try:
        latest_block = get_latest_block_number()

    except BlockchainServiceError as error:
        raise HTTPException(
            status_code=502,
            detail=str(error)
        )

    wallet = db.query(Wallet).filter(Wallet.address == address).first()

    if wallet:
        wallet.last_seen_block = latest_block

    else:
        wallet = Wallet(
            address=address,
            last_seen_block=latest_block
        )
        db.add(wallet)

    db.commit()
    db.refresh(wallet)

    return {
        "id": wallet.id,
        "address": wallet.address,
        "last_seen_block": wallet.last_seen_block
    }
