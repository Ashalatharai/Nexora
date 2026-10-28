from typing import List, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.inventory import InventoryItem, InventoryTransaction
from app.schemas.inventory import (
    InventoryAction,
    InventoryItemCreate,
    InventoryTransactionRequest,
    InventoryTransactionResponse,
    ItemUpdateResult,
)


def format_qty(qty: float) -> str:
    """Format quantity cleanly (e.g. 3.0 -> '3', 2.5 -> '2.5')."""
    return f"{qty:g}"


class InventoryService:
    @staticmethod
    def list_inventory(db: Session) -> List[InventoryItem]:
        """Fetch all inventory items ordered by name."""
        return db.query(InventoryItem).order_by(InventoryItem.name.asc()).all()

    @staticmethod
    def get_item_by_name(db: Session, name: str) -> InventoryItem | None:
        """Find an item by name (case-insensitive)."""
        clean_name = name.strip().lower()
        return db.query(InventoryItem).filter(func.lower(InventoryItem.name) == clean_name).first()

    @staticmethod
    def create_or_update_item(db: Session, payload: InventoryItemCreate) -> InventoryItem:
        """Create a new item or update an existing item baseline."""
        item = InventoryService.get_item_by_name(db, payload.name)
        if item:
            item.quantity = payload.quantity
            item.unit = payload.unit
            item.price = payload.price
            item.min_threshold = payload.min_threshold
        else:
            item = InventoryItem(
                name=payload.name.strip().lower(),
                quantity=payload.quantity,
                unit=payload.unit,
                price=payload.price,
                min_threshold=payload.min_threshold,
            )
            db.add(item)
        db.commit()
        db.refresh(item)
        return item

    @staticmethod
    def execute_transaction(db: Session, request: InventoryTransactionRequest) -> InventoryTransactionResponse:
        """
        Executes a batch inventory transaction atomically.
        Validates all items before making changes.
        If any item fails, rejects the entire transaction without changing stock.
        """
        if not request.items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Transaction request must include at least one item."
            )

        # Step 1: Pre-validation phase (All-or-Nothing check)
        validated_items: List[Tuple[InventoryItem, str, float]] = []

        # We keep track of simulated quantities to ensure multiple operations on the same item in one batch are safe
        projected_quantities = {}

        for entry in request.items:
            action = entry.action.value.lower()
            qty = entry.quantity
            item_name = entry.item_name.strip().lower()

            if qty <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid quantity {qty} for item '{item_name}'. Quantity must be greater than zero."
                )

            item = InventoryService.get_item_by_name(db, item_name)
            if not item:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Item '{item_name}' was not found in inventory. Please add it before updating stock."
                )

            current_qty = projected_quantities.get(item.id, item.quantity)

            if action in [InventoryAction.SOLD.value, InventoryAction.DAMAGED.value]:
                if current_qty < qty:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"Insufficient stock for '{item.name.title()}'. "
                            f"Available: {format_qty(current_qty)} {item.unit}, "
                            f"Requested to {action}: {format_qty(qty)} {item.unit}."
                        )
                    )
                projected_quantities[item.id] = current_qty - qty
            elif action in [InventoryAction.RECEIVED.value, InventoryAction.RETURNED.value]:
                projected_quantities[item.id] = current_qty + qty
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unsupported inventory action '{action}'."
                )

            validated_items.append((item, action, qty))

        # Step 2: Atomic Execution phase within DB transaction
        updates: List[ItemUpdateResult] = []
        low_stock_alerts: List[str] = []
        confirmation_parts: List[str] = []

        try:
            for item, action, qty in validated_items:
                prev_stock = item.quantity

                if action in [InventoryAction.SOLD.value, InventoryAction.DAMAGED.value]:
                    new_stock = prev_stock - qty
                else:  # received, returned
                    new_stock = prev_stock + qty

                item.quantity = new_stock

                # Record transaction log
                tx_record = InventoryTransaction(
                    item_name=item.name,
                    action=action,
                    quantity=qty,
                    previous_stock=prev_stock,
                    resulting_stock=new_stock,
                    note=request.note
                )
                db.add(tx_record)

                updates.append(
                    ItemUpdateResult(
                        item_name=item.name,
                        action=action,
                        quantity=qty,
                        previous_stock=prev_stock,
                        resulting_stock=new_stock,
                        unit=item.unit
                    )
                )

                confirmation_parts.append(
                    f"{item.name.title()} {format_qty(prev_stock)} → {format_qty(new_stock)}"
                )

                if new_stock <= item.min_threshold:
                    low_stock_alerts.append(
                        f"⚠️ Low stock: {item.name.title()} ({format_qty(new_stock)} {item.unit} remaining, min {format_qty(item.min_threshold)})"
                    )

            db.commit()

        except Exception as e:
            db.rollback()
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to record inventory transaction: {str(e)}"
            )

        confirmation_str = "Updated: " + ", ".join(confirmation_parts)

        return InventoryTransactionResponse(
            success=True,
            confirmation=confirmation_str,
            updates=updates,
            low_stock_alerts=low_stock_alerts
        )
