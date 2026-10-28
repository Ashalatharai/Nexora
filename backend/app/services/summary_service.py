from datetime import datetime, timezone, time, date
import urllib.parse
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.inventory import InventoryItem, InventoryTransaction
from app.models.credit import CreditTransaction
from app.schemas.summary import (
    StockStatus,
    LowStockItem,
    DailySummaryResponse,
    ActionGroupSummary,
    StockItemOverview,
    CreditDaySummary,
    SupplierReorderResponse
)


def normalize_indian_phone(phone: Optional[str]) -> Optional[str]:
    """Clean phone number into international WhatsApp standard (e.g. 919876543210)."""
    if not phone:
        return None
    digits = "".join(filter(str.isdigit, phone))
    if not digits:
        return None
    if len(digits) == 10:
        return f"91{digits}"
    if len(digits) == 11 and digits.startswith("0"):
        return f"91{digits[1:]}"
    return digits


class SummaryService:
    @staticmethod
    def get_low_stock_items(db: Session) -> List[LowStockItem]:
        """
        Fetch all items whose stock is less than or equal to their minimum threshold.
        Distinguishes between OUT_OF_STOCK (0 stock) and LOW_STOCK (0 < stock <= threshold).
        """
        items = db.query(InventoryItem).filter(InventoryItem.quantity <= InventoryItem.min_threshold).all()
        results: List[LowStockItem] = []
        for it in items:
            deficit = max(0.0, round(it.min_threshold - it.quantity, 2))
            status = StockStatus.OUT_OF_STOCK if it.quantity <= 0.0 else StockStatus.LOW_STOCK
            results.append(
                LowStockItem(
                    id=it.id,
                    name=it.name.title(),
                    current_stock=it.quantity,
                    min_threshold=it.min_threshold,
                    unit=it.unit,
                    deficit=deficit,
                    status=status
                )
            )
        # Order by out-of-stock first, then largest deficit
        return sorted(results, key=lambda x: (0 if x.status == StockStatus.OUT_OF_STOCK else 1, -x.deficit))

    @staticmethod
    def generate_supplier_reorder(
        db: Session,
        phone_number: Optional[str] = None
    ) -> SupplierReorderResponse:
        """
        Generate a ready-to-send supplier order message and WhatsApp click-to-chat URL.
        Never fabricates phone numbers; leaves destination blank if not supplied.
        Categorizes items by urgency: OUT OF STOCK first, followed by LOW STOCK.
        """
        items = SummaryService.get_low_stock_items(db)
        out_of_stock = [i for i in items if i.status == StockStatus.OUT_OF_STOCK]
        low_stock = [i for i in items if i.status == StockStatus.LOW_STOCK]

        if not items:
            message_text = "Namaste! All kirana inventory levels are healthy. No items need reordering today."
        else:
            lines = [
                "Namaste, please deliver the following items for my Kirana shop:",
                ""
            ]

            if out_of_stock:
                lines.append("🚨 *URGENT - COMPLETELY OUT OF STOCK:*")
                for it in out_of_stock:
                    suggested = max(it.min_threshold * 2, 10.0)
                    lines.append(f"• {it.name}: 0 {it.unit} remaining! (Need {suggested:g} {it.unit})")
                lines.append("")

            if low_stock:
                lines.append("⚠️ *LOW STOCK - REFILL NEEDED:*")
                for it in low_stock:
                    suggested = max(it.deficit * 2, 5.0)
                    lines.append(
                        f"• {it.name}: {it.current_stock:g} {it.unit} left (Min: {it.min_threshold:g} {it.unit}, Need: {suggested:g} {it.unit})"
                    )
                lines.append("")

            lines.append("Please confirm dispatch and expected delivery time. Thank you!")
            message_text = "\n".join(lines)

        encoded_text = urllib.parse.quote(message_text)

        clean_phone = normalize_indian_phone(phone_number)
        if clean_phone:
            whatsapp_url = f"https://wa.me/{clean_phone}?text={encoded_text}"
        else:
            whatsapp_url = f"https://wa.me/?text={encoded_text}"

        return SupplierReorderResponse(
            supplier_phone=clean_phone,
            items_count=len(items),
            out_of_stock_count=len(out_of_stock),
            low_stock_count=len(low_stock),
            items=items,
            message_text=message_text,
            whatsapp_url=whatsapp_url
        )

    @staticmethod
    def get_daily_summary(db: Session, target_date: Optional[date] = None) -> DailySummaryResponse:
        """
        Produce end-of-day summary with accurate retail accounting:
        - Items sold, received, damaged, returned
        - Gross sales value in INR (calculated from unit prices)
        - Current stock overview
        - Credit summary (udhaar taken vs payments collected)
        - Clear accounting note distinguishing revenue from debt recovery
        """
        if target_date is None:
            target_date = datetime.now(timezone.utc).date()

        start_dt = datetime.combine(target_date, time.min).replace(tzinfo=timezone.utc)
        end_dt = datetime.combine(target_date, time.max).replace(tzinfo=timezone.utc)

        # Inventory transactions for the day
        inv_txs = (
            db.query(InventoryTransaction)
            .filter(InventoryTransaction.timestamp >= start_dt, InventoryTransaction.timestamp <= end_dt)
            .all()
        )

        def group_by_action(action_name: str) -> List[ActionGroupSummary]:
            matching = [t for t in inv_txs if t.action.lower() == action_name.lower()]
            item_totals = {}
            for t in matching:
                item_totals[t.item_name] = item_totals.get(t.item_name, 0.0) + t.quantity

            result = []
            for item_name, total_qty in item_totals.items():
                item = db.query(InventoryItem).filter(InventoryItem.name == item_name).first()
                unit = item.unit if item else "pcs"
                price = item.price if item else 0.0
                count = sum(1 for t in matching if t.item_name == item_name)
                val = round(total_qty * price, 2)
                result.append(
                    ActionGroupSummary(
                        item_name=item_name.title(),
                        total_quantity=round(total_qty, 2),
                        unit=unit,
                        transactions_count=count,
                        estimated_value_inr=val
                    )
                )
            return sorted(result, key=lambda x: x.item_name)

        sold_list = group_by_action("sold")
        received_list = group_by_action("received")
        damaged_list = group_by_action("damaged")
        returned_list = group_by_action("returned")

        gross_sales_val = round(sum(s.estimated_value_inr for s in sold_list), 2)

        # Current stock overview of all items
        all_items = db.query(InventoryItem).order_by(InventoryItem.name.asc()).all()
        overview = [
            StockItemOverview(
                name=it.name.title(),
                quantity=it.quantity,
                unit=it.unit,
                price=it.price,
                is_low_stock=it.is_low_stock,
                is_out_of_stock=it.is_out_of_stock
            )
            for it in all_items
        ]

        # Credit transactions for the day
        credit_txs = (
            db.query(CreditTransaction)
            .filter(CreditTransaction.timestamp >= start_dt, CreditTransaction.timestamp <= end_dt)
            .all()
        )
        credit_purchases = sum(t.amount for t in credit_txs if t.action in ["credit_purchase", "credit_sale_item"])
        payments_collected = sum(t.amount for t in credit_txs if t.action == "payment")

        credit_summary = CreditDaySummary(
            total_credit_purchases_amount=round(credit_purchases, 2),
            total_payments_received_amount=round(payments_collected, 2),
            transactions_count=len(credit_txs)
        )

        accounting_note = (
            f"Gross sales value today is ₹{gross_sales_val:g}. "
            f"Udhaar payments collected (₹{payments_collected:g}) represent debt settlements, "
            f"not new sales revenue. Net Udhaar change today: ₹{round(credit_purchases - payments_collected, 2):g}."
        )

        return DailySummaryResponse(
            date=target_date.isoformat(),
            total_inventory_actions=len(inv_txs),
            gross_sales_value_inr=gross_sales_val,
            items_sold=sold_list,
            items_received=received_list,
            items_damaged=damaged_list,
            items_returned=returned_list,
            current_stock_overview=overview,
            credit_summary=credit_summary,
            accounting_note=accounting_note
        )
