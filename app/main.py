from fastapi import FastAPI

from app.database import Base, engine
from app.routers import chain
from app.routers import wallets

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Web3 Trust API",
    description="Proof-of-Human Trust API for wallet reputation scoring",
    version="0.2.0",
)


@app.get("/")
def root():
    return {"message": "Web3 Trust API is running"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}


app.include_router(chain.router)
app.include_router(wallets.router)
