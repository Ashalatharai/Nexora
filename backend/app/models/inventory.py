from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey
from app.database import Base


def utc_now():
    return datetime.now(timezone.utc)


# Explicit, maintainable alias mappings for common Indian kirana store variations
# Avoids dangerous fuzzy matching that could corrupt stock of similar items
ITEM_ALIASES = {
    "maggi noodles": "maggi",
    "maggi packet": "maggi",
    "maggi pkt": "maggi",
    "milk packet": "milk",
    "milk pkt": "milk",
    "rice bag": "rice",
    "rice bags": "rice",
    "cooking oil": "oil",
    "sunflower oil": "oil",
    "refined oil": "oil",
    "bath soap": "soap",
    "washing soap": "soap",
    "tea powder": "tea",
    "chai": "tea",
    "chai patti": "tea",
    "sugar kg": "sugar",
    "cheeni": "sugar",
    "shakkar": "sugar",
    "biscuits": "biscuit",
    "parle g": "biscuit",
}


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

    @property
    def is_out_of_stock(self) -> bool:
        return self.quantity <= 0.0


class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    item_id = Column(Integer, ForeignKey("inventory_items.id", ondelete="SET NULL"), nullable=True)
    item_name = Column(String(100), nullable=False, index=True)
    action = Column(String(30), nullable=False, index=True)  # sold, received, damaged, returned, reversal
    quantity = Column(Float, nullable=False)
    previous_stock = Column(Float, nullable=False)
    resulting_stock = Column(Float, nullable=False)
    note = Column(String(255), nullable=True)
    idempotency_key = Column(String(100), unique=True, nullable=True, index=True)
    is_reversed = Column(Boolean, nullable=False, default=False)
    timestamp = Column(DateTime(timezone=True), default=utc_now, index=True)
