from enum import Enum
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict


class InventoryAction(str, Enum):
    SOLD = "sold"
    RECEIVED = "received"
    DAMAGED = "damaged"
    RETURNED = "returned"


class InventoryItemBase(BaseModel):
    name: str = Field(..., min_length=1, description="Item name")
    quantity: float = Field(default=0.0, ge=0.0, description="Available stock quantity")
    unit: str = Field(default="pcs", description="Unit of measurement (pkt, bag, kg, litre, etc.)")
    price: float = Field(default=0.0, ge=0.0, description="Selling price per unit in INR")
    min_threshold: float = Field(default=5.0, ge=0.0, description="Minimum stock threshold for alerts")

    @field_validator("name")
    @classmethod
    def normalize_name(cls, v: str) -> str:
        return v.strip().lower()


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
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SingleItemAction(BaseModel):
    action: InventoryAction = Field(..., description="Action to perform: sold, received, damaged, returned")
    item_name: str = Field(..., min_length=1, description="Item name (case-insensitive)")
    quantity: float = Field(..., gt=0.0, description="Quantity for this action (must be > 0)")

    @field_validator("item_name")
    @classmethod
    def clean_item_name(cls, v: str) -> str:
        return v.strip().lower()


class InventoryTransactionRequest(BaseModel):
    items: List[SingleItemAction] = Field(..., min_length=1, description="List of items to update atomically")
    note: Optional[str] = Field(None, description="Optional note for the transaction")


class ItemUpdateResult(BaseModel):
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
