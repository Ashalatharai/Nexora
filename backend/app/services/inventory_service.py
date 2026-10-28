from typing import List, Tuple, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.inventory import InventoryItem, InventoryTransaction, ITEM_ALIASES
from app.schemas.inventory import (
    InventoryAction,
    InventoryItemCreate,
    InventoryTransactionRequest,
    InventoryTransactionResponse,
    ItemUpdateResult,
    TransactionReversalResponse
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
    def get_item_by_name(db: Session, name: str) -> Optional[InventoryItem]:
        """
        Find an item by name or known alias (case-insensitive and trimmed).
        Avoids dangerous fuzzy matching.
        """
        clean_name = name.strip().lower()
        canonical_name = ITEM_ALIASES.get(clean_name, clean_name)
        return db.query(InventoryItem).filter(func.lower(InventoryItem.name) == canonical_name).first()

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
        - Validates all items before making changes.
        - If any item fails, rejects the entire transaction without changing stock.
        - Prevents duplicate execution if an idempotency_key is provided.
        """
        if not request.items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Transaction request must include at least one item."
            )

        # Idempotency check: if key already exists, return safe replay
        if request.idempotency_key:
            existing_tx = (
                db.query(InventoryTransaction)
                .filter(InventoryTransaction.idempotency_key == request.idempotency_key)
                .first()
            )
            if existing_tx:
                item = db.query(InventoryItem).filter(InventoryItem.name == existing_tx.item_name).first()
                unit = item.unit if item else "pcs"
                return InventoryTransactionResponse(
                    success=True,
                    confirmation=(
                        f"Duplicate request detected (idempotency key '{request.idempotency_key}'). "
                        f"Previously processed: {existing_tx.item_name.title()} "
                        f"{format_qty(existing_tx.previous_stock)} → {format_qty(existing_tx.resulting_stock)} {unit}."
                    ),
                    updates=[
                        ItemUpdateResult(
                            item_id=existing_tx.item_id,
                            item_name=existing_tx.item_name,
                            action=existing_tx.action,
                            quantity=existing_tx.quantity,
                            previous_stock=existing_tx.previous_stock,
                            resulting_stock=existing_tx.resulting_stock,
                            unit=unit
                        )
                    ],
                    low_stock_alerts=[],
                    is_duplicate_replay=True
                )

        # Step 1: Pre-validation phase (All-or-Nothing check)
        validated_items: List[Tuple[InventoryItem, str, float]] = []
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
                    detail=(
                        f"Item '{item_name}' was not found in inventory. "
                        f"No stock was changed because one item in the batch could not be processed. "
                        f"Please verify the product name or add it first."
                    )
                )

            current_qty = projected_quantities.get(item.id, item.quantity)

            if action in [InventoryAction.SOLD.value, InventoryAction.DAMAGED.value]:
                if current_qty < qty:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"Insufficient stock for '{item.name.title()}'. "
                            f"Only {format_qty(current_qty)} {item.unit} available, "
                            f"but {format_qty(qty)} {item.unit} was requested to {action}. "
                            f"No stock was changed because one item in the batch could not be processed."
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
                    item_id=item.id,
                    item_name=item.name,
                    action=action,
                    quantity=qty,
                    previous_stock=prev_stock,
                    resulting_stock=new_stock,
                    note=request.note,
                    idempotency_key=request.idempotency_key
                )
                db.add(tx_record)

                updates.append(
                    ItemUpdateResult(
                        item_id=item.id,
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

                if new_stock == 0:
                    low_stock_alerts.append(
                        f"🚨 OUT OF STOCK: {item.name.title()} (0 {item.unit} remaining! Minimum is {format_qty(item.min_threshold)})"
                    )
                elif new_stock <= item.min_threshold:
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
            low_stock_alerts=low_stock_alerts,
            is_duplicate_replay=False
        )

    @staticmethod
    def reverse_transaction(
        db: Session,
        transaction_id: int,
        reason: str = "Shopkeeper requested reversal"
    ) -> TransactionReversalResponse:
        """
        Creates an auditable compensating transaction to reverse a mistaken past transaction.
        Never deletes history rows; records a compensating entry and updates current stock safely.
        """
        tx = db.query(InventoryTransaction).filter(InventoryTransaction.id == transaction_id).first()
        if not tx:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Transaction with ID #{transaction_id} not found."
            )

        if tx.is_reversed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Transaction #{transaction_id} has already been reversed."
            )

        item = db.query(InventoryItem).filter(InventoryItem.name == tx.item_name).first()
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Item '{tx.item_name}' no longer exists in inventory."
            )

        current_stock = item.quantity
        qty = tx.quantity

        # Calculate compensating delta
        # If original action reduced stock (sold, damaged), reversal restores stock (+qty)
        # If original action added stock (received, returned), reversal removes stock (-qty)
        if tx.action in [InventoryAction.SOLD.value, InventoryAction.DAMAGED.value]:
            restored_stock = current_stock + qty
        elif tx.action in [InventoryAction.RECEIVED.value, InventoryAction.RETURNED.value]:
            if current_stock < qty:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Cannot reverse receipt of {format_qty(qty)} {item.unit} because current "
                        f"stock is only {format_qty(current_stock)} {item.unit}."
                    )
                )
            restored_stock = current_stock - qty
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Action '{tx.action}' cannot be reversed."
            )

        try:
            # Mark original transaction as reversed
            tx.is_reversed = True

            # Update item stock
            item.quantity = restored_stock

            # Create compensating transaction record
            compensating_tx = InventoryTransaction(
                item_id=item.id,
                item_name=item.name,
                action=InventoryAction.REVERSAL.value,
                quantity=qty,
                previous_stock=current_stock,
                resulting_stock=restored_stock,
                note=f"Compensating reversal of Tx #{transaction_id}. Reason: {reason}"
            )
            db.add(compensating_tx)
            db.commit()
            db.refresh(compensating_tx)

        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Reversal failed: {str(e)}"
            )

        return TransactionReversalResponse(
            success=True,
            message=f"Transaction #{transaction_id} successfully reversed. {item.name.title()} stock restored to {format_qty(restored_stock)} {item.unit}.",
            reversed_transaction_id=tx.id,
            compensating_transaction_id=compensating_tx.id,
            item_name=item.name.title(),
            restored_stock=restored_stock,
            unit=item.unit
        )
