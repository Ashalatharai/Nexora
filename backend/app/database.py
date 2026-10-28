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


def seed_default_data(db: Session):
    """Seed initial realistic Kirana items and sample customer for judging demo if empty."""
    from app.models.inventory import InventoryItem
    from app.models.credit import Customer

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


def init_db(seed: bool = True):
    """Initialize database tables and seed baseline data."""
    Base.metadata.create_all(bind=engine)
    if seed:
        with SessionLocal() as db:
            seed_default_data(db)
