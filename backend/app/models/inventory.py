from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime
from app.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    quantity = Column(Float, nullable=False, default=0.0)
    unit = Column(String(30), nullable=False, default="pcs")
    price = Column(Float, nullable=False, default=0.0)
    min_threshold = Column(Float, nullable=False, default=5.0)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    @property
    def is_low_stock(self) -> bool:
        return self.quantity <= self.min_threshold


class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    item_name = Column(String(100), nullable=False, index=True)
    action = Column(String(30), nullable=False, index=True)  # sold, received, damaged, returned
    quantity = Column(Float, nullable=False)
    previous_stock = Column(Float, nullable=False)
    resulting_stock = Column(Float, nullable=False)
    note = Column(String(255), nullable=True)
    timestamp = Column(DateTime(timezone=True), default=utc_now, index=True)
