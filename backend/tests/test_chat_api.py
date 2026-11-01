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

    def test_13_deeksha_paid_20(self):
        """
        Verify payment:
        'Deeksha paid 20'
        Reduces Deeksha's pending credit balance (was 28 from previous credit test).
        """
        state = self.client.get("/api/store/state").json()
        deeksha = next(c for c in state["customers"] if "Deeksha" in c["name"])
        due_before = deeksha["due"]

        payload = {"message": "Deeksha paid 20", "session_id": "test_sess"}
        response = self.client.post("/api/chat", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["action_taken"], "payment")
        self.assertIn("Payment recorded", data["reply"])
        self.assertIn("Deeksha", data["reply"])

        deeksha_after = next(c for c in data["store_state"]["customers"] if "Deeksha" in c["name"])
        self.assertEqual(deeksha_after["due"], due_before - 20)

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

    def test_20_compound_sale_and_restock(self):
        """
        Verify multi-action prompt:
        'sold maggie 2 packets and received 2 tata salt packets'
        - Deducts 2 Maggi from stock (sale)
        - Adds 2 Tata Salt to stock (restock)
        - Logs both transactions
        """
        state = self.client.get("/api/store/state").json()
        maggi_before = next(p for p in state["products"] if "Maggi" in p["name"])["stock"]
        salt_before = next(p for p in state["products"] if "Tata Salt" in p["name"])["stock"]

        payload = {"message": "sold maggie 2 packets and received 2 tata salt packets", "session_id": "test_sess"}
        response = self.client.post("/api/chat", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["action_taken"], "multi")
        self.assertIn("Maggi", data["reply"])
        self.assertIn("Tata Salt", data["reply"])
        self.assertIn("Updated records", data["reply"])

        maggi_after = next(p for p in data["store_state"]["products"] if "Maggi" in p["name"])["stock"]
        salt_after = next(p for p in data["store_state"]["products"] if "Tata Salt" in p["name"])["stock"]
        self.assertEqual(maggi_after, maggi_before - 2)
        self.assertEqual(salt_after, salt_before + 2)

    def test_21_compound_multiple_sales(self):
        """
        Verify multi-item sale in one prompt:
        'Sold 3 Maggi, 2 milk'
        - Deducts 3 Maggi and 2 Milk
        """
        state = self.client.get("/api/store/state").json()
        maggi_before = next(p for p in state["products"] if "Maggi" in p["name"])["stock"]
        milk_before = next(p for p in state["products"] if "Milk" in p["name"])["stock"]

        payload = {"message": "Sold 3 Maggi, 2 milk", "session_id": "test_sess"}
        response = self.client.post("/api/chat", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["action_taken"], "multi")

        maggi_after = next(p for p in data["store_state"]["products"] if "Maggi" in p["name"])["stock"]
        milk_after = next(p for p in data["store_state"]["products"] if "Milk" in p["name"])["stock"]
        self.assertEqual(maggi_after, maggi_before - 3)
        self.assertEqual(milk_after, milk_before - 2)

    def test_22_compound_credit_and_payment(self):
        """
        Verify compound credit and payment:
        'Ramesh took 2 milk on credit and paid 50'
        """
        state = self.client.get("/api/store/state").json()
        ramesh = next(c for c in state["customers"] if c["name"] == "Ramesh")
        due_before = ramesh["due"]
        milk = next(p for p in state["products"] if "Milk" in p["name"])

        payload = {"message": "Ramesh took 2 milk on credit and paid 50", "session_id": "test_sess"}
        response = self.client.post("/api/chat", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["action_taken"], "multi")

        ramesh_after = next(c for c in data["store_state"]["customers"] if c["name"] == "Ramesh")
        # Due should be: due_before + (2 * price) - 50
        expected_due = max(0.0, due_before + (2 * milk["price"]) - 50)
        self.assertEqual(ramesh_after["due"], expected_due)

    def test_23_cash_purchase_ramesh(self):
        """
        Requirement 2: CASH PURCHASE
        'Ramesh bought 2 Maggi for cash'
        - Identifies customer, product, quantity, payment type Cash
        - Reduces inventory by 2
        - Records sale as paid/cash
        - Customer credit balance is NOT increased
        - Confirmation includes item, quantity, amount, payment type, stock remaining, credit balance
        """
        state = self.client.get("/api/store/state").json()
        ramesh_before = next(c for c in state["customers"] if c["name"] == "Ramesh")
        maggi_before = next(p for p in state["products"] if "Maggi" in p["name"])

        payload = {"message": "Ramesh bought 2 Maggi for cash", "session_id": "test_sess"}
        response = self.client.post("/api/chat", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["action_taken"], "sale")
        self.assertIn("Cash", data["reply"])
        self.assertIn("Maggi", data["reply"])
        self.assertIn("Stock remaining", data["reply"])

        # Check stock reduced by 2
        maggi_after = next(p for p in data["store_state"]["products"] if "Maggi" in p["name"])
        self.assertEqual(maggi_after["stock"], maggi_before["stock"] - 2)

        # Check Ramesh due balance did NOT increase
        ramesh_after = next(c for c in data["store_state"]["customers"] if c["id"] == ramesh_before["id"])
        self.assertEqual(ramesh_after["due"], ramesh_before["due"])

    def test_24_udhaar_purchase_ramesh(self):
        """
        Requirement 3: UDHAAR PURCHASE
        'Ramesh took 3 rice on udhaar'
        - Reduces inventory by 3
        - Calculates total using selling price (120 * 3 = 360)
        - Records transaction as credit
        - Increases Ramesh's outstanding balance
        """
        state = self.client.get("/api/store/state").json()
        ramesh_before = next(c for c in state["customers"] if c["name"] == "Ramesh")
        rice_before = next(p for p in state["products"] if "Rice" in p["name"])

        payload = {"message": "Ramesh took 3 rice on udhaar", "session_id": "test_sess"}
        response = self.client.post("/api/chat", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["action_taken"], "credit")
        self.assertIn("Udhaar", data["reply"])
        self.assertIn("Rice", data["reply"])
        self.assertIn("Stock remaining", data["reply"])

        # Check stock reduced by 3
        rice_after = next(p for p in data["store_state"]["products"] if "Rice" in p["name"])
        self.assertEqual(rice_after["stock"], rice_before["stock"] - 3)

        # Check Ramesh balance increased by 3 * 120 = 360
        ramesh_after = next(c for c in data["store_state"]["customers"] if c["id"] == ramesh_before["id"])
        self.assertEqual(ramesh_after["due"], ramesh_before["due"] + 360.0)

    def test_25_customer_payment_ramesh(self):
        """
        Requirement 4: CUSTOMER PAYMENT
        'Ramesh paid ₹200'
        - Reduces outstanding balance by 200
        - Does NOT change inventory
        """
        state = self.client.get("/api/store/state").json()
        ramesh_before = next(c for c in state["customers"] if c["name"] == "Ramesh")
        stock_snapshot = {p["id"]: p["stock"] for p in state["products"]}

        payload = {"message": "Ramesh paid ₹200", "session_id": "test_sess"}
        response = self.client.post("/api/chat", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["action_taken"], "payment")
        self.assertIn("paid ₹200", data["reply"])
        self.assertIn("Inventory unchanged", data["reply"])

        # Check balance reduced by 200
        ramesh_after = next(c for c in data["store_state"]["customers"] if c["id"] == ramesh_before["id"])
        self.assertEqual(ramesh_after["due"], ramesh_before["due"] - 200.0)

        # Verify inventory untouched
        for p in data["store_state"]["products"]:
            self.assertEqual(p["stock"], stock_snapshot[p["id"]])

    def test_26_customer_payment_exceeding_balance(self):
        """
        Requirement 4: Prevent payments exceeding outstanding balance
        'Ramesh paid 50000'
        - Rejected with clear error message
        - Balance untouched
        """
        state = self.client.get("/api/store/state").json()
        ramesh_before = next(c for c in state["customers"] if c["name"] == "Ramesh")

        payload = {"message": "Ramesh paid 50000", "session_id": "test_sess"}
        response = self.client.post("/api/chat", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["action_taken"], "none")
        self.assertIn("exceeds", data["reply"].lower())

        # Balance remains unchanged
        ramesh_after = next(c for c in data["store_state"]["customers"] if c["id"] == ramesh_before["id"])
        self.assertEqual(ramesh_after["due"], ramesh_before["due"])

    def test_27_customer_payment_zero_balance(self):
        """
        Requirement 4: Prevent payments when customer has zero balance
        'Kavita Shah paid 100' (Kavita Shah has 0 due)
        - Rejected with clear error message
        """
        payload = {"message": "Kavita Shah paid 100", "session_id": "test_sess"}
        response = self.client.post("/api/chat", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["action_taken"], "none")
        self.assertIn("no outstanding", data["reply"].lower())

    def test_28_new_customer_purchase_cash(self):
        """
        Requirement 5: NEW CUSTOMER PURCHASE (Cash)
        'New customer Priya with phone 9899988877 bought 2 Maggi for cash'
        - Auto-creates customer 'Priya' with phone in SQLite
        - Deducts 2 Maggi
        - Records Cash sale
        - Credit balance remains 0
        - Confirmation includes customer registration note
        """
        maggi_before = next(p for p in self.client.get("/api/store/state").json()["products"] if "Maggi" in p["name"])["stock"]

        payload = {"message": "New customer Priya with phone 9899988877 bought 2 Maggi for cash", "session_id": "test_sess"}
        response = self.client.post("/api/chat", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["action_taken"], "sale")
        self.assertIn("Priya", data["reply"])
        self.assertIn("Cash", data["reply"])

        # Customer is now in customer list
        priya = next((c for c in data["store_state"]["customers"] if c["name"] == "Priya"), None)
        self.assertIsNotNone(priya)
        self.assertEqual(priya["phone"], "9899988877")
        self.assertEqual(priya["due"], 0.0)

        # Maggi stock reduced
        maggi_after = next(p for p in data["store_state"]["products"] if "Maggi" in p["name"])["stock"]
        self.assertEqual(maggi_after, maggi_before - 2)

    def test_29_new_customer_purchase_udhaar(self):
        """
        Requirement 5: NEW CUSTOMER PURCHASE (Udhaar)
        'New customer Anita with phone 9811122233 took 1 milk on udhaar'
        - Auto-creates customer 'Anita' with phone in SQLite
        - Deducts 1 Milk
        - Records Udhaar purchase
        - Credit balance set to price of 1 milk (28)
        """
        state = self.client.get("/api/store/state").json()
        milk = next(p for p in state["products"] if "Milk" in p["name"])
        milk_before = milk["stock"]

        payload = {"message": "New customer Anita with phone 9811122233 took 1 milk on udhaar", "session_id": "test_sess"}
        response = self.client.post("/api/chat", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["action_taken"], "credit")
        self.assertIn("Anita", data["reply"])
        self.assertIn("Udhaar", data["reply"])

        # Anita created with due = 28
        anita = next((c for c in data["store_state"]["customers"] if c["name"] == "Anita"), None)
        self.assertIsNotNone(anita)
        self.assertEqual(anita["phone"], "9811122233")
        self.assertEqual(anita["due"], milk["price"])

        milk_after = next(p for p in data["store_state"]["products"] if "Milk" in p["name"])["stock"]
        self.assertEqual(milk_after, milk_before - 1)

    def test_30_missing_payment_type_clarification(self):
        """
        Requirement 6: VALIDATION (Missing payment type)
        'Ramesh took 2 Maggi'
        - Asks whether transaction was cash or udhaar
        - No transaction recorded
        """
        payload = {"message": "Ramesh took 2 Maggi", "session_id": "test_sess"}
        response = self.client.post("/api/chat", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["clarification_needed"])
        self.assertIn("cash", data["reply"].lower())
        self.assertIn("credit", data["reply"].lower())

    def test_31_new_customer_missing_name_clarification(self):
        """
        Requirement 5: If required customer info is missing, ask for it
        'New customer bought 2 Maggi for cash'
        - Asks for new customer name
        - No transaction recorded
        """
        payload = {"message": "New customer bought 2 Maggi for cash", "session_id": "test_sess"}
        response = self.client.post("/api/chat", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["clarification_needed"])
        self.assertIn("name", data["reply"].lower())

    def test_32_compound_cash_and_udhaar(self):
        """
        Requirement 6: Handle multiple items in one message
        'Ramesh bought 2 Maggi for cash and took 1 milk on udhaar'
        - Executes both transactions in sequence
        - Deducts 2 Maggi and 1 Milk
        - Increases Udhaar balance only for Milk
        """
        state = self.client.get("/api/store/state").json()
        maggi_before = next(p for p in state["products"] if "Maggi" in p["name"])["stock"]
        milk = next(p for p in state["products"] if "Milk" in p["name"])
        milk_before = milk["stock"]
        ramesh_before = next(c for c in state["customers"] if c["name"] == "Ramesh")["due"]

        payload = {"message": "Ramesh bought 2 Maggi for cash and took 1 milk on udhaar", "session_id": "test_sess"}
        response = self.client.post("/api/chat", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["action_taken"], "multi")

        state_after = data["store_state"]
        maggi_after = next(p for p in state_after["products"] if "Maggi" in p["name"])["stock"]
        milk_after = next(p for p in state_after["products"] if "Milk" in p["name"])["stock"]
        ramesh_after = next(c for c in state_after["customers"] if c["name"] == "Ramesh")["due"]

        self.assertEqual(maggi_after, maggi_before - 2)
        self.assertEqual(milk_after, milk_before - 1)
        self.assertEqual(ramesh_after, ramesh_before + milk["price"])

if __name__ == "__main__":
    unittest.main()
