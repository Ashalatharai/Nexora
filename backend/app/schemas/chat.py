from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
from app.schemas.inventory import ItemUpdateResult
from app.schemas.credit import CreditTransactionResponse


class ActionDomain(str, Enum):
    INVENTORY = "inventory"
    CREDIT = "credit"


class ChatStructuredAction(BaseModel):
    """Minimal contract for pre-parsed actions from message-parser module."""
    domain: ActionDomain = Field(default=ActionDomain.INVENTORY, description="Domain: 'inventory' or 'credit'")
    action: str = Field(..., description="Action: sold, received, damaged, returned, credit_purchase, payment")
    item_name: Optional[str] = Field(None, description="Item name (for inventory operations)")
    quantity: Optional[float] = Field(None, description="Quantity (for inventory operations)")
    customer_name: Optional[str] = Field(None, description="Customer name (for credit operations)")
    amount: Optional[float] = Field(None, description="Amount in INR (for credit operations)")
    unit: Optional[str] = Field(None, description="Optional unit")


class ChatRequest(BaseModel):
    """
    Unified chat request:
    - If `actions` is provided (by message-parser teammate), it executes directly.
    - If `message` is provided without `actions`, the built-in parser decodes it.
    """
    message: Optional[str] = Field(None, description="Raw text typed by shopkeeper, e.g. 'sold 3 maggi, 2 milk'")
    actions: Optional[List[ChatStructuredAction]] = Field(None, description="Structured actions supplied by message-parser")


class ChatResponse(BaseModel):
    success: bool
    reply: str
    intent: str
    parsed_actions: List[ChatStructuredAction] = []
    inventory_updates: List[ItemUpdateResult] = []
    credit_update: Optional[CreditTransactionResponse] = None
    low_stock_alerts: List[str] = []
