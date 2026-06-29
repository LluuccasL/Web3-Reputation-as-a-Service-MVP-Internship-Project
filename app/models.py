from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from app.database import Base


class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(Integer, primary_key=True, index=True)
    address = Column(String, unique=True, index=True, nullable=False)
    last_seen_block = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
