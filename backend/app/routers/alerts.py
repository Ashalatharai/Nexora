from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.summary import LowStockResponse, SupplierReorderResponse, StockStatus
from app.services.summary_service import SummaryService

router = APIRouter(tags=["Alerts & Supplier"])


@router.get("/alerts/low-stock", response_model=LowStockResponse, summary="Get low and out-of-stock alerts")
def get_low_stock_alerts(db: Session = Depends(get_db)):
    """
    Fetch all items with current stock at or below minimum threshold.
    Categorizes items into OUT_OF_STOCK (0 units) vs LOW_STOCK.
    Includes formatted supplier reorder draft and WhatsApp click-to-chat URL.
    """
    items = SummaryService.get_low_stock_items(db)
    reorder = SummaryService.generate_supplier_reorder(db)

    out_of_stock_count = sum(1 for i in items if i.status == StockStatus.OUT_OF_STOCK)
    low_stock_count = sum(1 for i in items if i.status == StockStatus.LOW_STOCK)

    return LowStockResponse(
        total_alerts=len(items),
        total_out_of_stock=out_of_stock_count,
        total_low_stock=low_stock_count,
        items=items,
        supplier_message=reorder.message_text,
        whatsapp_url=reorder.whatsapp_url
    )


@router.get("/supplier/reorder", response_model=SupplierReorderResponse, summary="Generate supplier WhatsApp reorder link")
def get_supplier_reorder(
    phone: Optional[str] = Query(None, description="Optional supplier phone number (e.g. 9876543210 or 919876543210)"),
    db: Session = Depends(get_db)
):
    """
    Generate URL-encoded WhatsApp click-to-chat link for all items needing reordering.
    Leaves phone number unpopulated if not provided.
    Normalizes 10-digit Indian phone numbers into international WhatsApp format.
    """
    return SummaryService.generate_supplier_reorder(db, phone_number=phone)
