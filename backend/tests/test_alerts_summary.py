from fastapi.testclient import TestClient


def test_low_stock_alerts_and_whatsapp_link(client: TestClient):
    """
    Milk threshold is 5. Stock is 12.
    Sell 8 milk -> 4 remaining <= 5 threshold -> triggers low stock!
    """
    # Sell 8 milk
    client.post("/api/inventory/transaction", json={
        "items": [{"action": "sold", "item_name": "milk", "quantity": 8}]
    })

    res = client.get("/api/alerts/low-stock")
    assert res.status_code == 200
    data = res.json()
    assert data["total_low_stock"] >= 1
    low_names = [i["name"] for i in data["items"]]
    assert "Milk" in low_names

    # Check WhatsApp link format
    assert "whatsapp_url" in data
    assert data["whatsapp_url"].startswith("https://wa.me/?text=")
    assert "Milk" in data["supplier_message"]


def test_supplier_reorder_with_phone_number(client: TestClient):
    """Passing a specific supplier phone formats https://wa.me/<number>?text=... correctly."""
    # Trigger low stock for oil (10 -> 2, min threshold 3)
    client.post("/api/inventory/transaction", json={
        "items": [{"action": "sold", "item_name": "oil", "quantity": 8}]
    })

    res = client.get("/api/supplier/reorder?phone=919876543210")
    assert res.status_code == 200
    data = res.json()
    assert data["supplier_phone"] == "919876543210"
    assert data["whatsapp_url"].startswith("https://wa.me/919876543210?text=")
    assert "Oil" in data["message_text"]


def test_daily_summary_aggregation(client: TestClient):
    """Record multiple transactions and check GET /api/summary/daily aggregation."""
    # 1. Sell items
    client.post("/api/inventory/transaction", json={
        "items": [
            {"action": "sold", "item_name": "maggi", "quantity": 4},
            {"action": "sold", "item_name": "milk", "quantity": 2}
        ]
    })
    # 2. Receive items
    client.post("/api/inventory/transaction", json={
        "items": [
            {"action": "received", "item_name": "rice", "quantity": 10}
        ]
    })
    # 3. Credit payment
    client.post("/api/credit/transaction", json={
        "customer_name": "Ramesh",
        "action": "payment",
        "amount": 100.0
    })

    res = client.get("/api/summary/daily")
    assert res.status_code == 200
    data = res.json()

    assert data["total_inventory_actions"] >= 3
    sold_items = {s["item_name"]: s["total_quantity"] for s in data["items_sold"]}
    assert sold_items.get("Maggi") == 4.0
    assert sold_items.get("Milk") == 2.0

    received_items = {s["item_name"]: s["total_quantity"] for s in data["items_received"]}
    assert received_items.get("Rice") == 10.0

    assert data["credit_summary"]["total_payments_received_amount"] >= 100.0
    assert len(data["current_stock_overview"]) >= 5
