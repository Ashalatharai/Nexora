from enum import Enum
from typing import List, Optional
from pydantic import BaseModel


class StockStatus(str, Enum):
    OUT_OF_STOCK = "out_of_stock"  # 0 units remaining
    LOW_STOCK = "low_stock"        # 0 < stock <= min_threshold


class LowStockItem(BaseModel):
    id: int
    name: str
    current_stock: float
    min_threshold: float
    unit: str
    deficit: float
    status: StockStatus


class LowStockResponse(BaseModel):
    total_alerts: int
    total_out_of_stock: int
    total_low_stock: int
    items: List[LowStockItem]
    supplier_message: str
    whatsapp_url: str


class ActionGroupSummary(BaseModel):
    item_name: str
    total_quantity: float
    unit: str
    transactions_count: int
    estimated_value_inr: float = 0.0


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
    is_out_of_stock: bool


class DailySummaryResponse(BaseModel):
    date: str
    total_inventory_actions: int
    gross_sales_value_inr: float
    items_sold: List[ActionGroupSummary]
    items_received: List[ActionGroupSummary]
    items_damaged: List[ActionGroupSummary]
    items_returned: List[ActionGroupSummary]
    current_stock_overview: List[StockItemOverview]
    credit_summary: CreditDaySummary
    accounting_note: str


class SupplierReorderResponse(BaseModel):
    supplier_phone: Optional[str] = None
    items_count: int
    out_of_stock_count: int
    low_stock_count: int
    items: List[LowStockItem]
    message_text: str
    whatsapp_url: str
