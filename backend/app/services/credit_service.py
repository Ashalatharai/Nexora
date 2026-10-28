from datetime import datetime, timezone
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.credit import Customer, CreditTransaction
from app.schemas.credit import (
    CreditAction,
    CreditTransactionRequest,
    CreditTransactionResponse,
)


class CreditService:
    @staticmethod
    def list_customers(db: Session) -> List[Customer]:
        """Return all customers sorted by outstanding balance descending."""
        return db.query(Customer).order_by(Customer.outstanding_balance.desc(), Customer.name.asc()).all()

    @staticmethod
    def get_customer_by_name(db: Session, name: str) -> Optional[Customer]:
        """Fetch customer by name (case-insensitive)."""
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
        """
        clean_name = request.customer_name.strip().title()
        amount = request.amount
        action = request.action.value

        if amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Transaction amount must be greater than zero."
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

        elif action == CreditAction.CREDIT_PURCHASE.value:
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
            timestamp=tx.timestamp
        )
