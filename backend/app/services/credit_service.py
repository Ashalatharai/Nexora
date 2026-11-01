from datetime import datetime, timezone
from typing import List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.credit import Customer, CreditTransaction
from app.schemas.credit import (
    CreditAction,
    CreditTransactionRequest,
    CreditTransactionResponse,
    CustomerLedgerReconciliation
)


class CreditService:
    @staticmethod
    def list_customers(db: Session) -> List[Customer]:
        """Return all customers sorted by outstanding balance descending."""
        return db.query(Customer).order_by(Customer.outstanding_balance.desc(), Customer.name.asc()).all()

    @staticmethod
    def get_customer_by_name(db: Session, name: str) -> Optional[Customer]:
        """Fetch customer by name (case-insensitive and trimmed)."""
        clean_name = name.strip().title()
        return db.query(Customer).filter(func.lower(Customer.name) == clean_name.lower()).first()

    @staticmethod
    def get_or_create_customer(db: Session, name: str, phone: Optional[str] = None) -> Customer:
        """Fetch existing customer or create a new profile with 0 balance."""
        clean_name = name.strip().title()
        customer = CreditService.get_customer_by_name(db, clean_name)
        if not customer:
            customer = Customer(name=clean_name, phone=phone, outstanding_balance=0.0)
            db.add(customer)
            db.commit()
            db.refresh(customer)
        return customer

    @staticmethod
    def execute_credit_transaction(db: Session, request: CreditTransactionRequest) -> CreditTransactionResponse:
        """
        Record credit purchase or debt payment.
        - Credit purchases increase outstanding balance.
        - Payments reduce outstanding balance.
        - Rejects zero/negative amounts and payments exceeding current balance.
        - Idempotency support to prevent duplicate debits/credits on client retries.
        """
        clean_name = request.customer_name.strip().title()
        amount = round(request.amount, 2)
        action = request.action.value

        if amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Transaction amount must be greater than zero."
            )

        # Idempotency check: if key already exists, return safe replay
        if request.idempotency_key:
            existing_tx = (
                db.query(CreditTransaction)
                .filter(CreditTransaction.idempotency_key == request.idempotency_key)
                .first()
            )
            if existing_tx:
                return CreditTransactionResponse(
                    success=True,
                    confirmation=(
                        f"Duplicate request detected (idempotency key '{request.idempotency_key}'). "
                        f"Previously processed: {existing_tx.customer_name} {existing_tx.action} ₹{existing_tx.amount:g}. "
                        f"Balance: ₹{existing_tx.resulting_balance:g}"
                    ),
                    customer_name=existing_tx.customer_name,
                    action=existing_tx.action,
                    amount=existing_tx.amount,
                    previous_balance=existing_tx.previous_balance,
                    resulting_balance=existing_tx.resulting_balance,
                    timestamp=existing_tx.timestamp,
                    is_duplicate_replay=True
                )

        customer = CreditService.get_customer_by_name(db, clean_name)

        if action == CreditAction.PAYMENT.value:
            if not customer:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Customer '{clean_name}' does not exist in credit records."
                )

            if customer.outstanding_balance <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Customer '{clean_name}' has no outstanding balance (₹0.00)."
                )

            if amount > customer.outstanding_balance:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Payment amount of ₹{amount:g} exceeds the outstanding balance "
                        f"of ₹{customer.outstanding_balance:g} for '{clean_name}'."
                    )
                )

            prev_balance = customer.outstanding_balance
            new_balance = round(prev_balance - amount, 2)
            confirmation = (
                f"Payment recorded: {clean_name} paid ₹{amount:g}. "
                f"Balance updated: ₹{prev_balance:g} → ₹{new_balance:g}"
            )

        elif action in [CreditAction.CREDIT_PURCHASE.value, "credit_sale_item"]:
            if not customer:
                customer = Customer(name=clean_name, outstanding_balance=0.0)
                db.add(customer)
                db.flush()

            prev_balance = customer.outstanding_balance
            new_balance = round(prev_balance + amount, 2)
            confirmation = (
                f"Udhaar recorded: {clean_name} credit +₹{amount:g}. "
                f"Balance updated: ₹{prev_balance:g} → ₹{new_balance:g}"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown credit action '{action}'."
            )

        try:
            customer.outstanding_balance = new_balance

            tx = CreditTransaction(
                customer_id=customer.id,
                customer_name=customer.name,
                action=action,
                amount=amount,
                previous_balance=prev_balance,
                resulting_balance=new_balance,
                details=request.details,
                idempotency_key=request.idempotency_key,
                timestamp=datetime.now(timezone.utc)
            )
            db.add(tx)
            db.commit()
            db.refresh(tx)

        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to record credit transaction: {str(e)}"
            )

        return CreditTransactionResponse(
            success=True,
            confirmation=confirmation,
            customer_name=customer.name,
            action=action,
            amount=amount,
            previous_balance=prev_balance,
            resulting_balance=new_balance,
            timestamp=tx.timestamp,
            is_duplicate_replay=False
        )

    @staticmethod
    def verify_customer_ledger(db: Session, customer_name: str) -> CustomerLedgerReconciliation:
        """
        Audit verification: recalculates running balance from transaction history
        and compares it against customer.outstanding_balance to detect any drift.
        """
        clean_name = customer_name.strip().title()
        customer = CreditService.get_customer_by_name(db, clean_name)
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Customer '{clean_name}' not found."
            )

        txs = (
            db.query(CreditTransaction)
            .filter(CreditTransaction.customer_name == customer.name)
            .order_by(CreditTransaction.timestamp.asc())
            .all()
        )

        total_purchases = sum(t.amount for t in txs if t.action in ["credit_purchase", "credit_sale_item"])
        total_payments = sum(t.amount for t in txs if t.action == "payment")
        computed_balance = round(total_purchases - total_payments, 2)
        is_consistent = abs(computed_balance - customer.outstanding_balance) < 0.01

        return CustomerLedgerReconciliation(
            customer_id=customer.id,
            customer_name=customer.name,
            current_balance=customer.outstanding_balance,
            computed_balance_from_ledger=computed_balance,
            is_consistent=is_consistent,
            total_purchases=round(total_purchases, 2),
            total_payments=round(total_payments, 2)
        )
