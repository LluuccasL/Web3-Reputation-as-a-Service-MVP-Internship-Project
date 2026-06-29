from fastapi import FastAPI

from app.database import Base, engine
from app.routers import wallets


Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Web3 Trust API",
    description="Proof-of-Human Trust API for wallet reputation scoring",
    version="0.1.0"
)


@app.get("/")
def root():
    return {"message": "Web3 Trust API is running"}


app.include_router(wallets.router)