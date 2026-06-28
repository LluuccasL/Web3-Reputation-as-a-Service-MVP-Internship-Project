from fastapi import FastAPI
from app.routers import wallets

app = FastAPI(
    title="Web3 Reputation API",
    description="Proof-of-Human Trust API for wallet reputation scoring",
    version="0.1.0"
)

app.include_router(wallets.router)

@app.get("/")
def root():
    return {
        "message": "Web3 Reputation API is running"
    }

@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }