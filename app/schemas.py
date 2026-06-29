from typing import Optional

from pydantic import BaseModel


class WalletIngestRequest(BaseModel):
    address: str


class WalletResponse(BaseModel):
    id: int
    address: str
    last_seen_block: Optional[int] = None
