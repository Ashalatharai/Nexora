from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class ChatRequest(BaseModel):
    message: str = Field(..., description="Shopkeeper's chat input")
    session_id: Optional[str] = Field("default", description="Session identifier for conversation memory")

class ChatResponse(BaseModel):
    reply: str
    action_taken: str = "none"
    action_details: Optional[Dict[str, Any]] = None
    clarification_needed: bool = False
    store_state: Optional[Dict[str, Any]] = None

class ProductCreate(BaseModel):
    name: str
    category: str = "Grocery"
    price: float
    cost_price: Optional[float] = 0.0
    stock: int
    min_stock: Optional[int] = 10
    unit: Optional[str] = "packet"

class CustomerCreate(BaseModel):
    name: str
    phone: Optional[str] = ""

class PaymentCreate(BaseModel):
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    amount: float
    notes: Optional[str] = ""

class StockAdjust(BaseModel):
    product_id: str
    adjustment: int

