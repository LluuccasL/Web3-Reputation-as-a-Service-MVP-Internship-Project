from datetime import datetime
from typing import Any

from pydantic import BaseModel


class WalletIngestRequest(BaseModel):
    address: str


class WalletIngestResponse(BaseModel):
    status: str
    address: str
    last_seen_block: int | None = None


class WalletResponse(BaseModel):
    id: int
    address: str
    source: str
    last_seen_block: int | None = None
    created_at: datetime | None = None


class WalletBalanceResponse(BaseModel):
    address: str
    balance_wei: str
    balance_eth: str
    network: str


class WalletTransfersResponse(BaseModel):
    address: str
    count: int
    transfers: list[dict[str, Any]]


class WalletReputationResponse(BaseModel):
    address: str
    score: int
    level: str
    signals: dict[str, Any]
