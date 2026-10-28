from typing import List
from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.credit import (
    CustomerResponse,
    CreditTransactionRequest,
    CreditTransactionResponse,
    CustomerLedgerReconciliation
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
    - Supports idempotency keys to prevent duplicate payments on retry.
    """
    return CreditService.execute_credit_transaction(db, request)


@router.get(
    "/customers/{customer_name}/verify",
    response_model=CustomerLedgerReconciliation,
    summary="Audit and reconcile customer balance against ledger history"
)
def verify_customer_ledger(
    customer_name: str = Path(..., description="Customer name to audit"),
    db: Session = Depends(get_db)
):
    """
    Recomputes total credit purchases minus total payments from raw transaction history
    and verifies that the stored balance matches exactly with zero drift.
    """
    return CreditService.verify_customer_ledger(db, customer_name=customer_name)
