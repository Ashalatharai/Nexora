import sys
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.database import Base, get_db
from app.main import app
from app.models.inventory import InventoryItem
from app.models.credit import Customer

# In-memory SQLite with StaticPool so all threads and sessions share the exact same in-memory DB
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Create fresh database tables and populate baseline test data per test."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()

    # Seed baseline items for tests
    items = [
        InventoryItem(name="maggi", quantity=40.0, unit="pkt", price=14.0, min_threshold=10.0),
        InventoryItem(name="milk", quantity=12.0, unit="pkt", price=28.0, min_threshold=5.0),
        InventoryItem(name="rice", quantity=25.0, unit="bag", price=650.0, min_threshold=5.0),
        InventoryItem(name="oil", quantity=10.0, unit="bottle", price=140.0, min_threshold=3.0),
        InventoryItem(name="soap", quantity=20.0, unit="bar", price=35.0, min_threshold=5.0),
    ]
    session.add_all(items)

    # Seed sample customer
    customer = Customer(name="Ramesh", phone="9876543210", outstanding_balance=350.0)
    session.add(customer)

    session.commit()

    yield session

    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """TestClient that uses the test database session."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
