from typing import List
from fastapi import APIRouter, Depends, status, Path
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.inventory import (
    InventoryItemCreate,
    InventoryItemResponse,
    InventoryTransactionRequest,
    InventoryTransactionResponse,
    TransactionReversalRequest,
    TransactionReversalResponse
)
from app.services.inventory_service import InventoryService

router = APIRouter(prefix="/inventory", tags=["Inventory"])


@router.get("", response_model=List[InventoryItemResponse], summary="List all inventory items")
def get_inventory(db: Session = Depends(get_db)):
    """Fetch complete stock list with current quantities, units, prices, and low/out-of-stock indicators."""
    return InventoryService.list_inventory(db)


@router.post("/item", response_model=InventoryItemResponse, status_code=status.HTTP_201_CREATED, summary="Add or update item definition")
def add_or_update_item(payload: InventoryItemCreate, db: Session = Depends(get_db)):
    """Create a new item in the catalogue or adjust base quantity and min threshold."""
    return InventoryService.create_or_update_item(db, payload)


@router.post("/transaction", response_model=InventoryTransactionResponse, summary="Apply inventory transactions")
def record_inventory_transaction(
    request: InventoryTransactionRequest,
    db: Session = Depends(get_db)
):
    """
    Atomically apply inventory actions (sold, received, damaged, returned) across multiple items.
    Rejects the entire batch without modifying any stock if any item fails validation.
    Supports idempotency keys to prevent duplicate execution on client network retries.
    """
    return InventoryService.execute_transaction(db, request)


@router.post(
    "/transaction/{transaction_id}/reverse",
    response_model=TransactionReversalResponse,
    summary="Auditably reverse an erroneous transaction"
)
def reverse_transaction(
    transaction_id: int = Path(..., description="ID of the transaction to reverse"),
    payload: TransactionReversalRequest = TransactionReversalRequest(),
    db: Session = Depends(get_db)
):
    """
    Creates an immutable compensating transaction to restore stock to its previous level.
    Never deletes original history rows; records a compensating entry with reason.
    """
    return InventoryService.reverse_transaction(db, transaction_id=transaction_id, reason=payload.reason)
