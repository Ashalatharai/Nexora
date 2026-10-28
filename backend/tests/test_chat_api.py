import os
import sys
import unittest
import sqlite3
from pathlib import Path

# Add backend directory to sys.path
CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from main import app
from database import init_db
from config import settings

class KiranaChatAPITestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Use an isolated SQLite test database
        cls.test_db = str(CURRENT_DIR / "test_kirana_chat.db")
        settings.DATABASE_PATH = cls.test_db
        if os.path.exists(cls.test_db):
            os.remove(cls.test_db)
        init_db(cls.test_db)
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.test_db):
            try:
                os.remove(cls.test_db)
            except Exception:
                pass

    def test_01_health_check(self):
        """Verify GET /api/health endpoint returns FastAPI status and database connectivity."""
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["framework"], "FastAPI")
        self.assertEqual(data["database"], "connected")
        self.assertIn("llm_provider", data)

    def test_02_store_state(self):
        """Verify GET /api/store/state returns complete SQLite records."""
        response = self.client.get("/api/store/state")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("products", data)
        self.assertIn("customers", data)
        self.assertIn("transactions", data)
        self.assertGreaterEqual(len(data["products"]), 8)
        self.assertGreaterEqual(len(data["customers"]), 6)
        # Verify Deeksha is in the customer records
        self.assertTrue(any("Deeksha" in c["name"] for c in data["customers"]))

    def test_03_chat_greetings(self):
        """Verify chat handles greetings naturally."""
        payload = {"message": "Namaste! Kaise ho?", "session_id": "test_sess"}
        response = self.client.post("/api/chat", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("Namaste", data["reply"])
        self.assertFalse(data["clarification_needed"])

    def test_04_deeksha_bought_2_maggie(self):
        """
        Verify natural language customer purchase:
        'Deeksha bought 2 maggie'
        - Resolves customer 'Deeksha'
        - Handles informal spelling 'maggie' -> 'Maggi 2-Minute Noodles'
        - Deducts 2 from stock
        - Records sale transaction
        """
        # Get current Maggi stock
        state = self.client.get("/api/store/state").json()
        maggi = next(p for p in state["products"] if "Maggi" in p["name"])
        stock_before = maggi["stock"]

        payload = {"message": "Deeksha bought 2 maggie", "session_id": "test_sess"}
        response = self.client.post("/api/chat", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["action_taken"], "sale")
        self.assertIn("Maggi", data["reply"])
        self.assertIn("Deeksha", data["reply"])

        # Check that stock was reduced in SQLite
        maggi_after = next(p for p in data["store_state"]["products"] if "Maggi" in p["name"])
        self.assertEqual(maggi_after["stock"], stock_before - 2)

    def test_05_sold_2_maggi_to_deeksha(self):
        """Verify alternate sentence structure: 'Sold 2 Maggi to Deeksha'."""
        state = self.client.get("/api/store/state").json()
        maggi = next(p for p in state["products"] if "Maggi" in p["name"])
        stock_before = maggi["stock"]

        payload = {"message": "Sold 2 Maggi to Deeksha", "session_id": "test_sess"}
        response = self.client.post("/api/chat", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["action_taken"], "sale")
        self.assertIn("Maggi", data["reply"])
        self.assertIn("Deeksha", data["reply"])

        maggi_after = next(p for p in data["store_state"]["products"] if "Maggi" in p["name"])
        self.assertEqual(maggi_after["stock"], stock_before - 2)

    def test_06_product_not_found_handling(self):
        """
        Example C: Product unavailable in inventory catalogue
        User: 'Sold 2 Chocolate bars.'
        System: 'Product Not Found: Chocolate bars is not listed in your inventory...'
        No sale recorded.
        """
        payload = {"message": "Sold 2 Chocolate bars", "session_id": "test_sess"}
        response = self.client.post("/api/chat", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["action_taken"], "none")
        self.assertIn("Product Not Found", data["reply"])
        self.assertIn("Chocolate bars", data["reply"])

    def test_07_out_of_stock_handling(self):
        """
        Example A: Product exists but stock is 0
        System: '{Product} is Out of Stock. No sale was recorded.'
        """
        # Set Amul Butter stock to 0 in database
        conn = sqlite3.connect(self.test_db)
        conn.execute("UPDATE products SET stock = 0 WHERE name LIKE '%Butter%'")
        conn.commit()
        conn.close()

        payload = {"message": "Sold 2 Butter to Deeksha", "session_id": "test_sess"}
        response = self.client.post("/api/chat", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["action_taken"], "none")
        self.assertIn("Out of Stock", data["reply"])
        self.assertIn("No sale was recorded", data["reply"])

        # Check stock is still 0 (not reduced below zero)
        state = self.client.get("/api/store/state").json()
        butter = next(p for p in state["products"] if "Butter" in p["name"])
        self.assertEqual(butter["stock"], 0)

    def test_08_insufficient_stock_handling(self):
        """
        Example B: Requested quantity exceeds available quantity
        Available stock: 3 packets. Requested: 5 packets.
        System: 'Insufficient Stock: Only 3 ... are available, but you requested 5. No sale was recorded.'
        """
        # Set Tata Salt stock to 3
        conn = sqlite3.connect(self.test_db)
        conn.execute("UPDATE products SET stock = 3 WHERE name LIKE '%Tata Salt%'")
        conn.commit()
        conn.close()

        payload = {"message": "Sold 5 Tata Salt to Deeksha", "session_id": "test_sess"}
        response = self.client.post("/api/chat", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["action_taken"], "none")
        self.assertIn("Insufficient Stock", data["reply"])
        self.assertIn("Only 3", data["reply"])
        self.assertIn("requested 5", data["reply"])
        self.assertIn("No sale was recorded", data["reply"])

        # Ensure stock remains untouched at 3
        state = self.client.get("/api/store/state").json()
        salt = next(p for p in state["products"] if "Tata Salt" in p["name"])
        self.assertEqual(salt["stock"], 3)

    def test_09_add_stock_restock(self):
        """
        Verify stock replenishment:
        'Add 10 Maggi packets to stock'
        Increases stock in SQLite.
        """
        state = self.client.get("/api/store/state").json()
        maggi = next(p for p in state["products"] if "Maggi" in p["name"])
        stock_before = maggi["stock"]

        payload = {"message": "Add 10 Maggi packets to stock", "session_id": "test_sess"}
        response = self.client.post("/api/chat", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["action_taken"], "restock")
        self.assertIn("Stock updated", data["reply"])

        maggi_after = next(p for p in data["store_state"]["products"] if "Maggi" in p["name"])
        self.assertEqual(maggi_after["stock"], stock_before + 10)

    def test_10_how_much_maggi_is_left(self):
        """Verify stock question: 'How much Maggi is left?'."""
        payload = {"message": "How much Maggi is left?", "session_id": "test_sess"}
        response = self.client.post("/api/chat", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["action_taken"], "query")
        self.assertIn("Maggi", data["reply"])
        self.assertIn("in stock", data["reply"])

    def test_11_show_todays_sales(self):
        """Verify sales metrics question: 'Show today's sales.'."""
        payload = {"message": "Show today's sales", "session_id": "test_sess"}
        response = self.client.post("/api/chat", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["action_taken"], "query")
        self.assertIn("sales", data["reply"].lower())
        self.assertIn("₹", data["reply"])

    def test_12_deeksha_took_2_maggi_on_credit(self):
        """
        Verify credit (Udhaar) entry:
        'Deeksha took 2 Maggi on credit'
        - Checks available stock first
        - Deducts stock
        - Adds to Deeksha's balance
        """
        state = self.client.get("/api/store/state").json()
        deeksha = next(c for c in state["customers"] if "Deeksha" in c["name"])
        due_before = deeksha["due"]
        maggi = next(p for p in state["products"] if "Maggi" in p["name"])
        stock_before = maggi["stock"]

        payload = {"message": "Deeksha took 2 Maggi on credit", "session_id": "test_sess"}
        response = self.client.post("/api/chat", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["action_taken"], "credit")
        self.assertIn("credit", data["reply"].lower())
        self.assertIn("Deeksha", data["reply"])

        # Check customer balance updated
        deeksha_after = next(c for c in data["store_state"]["customers"] if "Deeksha" in c["name"])
        self.assertEqual(deeksha_after["due"], due_before + (2 * maggi["price"]))

        # Check stock deducted
        maggi_after = next(p for p in data["store_state"]["products"] if "Maggi" in p["name"])
        self.assertEqual(maggi_after["stock"], stock_before - 2)

    def test_13_deeksha_paid_100(self):
        """
        Verify payment:
        'Deeksha paid 100'
        Reduces Deeksha's pending credit balance.
        """
        state = self.client.get("/api/store/state").json()
        deeksha = next(c for c in state["customers"] if "Deeksha" in c["name"])
        due_before = deeksha["due"]

        payload = {"message": "Deeksha paid 100", "session_id": "test_sess"}
        response = self.client.post("/api/chat", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["action_taken"], "payment")
        self.assertIn("Payment noted", data["reply"])
        self.assertIn("Deeksha", data["reply"])

        deeksha_after = next(c for c in data["store_state"]["customers"] if "Deeksha" in c["name"])
        self.assertEqual(deeksha_after["due"], max(0.0, due_before - 100))

    def test_14_ambiguous_direction_clarification(self):
        """
        Verify asking clarification when transaction direction is ambiguous:
        'Deeksha took 2 Maggi' (without cash or credit specified)
        """
        payload = {"message": "Deeksha took 2 Maggi", "session_id": "test_sess"}
        response = self.client.post("/api/chat", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["clarification_needed"])
        self.assertIn("cash", data["reply"].lower())
        self.assertIn("credit", data["reply"].lower())

    def test_15_clarification_missing_product(self):
        """Verify asking clarification when product is omitted: 'Sold 3'."""
        payload = {"message": "Sold 3", "session_id": "test_sess"}
        response = self.client.post("/api/chat", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["clarification_needed"])
        self.assertIn("Which product", data["reply"])

    def test_16_create_new_customer_ramesh(self):
        """
        Verify new customer creation:
        'Add new customer Ramesh'
        - Recognizes customer-registration intent
        - Saves customer 'Ramesh' in the database
        - Appears in customer list
        """
        payload = {"message": "Add new customer Ramesh", "session_id": "test_sess"}
        response = self.client.post("/api/chat", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["action_taken"], "create_customer")
        self.assertIn("Ramesh", data["reply"])
        self.assertIn("successfully added", data["reply"])

        # Customer must appear in customer list
        customers = data["store_state"]["customers"]
        ramesh = next((c for c in customers if c["name"] == "Ramesh"), None)
        self.assertIsNotNone(ramesh)
        self.assertEqual(ramesh["due"], 0.0)

    def test_17_prevent_duplicate_customer_creation(self):
        """
        Verify duplicate customer prevention:
        Typing 'Add new customer Ramesh' again must NOT create a duplicate.
        """
        # Count current customers
        state_before = self.client.get("/api/store/state").json()
        count_before = len([c for c in state_before["customers"] if c["name"] == "Ramesh"])
        self.assertEqual(count_before, 1)

        payload = {"message": "Add new customer Ramesh", "session_id": "test_sess"}
        response = self.client.post("/api/chat", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["action_taken"], "none")
        self.assertIn("already exists", data["reply"])
        self.assertIn("No duplicate was created", data["reply"])

        # Count must remain 1
        state_after = self.client.get("/api/store/state").json()
        count_after = len([c for c in state_after["customers"] if c["name"] == "Ramesh"])
        self.assertEqual(count_after, 1)

    def test_18_create_customer_with_phone(self):
        """Verify new customer registration with phone: 'Add new customer Suresh with phone 9876543210'."""
        payload = {"message": "Add new customer Suresh with phone 9876543210", "session_id": "test_sess"}
        response = self.client.post("/api/chat", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["action_taken"], "create_customer")
        self.assertIn("Suresh", data["reply"])
        self.assertIn("9876543210", data["reply"])

        customers = data["store_state"]["customers"]
        suresh = next((c for c in customers if c["name"] == "Suresh"), None)
        self.assertIsNotNone(suresh)
        self.assertEqual(suresh["phone"], "9876543210")

    def test_19_transact_with_newly_created_customer(self):
        """Verify newly created customer can immediately perform credit and sales transactions."""
        payload = {"message": "Suresh took 1 milk on credit", "session_id": "test_sess"}
        response = self.client.post("/api/chat", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["action_taken"], "credit")
        self.assertIn("Suresh", data["reply"])

        suresh = next(c for c in data["store_state"]["customers"] if c["name"] == "Suresh")
        self.assertGreater(suresh["due"], 0)

if __name__ == "__main__":
    unittest.main()
