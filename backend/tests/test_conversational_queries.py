import pytest
from fastapi.testclient import TestClient
from app.services.context_service import ContextManager


def test_read_only_stock_query_does_not_mutate_db(client: TestClient):
    """'How much rice do I have?' returns stock info and does not alter inventory."""
    # Get initial stock
    inv_res = client.get("/api/inventory")
    initial_items = {it["name"].lower(): it["quantity"] for it in inv_res.json()}
    initial_rice = initial_items.get("rice")

    # Ask stock query
    res = client.post("/api/chat", json={"message": "How much rice do I have?", "session_id": "test-session-query"})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["intent"] == "query"
    assert "Rice" in data["reply"]
    assert str(int(initial_rice)) in data["reply"]

    # Verify inventory in DB remains strictly identical
    inv_after = client.get("/api/inventory")
    after_items = {it["name"].lower(): it["quantity"] for it in inv_after.json()}
    assert after_items.get("rice") == initial_rice


def test_read_only_customer_debt_query_does_not_mutate_db(client: TestClient):
    """'How much does Ramesh owe?' returns balance and does not alter ledger."""
    # Ramesh is pre-seeded with 350.0 balance in conftest
    cust_res = client.get("/api/credit/customers")
    ramesh = next(c for c in cust_res.json() if c["name"].lower() == "ramesh")
    initial_balance = ramesh["outstanding_balance"]

    # Ask balance query
    res = client.post("/api/chat", json={"message": "How much does Ramesh owe?", "session_id": "test-session-debt"})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["intent"] == "query"
    assert "Ramesh" in data["reply"]
    assert str(int(initial_balance)) in data["reply"]

    # Verify ledger remains identical
    cust_after = client.get("/api/credit/customers")
    ramesh_after = next(c for c in cust_after.json() if c["name"].lower() == "ramesh")
    assert ramesh_after["outstanding_balance"] == initial_balance


def test_read_only_low_stock_and_daily_summary_queries(client: TestClient):
    """'What items are low on stock?' and 'What were today\'s sales?' execute read-only."""
    res_low = client.post("/api/chat", json={"message": "what items are low on stock?", "session_id": "test-session-low"})
    assert res_low.status_code == 200
    assert res_low.json()["intent"] == "query"

    res_sum = client.post("/api/chat", json={"message": "what were today's sales?", "session_id": "test-session-sum"})
    assert res_sum.status_code == 200
    assert res_sum.json()["intent"] == "query"
    assert "Summary" in res_sum.json()["reply"] or "Gross Sales" in res_sum.json()["reply"]


def test_contextual_follow_up_with_confirmation(client: TestClient):
    """
    Turn 1: 'How much rice do I have?' -> sets last_item_name = 'rice'.
    Turn 2: 'Sell 2' -> prompts confirmation without mutating DB yet.
    Turn 3: 'yes' -> executes deduction atomically.
    """
    sid = "test-session-confirm-flow"
    ContextManager.reset_session(sid)

    # Turn 1: Ask stock
    res1 = client.post("/api/chat", json={"message": "check stock of rice", "session_id": sid})
    assert res1.status_code == 200
    assert res1.json()["intent"] == "query"

    # Get current stock
    inv1 = client.get("/api/inventory")
    rice1 = next(it for it in inv1.json() if it["name"].lower() == "rice")["quantity"]

    # Turn 2: Contextual follow-up 'Sell 2'
    res2 = client.post("/api/chat", json={"message": "sell 2", "session_id": sid})
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["success"] is True
    assert data2["intent"] == "confirmation_pending"
    assert "Do you want to record sold of 2 Rice" in data2["reply"]

    # Verify stock has NOT changed before confirmation
    inv2 = client.get("/api/inventory")
    rice2 = next(it for it in inv2.json() if it["name"].lower() == "rice")["quantity"]
    assert rice2 == rice1

    # Turn 3: User confirms with 'yes'
    res3 = client.post("/api/chat", json={"message": "yes", "session_id": sid})
    assert res3.status_code == 200
    data3 = res3.json()
    assert data3["success"] is True
    assert "Confirmed" in data3["reply"]

    # Verify stock is now decremented by 2
    inv3 = client.get("/api/inventory")
    rice3 = next(it for it in inv3.json() if it["name"].lower() == "rice")["quantity"]
    assert rice3 == rice1 - 2.0


def test_contextual_follow_up_with_cancellation(client: TestClient):
    """
    Turn 1: Ask about Ramesh.
    Turn 2: 'He paid 100' -> prompts confirmation.
    Turn 3: 'no' -> cancels transaction; balance remains unchanged.
    """
    sid = "test-session-cancel-flow"
    ContextManager.reset_session(sid)

    # Turn 1: Ask about Ramesh
    res1 = client.post("/api/chat", json={"message": "How much does Ramesh owe?", "session_id": sid})
    assert res1.status_code == 200
    assert "Ramesh" in res1.json()["reply"]

    # Turn 2: 'He paid 100'
    res2 = client.post("/api/chat", json={"message": "he paid 100", "session_id": sid})
    assert res2.status_code == 200
    assert res2.json()["intent"] == "confirmation_pending"
    assert "Ramesh" in res2.json()["reply"]

    # Turn 3: 'no'
    res3 = client.post("/api/chat", json={"message": "no", "session_id": sid})
    assert res3.status_code == 200
    assert "Cancelled" in res3.json()["reply"]

    # Verify balance was not changed
    cust_res = client.get("/api/credit/customers")
    ramesh = next(c for c in cust_res.json() if c["name"].lower() == "ramesh")
    assert ramesh["outstanding_balance"] == 350.0


def test_missing_entity_without_context_prompts_ambiguity(client: TestClient):
    """'sell 5' or 'paid 200' with fresh session must prompt user to specify item or customer."""
    sid = "test-session-empty-ctx"
    ContextManager.reset_session(sid)

    res_item = client.post("/api/chat", json={"message": "sell 5", "session_id": sid})
    assert res_item.status_code == 200
    assert res_item.json()["success"] is False
    assert "specify which item" in res_item.json()["reply"]

    res_cust = client.post("/api/chat", json={"message": "paid 200", "session_id": sid})
    assert res_cust.status_code == 200
    assert res_cust.json()["success"] is False
    assert "specify who made the payment" in res_cust.json()["reply"]
