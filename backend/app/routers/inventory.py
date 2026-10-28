from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.inventory import (
    InventoryItemCreate,
    InventoryItemResponse,
    InventoryTransactionRequest,
    InventoryTransactionResponse
)
from app.services.inventory_service import InventoryService

router = APIRouter(prefix="/inventory", tags=["Inventory"])


@router.get("", response_model=List[InventoryItemResponse], summary="List all inventory items")
def get_inventory(db: Session = Depends(get_db)):
    """Fetch complete stock list with current quantities and low-stock indicators."""
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
    """
    return InventoryService.execute_transaction(db, request)
