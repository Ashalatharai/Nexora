from typing import List, Dict, Any, Optional
from pydantic import BaseModel


class LowStockItem(BaseModel):
    id: int
    name: str
    current_stock: float
    min_threshold: float
    unit: str
    deficit: float


class LowStockResponse(BaseModel):
    total_low_stock: int
    items: List[LowStockItem]
    supplier_message: str
    whatsapp_url: str


class ActionGroupSummary(BaseModel):
    item_name: str
    total_quantity: float
    unit: str
    transactions_count: int


class CreditDaySummary(BaseModel):
    total_credit_purchases_amount: float
    total_payments_received_amount: float
    transactions_count: int


class StockItemOverview(BaseModel):
    name: str
    quantity: float
    unit: str
    price: float
    is_low_stock: bool


class DailySummaryResponse(BaseModel):
    date: str
    total_inventory_actions: int
    items_sold: List[ActionGroupSummary]
    items_received: List[ActionGroupSummary]
    items_damaged: List[ActionGroupSummary]
    items_returned: List[ActionGroupSummary]
    current_stock_overview: List[StockItemOverview]
    credit_summary: CreditDaySummary


class SupplierReorderResponse(BaseModel):
    supplier_phone: Optional[str] = None
    items_count: int
    items: List[LowStockItem]
    message_text: str
    whatsapp_url: str
