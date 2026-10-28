from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from app.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    phone = Column(String(20), nullable=True)
    outstanding_balance = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class CreditTransaction(Base):
    __tablename__ = "credit_transactions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)
    customer_name = Column(String(100), nullable=False, index=True)
    action = Column(String(30), nullable=False, index=True)  # credit_purchase, payment
    amount = Column(Float, nullable=False)
    previous_balance = Column(Float, nullable=False)
    resulting_balance = Column(Float, nullable=False)
    details = Column(String(255), nullable=True)
    timestamp = Column(DateTime(timezone=True), default=utc_now, index=True)
