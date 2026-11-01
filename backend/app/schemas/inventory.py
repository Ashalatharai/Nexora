from enum import Enum
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict
from app.models.inventory import ITEM_ALIASES


class InventoryAction(str, Enum):
    SOLD = "sold"
    RECEIVED = "received"
    DAMAGED = "damaged"
    RETURNED = "returned"  # Restockable customer return added back to sellable stock
    REVERSAL = "reversal"  # Compensating audit reversal of an earlier transaction


class InventoryItemBase(BaseModel):
    name: str = Field(..., min_length=1, description="Item name")
    quantity: float = Field(default=0.0, ge=0.0, description="Available stock quantity")
    unit: str = Field(default="pcs", description="Unit of measurement (pkt, bag, kg, litre, etc.)")
    price: float = Field(default=0.0, ge=0.0, description="Selling price per unit in INR")
    min_threshold: float = Field(default=5.0, ge=0.0, description="Minimum stock threshold for alerts")

    @field_validator("name")
    @classmethod
    def normalize_name(cls, v: str) -> str:
        clean = v.strip().lower()
        return ITEM_ALIASES.get(clean, clean)


class InventoryItemCreate(InventoryItemBase):
    pass


class InventoryItemUpdate(BaseModel):
    quantity: Optional[float] = Field(None, ge=0.0)
    unit: Optional[str] = None
    price: Optional[float] = Field(None, ge=0.0)
    min_threshold: Optional[float] = Field(None, ge=0.0)


class InventoryItemResponse(InventoryItemBase):
    id: int
    is_low_stock: bool
    is_out_of_stock: bool
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SingleItemAction(BaseModel):
    action: InventoryAction = Field(..., description="Action: sold, received, damaged, returned")
    item_name: str = Field(..., min_length=1, description="Item name or common alias")
    quantity: float = Field(..., gt=0.0, description="Quantity for this action (must be > 0)")

    @field_validator("item_name")
    @classmethod
    def clean_item_name(cls, v: str) -> str:
        clean = v.strip().lower()
        return ITEM_ALIASES.get(clean, clean)


class InventoryTransactionRequest(BaseModel):
    items: List[SingleItemAction] = Field(..., min_length=1, description="List of items to update atomically")
    note: Optional[str] = Field(None, description="Optional note or reference")
    idempotency_key: Optional[str] = Field(None, description="Optional unique key to prevent accidental duplicate submission on network retries")


class ItemUpdateResult(BaseModel):
    item_id: Optional[int] = None
    item_name: str
    action: str
    quantity: float
    previous_stock: float
    resulting_stock: float
    unit: str


class InventoryTransactionResponse(BaseModel):
    success: bool
    confirmation: str
    updates: List[ItemUpdateResult]
    low_stock_alerts: List[str] = []
    is_duplicate_replay: bool = False


class TransactionReversalRequest(BaseModel):
    reason: Optional[str] = Field("Correcting erroneous entry", description="Auditable reason for transaction reversal")


class TransactionReversalResponse(BaseModel):
    success: bool
    message: str
    reversed_transaction_id: int
    compensating_transaction_id: int
    item_name: str
    restored_stock: float
    unit: str
