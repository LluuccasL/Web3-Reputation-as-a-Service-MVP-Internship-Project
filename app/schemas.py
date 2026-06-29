from pydantic import BaseModel


class WalletIngestRequest(BaseModel):
    address: str


class WalletIngestResponse(BaseModel):
    status: str
    address: str
    last_seen_block: int | None = None