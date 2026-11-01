import pytest
from app.parser import KiranaMessageParser, ParseResult, AmbiguityType
from fastapi.testclient import TestClient


# ==========================================
# 1. INVENTORY PARSING TESTS
# ==========================================

def test_parse_sales_single_item():
    """Sales: 'sold 3 maggi', 'sell 2 milk packets', 'I sold 4 rice bags'."""
    res1 = KiranaMessageParser.parse("sold 3 maggi")
    assert res1.success is True
    assert res1.intent == "inventory"
    assert len(res1.actions) == 1
    assert res1.actions[0].action == "sold"
    assert res1.actions[0].item_name == "maggi"
    assert res1.actions[0].quantity == 3.0

    res2 = KiranaMessageParser.parse("sell 2 milk packets")
    assert res2.success is True
    assert res2.actions[0].action == "sold"
    assert res2.actions[0].item_name == "milk"
    assert res2.actions[0].quantity == 2.0
    assert res2.actions[0].unit == "pkt"

    res3 = KiranaMessageParser.parse("I sold 4 rice bags")
    assert res3.success is True
    assert res3.actions[0].action == "sold"
    assert res3.actions[0].item_name == "rice"
    assert res3.actions[0].quantity == 4.0
    assert res3.actions[0].unit == "bag"


def test_parse_sales_multiple_items():
    """Sales with multiple items: 'sold 3 maggi and 2 milk', 'sold 5 soaps and 3 shampoos'."""
    res = KiranaMessageParser.parse("sold 3 maggi and 2 milk")
    assert res.success is True
    assert len(res.actions) == 2
    assert res.actions[0].item_name == "maggi"
    assert res.actions[0].quantity == 3.0
    assert res.actions[1].item_name == "milk"
    assert res.actions[1].quantity == 2.0

    res_plural = KiranaMessageParser.parse("sold 5 soaps and 3 shampoos")
    assert res_plural.success is True
    assert len(res_plural.actions) == 2
    assert res_plural.actions[0].item_name == "soap"
    assert res_plural.actions[0].quantity == 5.0
    assert res_plural.actions[1].item_name == "shampoo"
    assert res_plural.actions[1].quantity == 3.0


def test_parse_stock_received():
    """Received: 'received 20 rice bags', 'added 10 milk packets to stock', 'bought 5 oil bottles'."""
    res1 = KiranaMessageParser.parse("received 20 rice bags")
    assert res1.success is True
    assert res1.actions[0].action == "received"
    assert res1.actions[0].item_name == "rice"
    assert res1.actions[0].quantity == 20.0
    assert res1.actions[0].unit == "bag"

    res2 = KiranaMessageParser.parse("added 10 milk packets to stock")
    assert res2.success is True
    assert res2.actions[0].action == "received"
    assert res2.actions[0].item_name == "milk"
    assert res2.actions[0].quantity == 10.0

    res3 = KiranaMessageParser.parse("bought 5 oil bottles")
    assert res3.success is True
    assert res3.actions[0].action == "received"
    assert res3.actions[0].item_name == "oil"
    assert res3.actions[0].quantity == 5.0


def test_parse_damaged_stock():
    """Damaged: 'damaged 2 oil bottles', '2 biscuits were damaged'."""
    res1 = KiranaMessageParser.parse("damaged 2 oil bottles")
    assert res1.success is True
    assert res1.actions[0].action == "damaged"
    assert res1.actions[0].item_name == "oil"
    assert res1.actions[0].quantity == 2.0

    res2 = KiranaMessageParser.parse("2 biscuits were damaged")
    assert res2.success is True
    assert res2.actions[0].action == "damaged"
    assert res2.actions[0].item_name == "biscuit"
    assert res2.actions[0].quantity == 2.0


def test_parse_customer_returns():
    """Returns: 'customer returned 2 soaps', 'returned 3 milk packets'."""
    res1 = KiranaMessageParser.parse("customer returned 2 soaps")
    assert res1.success is True
    assert res1.actions[0].action == "returned"
    assert res1.actions[0].item_name == "soap"
    assert res1.actions[0].quantity == 2.0

    res2 = KiranaMessageParser.parse("returned 3 milk packets")
    assert res2.success is True
    assert res2.actions[0].action == "returned"
    assert res2.actions[0].item_name == "milk"
    assert res2.actions[0].quantity == 3.0


def test_parse_item_aliases():
    """Item aliases resolve correctly without fuzzy errors: 'maggi noodles', 'chai', 'cheeni'."""
    res1 = KiranaMessageParser.parse("sold 2 maggi noodles")
    assert res1.actions[0].item_name == "maggi"

    res2 = KiranaMessageParser.parse("sold 1 chai")
    assert res2.actions[0].item_name == "tea"

    res3 = KiranaMessageParser.parse("sold 5 cheeni")
    assert res3.actions[0].item_name == "sugar"


# ==========================================
# 2. CREDIT (UDHAAR) PARSING TESTS
# ==========================================

def test_parse_credit_item_purchases():
    """Credit purchases with items: 'Ramesh took 2 rice on credit', 'give Ramesh 3 soaps on udhaar'."""
    res1 = KiranaMessageParser.parse("Ramesh took 2 rice on credit")
    assert res1.success is True
    assert res1.intent == "credit"
    assert res1.actions[0].action == "credit_purchase"
    assert res1.actions[0].customer_name == "Ramesh"
    assert res1.actions[0].item_name == "rice"
    assert res1.actions[0].quantity == 2.0

    res2 = KiranaMessageParser.parse("give Ramesh 3 soaps on udhaar")
    assert res2.success is True
    assert res2.actions[0].customer_name == "Ramesh"
    assert res2.actions[0].item_name == "soap"
    assert res2.actions[0].quantity == 3.0


def test_parse_credit_repayments():
    """Repayments: 'Ramesh paid 200', 'received 500 from Ramesh', 'Ramesh repaid 300', currency symbols."""
    res1 = KiranaMessageParser.parse("Ramesh paid 200")
    assert res1.success is True
    assert res1.actions[0].action == "payment"
    assert res1.actions[0].customer_name == "Ramesh"
    assert res1.actions[0].amount == 200.0

    res2 = KiranaMessageParser.parse("received 500 from Ramesh")
    assert res2.success is True
    assert res2.actions[0].customer_name == "Ramesh"
    assert res2.actions[0].amount == 500.0

    res3 = KiranaMessageParser.parse("Ramesh repaid 300")
    assert res3.success is True
    assert res3.actions[0].customer_name == "Ramesh"
    assert res3.actions[0].amount == 300.0

    res_curr1 = KiranaMessageParser.parse("Ramesh paid ₹200")
    assert res_curr1.actions[0].amount == 200.0

    res_curr2 = KiranaMessageParser.parse("Ramesh paid Rs. 500")
    assert res_curr2.actions[0].amount == 500.0


def test_parse_credit_direct_amount():
    """Direct credit amounts: 'Ramesh took 500 on credit', 'udhaar Ramesh 300'."""
    res1 = KiranaMessageParser.parse("Ramesh took 500 on credit")
    assert res1.success is True
    assert res1.actions[0].action == "credit_purchase"
    assert res1.actions[0].customer_name == "Ramesh"
    assert res1.actions[0].amount == 500.0

    res2 = KiranaMessageParser.parse("udhaar Ramesh 300")
    assert res2.success is True
    assert res2.actions[0].customer_name == "Ramesh"
    assert res2.actions[0].amount == 300.0


# ==========================================
# 3. AMBIGUITY & VALIDATION TESTS
# ==========================================

def test_missing_quantity_prompts_clarification():
    """'sold some rice', 'received milk' must not fabricate quantity."""
    res1 = KiranaMessageParser.parse("sold some rice")
    assert res1.success is False
    assert res1.is_ambiguous is True
    assert res1.ambiguity_type == AmbiguityType.MISSING_QUANTITY
    assert "quantity" in res1.clarification_prompt.lower()

    res2 = KiranaMessageParser.parse("received milk")
    assert res2.success is False
    assert res2.ambiguity_type == AmbiguityType.MISSING_QUANTITY


def test_missing_item_prompts_clarification():
    """'add stock', 'stock received' must not fabricate items."""
    res = KiranaMessageParser.parse("add stock")
    assert res.success is False
    assert res.is_ambiguous is True
    assert res.ambiguity_type == AmbiguityType.MISSING_ITEM


def test_missing_action_prompts_clarification():
    """'3 maggi', '2 milk' must not silently assume sale."""
    res = KiranaMessageParser.parse("3 maggi")
    assert res.success is False
    assert res.is_ambiguous is True
    assert res.ambiguity_type == AmbiguityType.MISSING_ACTION
    assert "sell, receive, or damage" in res.clarification_prompt


def test_missing_payment_amount():
    """'Ramesh paid' must not fabricate payment amount."""
    res = KiranaMessageParser.parse("Ramesh paid")
    assert res.success is False
    assert res.is_ambiguous is True
    assert res.ambiguity_type == AmbiguityType.MISSING_AMOUNT
    assert "Ramesh" in res.clarification_prompt


def test_reject_zero_or_negative_quantities():
    """Zero or negative quantities must be rejected."""
    res1 = KiranaMessageParser.parse("sold 0 maggi")
    assert res1.success is False
    assert res1.ambiguity_type == AmbiguityType.INVALID_NUMBER

    res2 = KiranaMessageParser.parse("sold -3 milk")
    assert res2.success is False
    assert res2.ambiguity_type == AmbiguityType.INVALID_NUMBER


def test_empty_and_unrelated_messages():
    """Empty messages and greetings should not parse as transactions."""
    res_empty = KiranaMessageParser.parse("")
    assert res_empty.success is False

    res_greeting = KiranaMessageParser.parse("hello good morning how are you")
    assert res_greeting.success is False
    assert res_greeting.intent == "unrecognized"


# ==========================================
# 4. ROBUSTNESS & DIRECT ENDPOINT TESTS
# ==========================================

def test_case_insensitivity_and_whitespace():
    """Handles noisy punctuation, capitalization, and whitespace."""
    res = KiranaMessageParser.parse("  SOLD   3   MAGGI  ,  2   MILK !  ")
    assert res.success is True
    assert len(res.actions) == 2
    assert res.actions[0].item_name == "maggi"
    assert res.actions[0].quantity == 3.0
    assert res.actions[1].item_name == "milk"
    assert res.actions[1].quantity == 2.0


def test_direct_parser_endpoint(client: TestClient):
    """POST /api/parser/parse returns structured ParseResult."""
    res = client.post("/api/parser/parse", json={"message": "sold 4 maggi and 1 oil"})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["intent"] == "inventory"
    assert len(data["actions"]) == 2
    assert data["actions"][0]["item_name"] == "maggi"
    assert data["actions"][0]["quantity"] == 4.0
    assert data["actions"][1]["item_name"] == "oil"
    assert data["actions"][1]["quantity"] == 1.0


def test_direct_parser_endpoint_ambiguity(client: TestClient):
    """POST /api/parser/parse on ambiguous input returns clarification prompt."""
    res = client.post("/api/parser/parse", json={"message": "sold some rice"})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False
    assert data["is_ambiguous"] is True
    assert "quantity" in data["clarification_prompt"]
