from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.credit import (
    CustomerResponse,
    CreditTransactionRequest,
    CreditTransactionResponse
)
from app.services.credit_service import CreditService

router = APIRouter(prefix="/credit", tags=["Credit (Udhaar)"])


@router.get("/customers", response_model=List[CustomerResponse], summary="List all customers and credit balances")
def list_customers(db: Session = Depends(get_db)):
    """Retrieve all customer accounts with their outstanding credit balance."""
    return CreditService.list_customers(db)


@router.post("/transaction", response_model=CreditTransactionResponse, summary="Record credit purchase or debt payment")
def record_credit_transaction(
    request: CreditTransactionRequest,
    db: Session = Depends(get_db)
):
    """
    Record customer credit purchase or payment:
    - action='credit_purchase': Increases customer debt.
    - action='payment': Decreases customer debt (rejects overpayments).
    """
    return CreditService.execute_credit_transaction(db, request)
