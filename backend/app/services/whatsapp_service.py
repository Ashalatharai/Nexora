import json
import logging
import urllib.request
import urllib.error
from urllib.parse import quote_plus
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session

from app.config import (
    WHATSAPP_ACCESS_TOKEN,
    WHATSAPP_PHONE_NUMBER_ID,
    WHATSAPP_BUSINESS_ACCOUNT_ID,
    WHATSAPP_VERIFY_TOKEN,
    WHATSAPP_API_VERSION
)
from app.services.inventory_service import format_qty
from app.services.summary_service import SummaryService
from app.schemas.summary import StockStatus

logger = logging.getLogger("kirana.whatsapp")


class WhatsAppService:
    """
    Production-style integration with Meta WhatsApp Business Cloud API.
    Supports supplier reorder messaging, transaction alerts, and webhook status tracking.
    Gracefully degrades to click-to-chat fallback when credentials are not configured.
    """

    @classmethod
    def is_configured(cls) -> bool:
        """Return True if required Meta WhatsApp credentials are present in environment."""
        token = WHATSAPP_ACCESS_TOKEN.strip()
        phone_id = WHATSAPP_PHONE_NUMBER_ID.strip()
        return bool(token and phone_id and token != "your_whatsapp_system_user_access_token_here")

    @classmethod
    def get_status(cls) -> Dict[str, Any]:
        """Safe non-secret status summary for dashboard and health inspection."""
        configured = cls.is_configured()
        return {
            "configured": configured,
            "provider": "WhatsApp Business Platform (Cloud API)",
            "api_version": WHATSAPP_API_VERSION,
            "phone_number_id_set": bool(WHATSAPP_PHONE_NUMBER_ID),
            "business_account_id_set": bool(WHATSAPP_BUSINESS_ACCOUNT_ID),
            "webhook_verify_token_set": bool(WHATSAPP_VERIFY_TOKEN),
            "mode": "cloud_api" if configured else "fallback_click_to_chat"
        }

    @classmethod
    def clean_phone_number(cls, raw: Optional[str]) -> str:
        """
        Normalize mobile phone to E.164-compatible digits for WhatsApp.
        E.g. '+91 98765 43210' -> '919876543210'
             '9876543210'     -> '919876543210' (10-digit Indian standard)
        """
        if not raw:
            return ""
        digits = "".join(ch for ch in raw if ch.isdigit())
        if len(digits) == 10:
            return f"91{digits}"
        if len(digits) == 11 and digits.startswith("0"):
            return f"91{digits[1:]}"
        return digits

    @classmethod
    def generate_reorder_draft(cls, db: Session, supplier_name: Optional[str] = None) -> Tuple[str, list, str]:
        """
        Construct a professional Hindi/English supplier restock order message from live DB stock.
        Returns: (message_text, items_needing_reorder, click_to_chat_url)
        """
        low_items = SummaryService.get_low_stock_items(db)
        if not low_items:
            msg = "Namaste, all items are currently well-stocked at our store. No reorders needed right now."
            return msg, [], f"https://wa.me/?text={quote_plus(msg)}"

        supplier_header = f"Namaste {supplier_name}," if supplier_name else "Namaste,"
        lines = [
            f"{supplier_header} Please deliver the following stock urgently for our store:\n"
        ]

        item_list = []
        for it in low_items:
            deficit = max(1.0, it.deficit or (it.min_threshold - it.current_stock))
            status_tag = "OUT OF STOCK" if it.current_stock <= 0 else "LOW STOCK"
            lines.append(f"• {it.name}: {format_qty(deficit)} {it.unit} needed ({status_tag}, current: {format_qty(it.current_stock)})")
            item_list.append({
                "item_name": it.name,
                "current_stock": it.current_stock,
                "min_threshold": it.min_threshold,
                "deficit": deficit,
                "unit": it.unit,
                "status": status_tag
            })

        lines.append("\nPlease confirm delivery timing and pricing. Thank you!")
        message_text = "\n".join(lines)
        fallback_url = f"https://wa.me/?text={quote_plus(message_text)}"
        return message_text, item_list, fallback_url

    @classmethod
    def send_message(cls, recipient_phone: str, message_text: str) -> Dict[str, Any]:
        """
        Dispatch message via Meta WhatsApp Business Cloud API:
        POST https://graph.facebook.com/{version}/{phone_number_id}/messages
        """
        clean_phone = cls.clean_phone_number(recipient_phone)
        if not clean_phone or len(clean_phone) < 10:
            return {
                "success": False,
                "status": "invalid_recipient",
                "error": "A valid recipient phone number is required (at least 10 digits).",
                "recipient": recipient_phone
            }

        fallback_url = f"https://wa.me/{clean_phone}?text={quote_plus(message_text)}"

        # If credentials are not set, return graceful fallback instructions
        if not cls.is_configured():
            logger.info("WhatsApp Cloud API unconfigured. Returning fallback click-to-chat URL.")
            return {
                "success": False,
                "status": "unconfigured_fallback",
                "provider": "WhatsApp Business Platform",
                "message": "WhatsApp Cloud API credentials are not configured in environment. Use the fallback click-to-chat link.",
                "recipient": clean_phone,
                "message_preview": message_text,
                "fallback_url": fallback_url
            }

        url = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": clean_phone,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": message_text
            }
        }

        headers = {
            "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN.strip()}",
            "Content-Type": "application/json"
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=8.0) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                messages = resp_data.get("messages", [])
                message_id = messages[0].get("id") if messages else "sent"
                logger.info(f"WhatsApp Cloud API message accepted for {clean_phone}: id={message_id}")
                return {
                    "success": True,
                    "status": "accepted_by_provider",
                    "provider": "WhatsApp Business Platform (Cloud API)",
                    "message_id": message_id,
                    "recipient": clean_phone,
                    "http_status": resp.getcode(),
                    "message": "Message successfully dispatched via Meta WhatsApp Cloud API."
                }
        except urllib.error.HTTPError as he:
            err_body = he.read().decode("utf-8") if he.fp else str(he)
            logger.error(f"WhatsApp Cloud API HTTP error {he.code}: {err_body}")
            return {
                "success": False,
                "status": "api_error",
                "http_status": he.code,
                "recipient": clean_phone,
                "error": err_body,
                "fallback_url": fallback_url
            }
        except Exception as ex:
            logger.error(f"WhatsApp Cloud API dispatch exception: {str(ex)}")
            return {
                "success": False,
                "status": "dispatch_failed",
                "recipient": clean_phone,
                "error": str(ex),
                "fallback_url": fallback_url
            }

    @classmethod
    def verify_webhook(cls, mode: Optional[str], token: Optional[str], challenge: Optional[str]) -> Optional[str]:
        """Validate Meta webhook handshake."""
        if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
            return challenge or ""
        return None
