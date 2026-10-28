from datetime import datetime, timezone, time, date
import urllib.parse
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.inventory import InventoryItem, InventoryTransaction
from app.models.credit import CreditTransaction
from app.schemas.summary import (
    LowStockItem,
    LowStockResponse,
    DailySummaryResponse,
    ActionGroupSummary,
    StockItemOverview,
    CreditDaySummary,
    SupplierReorderResponse
)


class SummaryService:
    @staticmethod
    def get_low_stock_items(db: Session) -> List[LowStockItem]:
        """Fetch all items whose stock is less than or equal to their minimum threshold."""
        items = db.query(InventoryItem).filter(InventoryItem.quantity <= InventoryItem.min_threshold).all()
        results: List[LowStockItem] = []
        for it in items:
            deficit = max(0.0, round(it.min_threshold - it.quantity, 2))
            results.append(
                LowStockItem(
                    id=it.id,
                    name=it.name.title(),
                    current_stock=it.quantity,
                    min_threshold=it.min_threshold,
                    unit=it.unit,
                    deficit=deficit
                )
            )
        return results

    @staticmethod
    def generate_supplier_reorder(
        db: Session,
        phone_number: Optional[str] = None
    ) -> SupplierReorderResponse:
        """
        Generate a ready-to-send supplier order message and WhatsApp click-to-chat URL.
        Never fabricates phone numbers; leaves destination blank if not supplied.
        """
        low_items = SummaryService.get_low_stock_items(db)

        if not low_items:
            message_text = "All kirana inventory levels are healthy. No items need reordering today."
        else:
            lines = [
                "Namaste, please deliver the following items for my Kirana shop:",
                ""
            ]
            for it in low_items:
                reorder_suggested = max(it.deficit * 2, 5.0)
                lines.append(
                    f"• {it.name}: Current stock {it.current_stock:g} {it.unit} (Need at least {reorder_suggested:g} {it.unit})"
                )
            lines.append("")
            lines.append("Please confirm dispatch. Thank you!")
            message_text = "\n".join(lines)

        encoded_text = urllib.parse.quote(message_text)

        # Build WhatsApp click-to-chat URL: https://wa.me/<number>?text=...
        # If phone_number is not provided or empty, use https://wa.me/?text=...
        clean_phone = "".join(filter(str.isdigit, phone_number)) if phone_number else ""
        if clean_phone:
            whatsapp_url = f"https://wa.me/{clean_phone}?text={encoded_text}"
        else:
            whatsapp_url = f"https://wa.me/?text={encoded_text}"

        return SupplierReorderResponse(
            supplier_phone=clean_phone if clean_phone else None,
            items_count=len(low_items),
            items=low_items,
            message_text=message_text,
            whatsapp_url=whatsapp_url
        )

    @staticmethod
    def get_daily_summary(db: Session, target_date: Optional[date] = None) -> DailySummaryResponse:
        """
        Produce end-of-day summary:
        - Items sold, received, damaged, returned
        - Current stock overview
        - Credit summary (udhaar taken vs payments collected)
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

            # Look up units
            result = []
            for item_name, total_qty in item_totals.items():
                item = db.query(InventoryItem).filter(InventoryItem.name == item_name).first()
                unit = item.unit if item else "pcs"
                count = sum(1 for t in matching if t.item_name == item_name)
                result.append(
                    ActionGroupSummary(
                        item_name=item_name.title(),
                        total_quantity=round(total_qty, 2),
                        unit=unit,
                        transactions_count=count
                    )
                )
            return sorted(result, key=lambda x: x.item_name)

        sold_list = group_by_action("sold")
        received_list = group_by_action("received")
        damaged_list = group_by_action("damaged")
        returned_list = group_by_action("returned")

        # Current stock overview of all items
        all_items = db.query(InventoryItem).order_by(InventoryItem.name.asc()).all()
        overview = [
            StockItemOverview(
                name=it.name.title(),
                quantity=it.quantity,
                unit=it.unit,
                price=it.price,
                is_low_stock=it.is_low_stock
            )
            for it in all_items
        ]

        # Credit transactions for the day
        credit_txs = (
            db.query(CreditTransaction)
            .filter(CreditTransaction.timestamp >= start_dt, CreditTransaction.timestamp <= end_dt)
            .all()
        )
        credit_purchases = sum(t.amount for t in credit_txs if t.action == "credit_purchase")
        payments_collected = sum(t.amount for t in credit_txs if t.action == "payment")

        credit_summary = CreditDaySummary(
            total_credit_purchases_amount=round(credit_purchases, 2),
            total_payments_received_amount=round(payments_collected, 2),
            transactions_count=len(credit_txs)
        )

        return DailySummaryResponse(
            date=target_date.isoformat(),
            total_inventory_actions=len(inv_txs),
            items_sold=sold_list,
            items_received=received_list,
            items_damaged=damaged_list,
            items_returned=returned_list,
            current_stock_overview=overview,
            credit_summary=credit_summary
        )
