from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException, status, Response, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.whatsapp_service import WhatsAppService

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp Integration"])


class WhatsAppStatusResponse(BaseModel):
    configured: bool
    provider: str
    api_version: str
    phone_number_id_set: bool
    business_account_id_set: bool
    webhook_verify_token_set: bool
    mode: str


class ReorderItemPreview(BaseModel):
    item_name: str
    current_stock: float
    min_threshold: float
    deficit: float
    unit: str
    status: str


class WhatsAppReorderPreviewResponse(BaseModel):
    message_text: str
    recipient_phone: Optional[str] = None
    items_count: int
    items: List[ReorderItemPreview]
    click_to_chat_url: str
    configured: bool


class WhatsAppSendRequest(BaseModel):
    recipient_phone: str = Field(..., min_length=10, description="Recipient phone number (e.g. 9876543210 or +919876543210)")
    message_text: str = Field(..., min_length=1, description="Message body to send via WhatsApp")
    reorder_reference: Optional[str] = Field(None, description="Optional supplier reference or order tag")


class WhatsAppSendResponse(BaseModel):
    success: bool
    status: str
    provider: Optional[str] = None
    message: Optional[str] = None
    message_id: Optional[str] = None
    recipient: str
    fallback_url: Optional[str] = None
    http_status: Optional[int] = None
    error: Optional[str] = None


@router.get("/status", response_model=WhatsAppStatusResponse, summary="Check WhatsApp Business API configuration")
def get_whatsapp_status():
    """Returns whether WhatsApp Cloud API credentials are configured in the backend environment."""
    return WhatsAppService.get_status()


@router.get("/preview/reorder", response_model=WhatsAppReorderPreviewResponse, summary="Preview supplier restock order message")
def preview_supplier_reorder(
    supplier_name: Optional[str] = Query(None, description="Name of the supplier"),
    supplier_phone: Optional[str] = Query(None, description="Mobile number of the supplier"),
    recipient_phone: Optional[str] = Query(None, description="Mobile number of the supplier (alias)"),
    db: Session = Depends(get_db)
):
    """
    Constructs an editable supplier reorder message from current live low-stock database items,
    along with a direct WhatsApp click-to-chat URL.
    """
    target_phone = supplier_phone or recipient_phone
    msg_text, items, fallback_url = WhatsAppService.generate_reorder_draft(db, supplier_name)
    clean_phone = WhatsAppService.clean_phone_number(target_phone) if target_phone else None
    if clean_phone:
        fallback_url = f"https://wa.me/{clean_phone}?text={quote_reorder(msg_text)}"

    return WhatsAppReorderPreviewResponse(
        message_text=msg_text,
        recipient_phone=clean_phone or target_phone,
        items_count=len(items),
        items=[ReorderItemPreview(**it) for it in items],
        click_to_chat_url=fallback_url,
        configured=WhatsAppService.is_configured()
    )


def quote_reorder(text: str) -> str:
    from urllib.parse import quote_plus
    return quote_plus(text)


@router.post("/send", response_model=WhatsAppSendResponse, summary="Send WhatsApp message via WhatsApp Cloud API")
def send_whatsapp_message(payload: WhatsAppSendRequest):
    """
    Send an approved supplier message or transaction notification via WhatsApp Business Platform Cloud API.
    If credentials are not configured, returns safe fallback instructions and direct click-to-chat link.
    """
    res = WhatsAppService.send_message(payload.recipient_phone, payload.message_text)
    return WhatsAppSendResponse(**res)


@router.get("/webhook", summary="Meta WhatsApp Webhook Verification")
def verify_webhook(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token")
):
    """Handles standard Meta webhook verification challenge."""
    if not hub_mode or not hub_verify_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing webhook parameters.")

    challenge = WhatsAppService.verify_webhook(hub_mode, hub_verify_token, hub_challenge or "")
    if challenge is not None:
        return Response(content=challenge, media_type="text/plain")

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verification token mismatch.")


@router.post("/webhook", summary="Meta WhatsApp Inbound & Status Webhook Receiver")
async def receive_webhook_payload(request: Request):
    """
    Receives incoming delivery status updates (sent, delivered, read, failed) from Meta.
    Validates payload format and responds with HTTP 200 OK as required by Meta.
    """
    try:
        body = await request.json()
        entries = body.get("entry", [])
        for entry in entries:
            changes = entry.get("changes", [])
            for change in changes:
                value = change.get("value", {})
                statuses = value.get("statuses", [])
                for st in statuses:
                    msg_id = st.get("id")
                    status_name = st.get("status")
                    recipient_id = st.get("recipient_id")
                    # Log event safely without leaking customer secrets
                    import logging
                    logging.getLogger("kirana.whatsapp").info(
                        f"Webhook status update: msg_id={msg_id}, status={status_name}, recipient={recipient_id}"
                    )
        return {"status": "received"}
    except Exception as ex:
        import logging
        logging.getLogger("kirana.whatsapp").warning(f"Malformed webhook payload received: {str(ex)}")
        return {"status": "received"}
