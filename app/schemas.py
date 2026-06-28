from pydantic import BaseModel


class WalletCreate(BaseModel):
    wallet_address: str
    chain: str = "ethereum"


class WalletResponse(BaseModel):
    id: int
    wallet_address: str
    chain: str

    class Config:
        from_attributes = True