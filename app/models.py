from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime

from app.database import Base


class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(Integer, primary_key=True, index=True)
    wallet_address = Column(String, unique=True, index=True, nullable=False)
    source = Column(String, default="alchemy")
    last_seen_block = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)