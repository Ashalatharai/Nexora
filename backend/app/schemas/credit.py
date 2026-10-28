from enum import Enum
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict


class CreditAction(str, Enum):
    CREDIT_PURCHASE = "credit_purchase"
    PAYMENT = "payment"


class CustomerBase(BaseModel):
    name: str = Field(..., min_length=1, description="Customer name")
    phone: Optional[str] = Field(None, description="Contact phone number")

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        return v.strip().title()


class CustomerCreate(CustomerBase):
    initial_balance: float = Field(default=0.0, ge=0.0)


class CustomerResponse(CustomerBase):
    id: int
    outstanding_balance: float
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CreditTransactionRequest(BaseModel):
    customer_name: str = Field(..., min_length=1, description="Customer name")
    action: CreditAction = Field(..., description="Action: 'credit_purchase' or 'payment'")
    amount: float = Field(..., gt=0.0, description="Amount in INR (must be > 0)")
    details: Optional[str] = Field(None, description="Optional details (e.g. '2 rice bags on credit')")
    idempotency_key: Optional[str] = Field(None, description="Optional unique key to prevent duplicate payments on retry")

    @field_validator("customer_name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        return v.strip().title()


class CreditTransactionResponse(BaseModel):
    success: bool
    confirmation: str
    customer_name: str
    action: str
    amount: float
    previous_balance: float
    resulting_balance: float
    timestamp: datetime
    is_duplicate_replay: bool = False


class CustomerLedgerReconciliation(BaseModel):
    customer_id: int
    customer_name: str
    current_balance: float
    computed_balance_from_ledger: float
    is_consistent: bool
    total_purchases: float
    total_payments: float
