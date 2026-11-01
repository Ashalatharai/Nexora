from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.config import DATABASE_URL

# For SQLite, check_same_thread=False allows FastAPI multithreaded requests
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency to yield an isolated database session per request."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def migrate_db():
    """
    Safely apply missing columns to existing SQLite database tables without data loss.
    Guarantees compatibility when models are extended without requiring manual alembic migrations.
    """
    try:
        with engine.connect() as conn:
            cursor = conn.connection.cursor()

            # Check inventory_transactions table
            cursor.execute("PRAGMA table_info(inventory_transactions)")
            inv_cols = [row[1] for row in cursor.fetchall()]
            if inv_cols:
                if "item_id" not in inv_cols:
                    cursor.execute("ALTER TABLE inventory_transactions ADD COLUMN item_id INTEGER")
                if "idempotency_key" not in inv_cols:
                    cursor.execute("ALTER TABLE inventory_transactions ADD COLUMN idempotency_key VARCHAR(100)")
                if "is_reversed" not in inv_cols:
                    cursor.execute("ALTER TABLE inventory_transactions ADD COLUMN is_reversed BOOLEAN DEFAULT 0")

            # Check credit_transactions table
            cursor.execute("PRAGMA table_info(credit_transactions)")
            credit_cols = [row[1] for row in cursor.fetchall()]
            if credit_cols:
                if "idempotency_key" not in credit_cols:
                    cursor.execute("ALTER TABLE credit_transactions ADD COLUMN idempotency_key VARCHAR(100)")

            conn.connection.commit()
    except Exception as e:
        # If migration fails, log but do not crash startup
        print(f"Database migration note: {e}")


def seed_default_data(db: Session):
    """Seed initial realistic Kirana items and sample customer for judging demo if empty."""
    from app.models.inventory import InventoryItem
    from app.models.credit import Customer, CreditTransaction

    # Check if inventory already has records
    if db.query(InventoryItem).first() is None:
        initial_items = [
            InventoryItem(name="maggi", quantity=40.0, unit="pkt", price=14.0, min_threshold=10.0),
            InventoryItem(name="milk", quantity=12.0, unit="pkt", price=28.0, min_threshold=5.0),
            InventoryItem(name="rice", quantity=25.0, unit="bag", price=650.0, min_threshold=5.0),
            InventoryItem(name="oil", quantity=10.0, unit="bottle", price=140.0, min_threshold=3.0),
            InventoryItem(name="soap", quantity=20.0, unit="bar", price=35.0, min_threshold=5.0),
            InventoryItem(name="sugar", quantity=15.0, unit="kg", price=45.0, min_threshold=5.0),
            InventoryItem(name="tea", quantity=8.0, unit="pkt", price=90.0, min_threshold=4.0),
            InventoryItem(name="biscuit", quantity=30.0, unit="pkt", price=20.0, min_threshold=8.0),
        ]
        db.add_all(initial_items)
        db.commit()

    # Check if customer credit table is empty
    if db.query(Customer).first() is None:
        sample_customers = [
            Customer(name="Ramesh", phone="9876543210", outstanding_balance=350.0),
            Customer(name="Suresh", phone="9876543211", outstanding_balance=0.0),
            Customer(name="Pooja", phone="9876543212", outstanding_balance=120.0),
        ]
        db.add_all(sample_customers)
        db.commit()

        # Seed opening transactions for audit trail consistency
        for c in sample_customers:
            if c.outstanding_balance > 0:
                tx = CreditTransaction(
                    customer_id=c.id,
                    customer_name=c.name,
                    action="credit_purchase",
                    amount=c.outstanding_balance,
                    previous_balance=0.0,
                    resulting_balance=c.outstanding_balance,
                    details="Opening Udhaar Balance"
                )
                db.add(tx)
        db.commit()


def init_db(seed: bool = True):
    """Initialize database tables, run safe automatic migrations, and seed baseline data."""
    Base.metadata.create_all(bind=engine)
    migrate_db()
    if seed:
        with SessionLocal() as db:
            seed_default_data(db)
