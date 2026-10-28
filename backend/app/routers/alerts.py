from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.summary import LowStockResponse, SupplierReorderResponse
from app.services.summary_service import SummaryService

router = APIRouter(tags=["Alerts & Supplier"])


@router.get("/alerts/low-stock", response_model=LowStockResponse, summary="Get low stock alerts")
def get_low_stock_alerts(db: Session = Depends(get_db)):
    """
    Fetch all items with current stock at or below minimum threshold.
    Includes formatted supplier reorder draft and WhatsApp click-to-chat URL.
    """
    low_items = SummaryService.get_low_stock_items(db)
    reorder = SummaryService.generate_supplier_reorder(db)

    return LowStockResponse(
        total_low_stock=len(low_items),
        items=low_items,
        supplier_message=reorder.message_text,
        whatsapp_url=reorder.whatsapp_url
    )


@router.get("/supplier/reorder", response_model=SupplierReorderResponse, summary="Generate supplier WhatsApp reorder link")
def get_supplier_reorder(
    phone: Optional[str] = Query(None, description="Optional supplier phone number with country code, e.g. 919876543210"),
    db: Session = Depends(get_db)
):
    """
    Generate URL-encoded WhatsApp click-to-chat link for all items needing reordering.
    Leaves phone number unpopulated if not provided.
    """
    return SummaryService.generate_supplier_reorder(db, phone_number=phone)
