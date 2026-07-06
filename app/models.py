from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String

from app.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(Integer, primary_key=True, index=True)
    wallet_address = Column(String, unique=True, index=True, nullable=False)
    source = Column(String, default="alchemy")
    last_seen_block = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    wallet_address = Column(String, index=True, nullable=False)
    tx_hash = Column(String, index=True, nullable=False)
    direction = Column(String, nullable=True)
    asset = Column(String, nullable=True)
    value = Column(String, nullable=True)
    category = Column(String, nullable=True)
    block_num = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
