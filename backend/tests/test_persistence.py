import tempfile
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.inventory import InventoryItem, InventoryTransaction
from app.models.credit import Customer, CreditTransaction


def test_sqlite_file_persistence():
    """Ensure data written to SQLite persists across closed sessions and separate engine instances."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_persist.db")
        db_url = f"sqlite:///{db_path}"

        # 1. First engine instance: create schema and seed data
        engine1 = create_engine(db_url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine1)
        Session1 = sessionmaker(bind=engine1)

        with Session1() as session:
            item = InventoryItem(name="biscuit", quantity=50.0, unit="pkt", price=20.0, min_threshold=10.0)
            customer = Customer(name="Suresh", phone="9988776655", outstanding_balance=400.0)
            session.add(item)
            session.add(customer)
            session.commit()

        engine1.dispose()

        # 2. Second engine instance (simulating app restart)
        engine2 = create_engine(db_url, connect_args={"check_same_thread": False})
        Session2 = sessionmaker(bind=engine2)

        with Session2() as session:
            persisted_item = session.query(InventoryItem).filter_by(name="biscuit").first()
            persisted_customer = session.query(Customer).filter_by(name="Suresh").first()

            assert persisted_item is not None
            assert persisted_item.quantity == 50.0
            assert persisted_item.price == 20.0

            assert persisted_customer is not None
            assert persisted_customer.outstanding_balance == 400.0

            # Apply stock change and add transaction log
            persisted_item.quantity -= 10.0
            tx = InventoryTransaction(
                item_name="biscuit",
                action="sold",
                quantity=10.0,
                previous_stock=50.0,
                resulting_stock=40.0
            )
            session.add(tx)
            session.commit()

        engine2.dispose()

        # 3. Third engine instance: verify updated quantity and log survived
        engine3 = create_engine(db_url, connect_args={"check_same_thread": False})
        Session3 = sessionmaker(bind=engine3)

        with Session3() as session:
            final_item = session.query(InventoryItem).filter_by(name="biscuit").first()
            assert final_item.quantity == 40.0

            logs = session.query(InventoryTransaction).filter_by(item_name="biscuit").all()
            assert len(logs) == 1
            assert logs[0].resulting_stock == 40.0

        engine3.dispose()
