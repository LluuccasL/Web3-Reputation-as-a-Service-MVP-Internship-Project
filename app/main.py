from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .models import Wallet
from .schemas import WalletCreate, WalletResponse

Base.metadata.create_all(bind=engine)

app = FastAPI()


@app.get("/")
def root():
    return {"message": "Backend is running"}


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/wallets/ingest", response_model=WalletResponse)
def ingest_wallet(wallet: WalletCreate, db: Session = Depends(get_db)):
    existing_wallet = db.query(Wallet).filter(
        Wallet.wallet_address == wallet.wallet_address
    ).first()

    if existing_wallet:
        raise HTTPException(status_code=400, detail="Wallet already exists")

    new_wallet = Wallet(
        wallet_address=wallet.wallet_address,
        chain=wallet.chain
    )

    db.add(new_wallet)
    db.commit()
    db.refresh(new_wallet)

    return new_wallet