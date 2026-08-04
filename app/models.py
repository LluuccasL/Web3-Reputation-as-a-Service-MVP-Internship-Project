from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Integer, String, Text

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


class BackgroundJob(Base):
    __tablename__ = "background_jobs"

    id = Column(String(36), primary_key=True, index=True)
    wallet_address = Column(String, index=True, nullable=False)
    job_type = Column(String, index=True, nullable=False)
    status = Column(String, index=True, nullable=False, default="queued")
    attempts = Column(Integer, nullable=False, default=0)
    result = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)


class WalletScore(Base):
    __tablename__ = "wallet_scores"

    wallet_address = Column(String, primary_key=True, index=True)
    job_id = Column(String(36), nullable=False)
    result = Column(JSON, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
