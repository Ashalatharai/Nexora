from fastapi.testclient import TestClient


def test_list_inventory(client: TestClient):
    """GET /api/inventory should list all seeded items."""
    res = client.get("/api/inventory")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 5
    names = [i["name"] for i in data]
    assert "maggi" in names
    assert "milk" in names


def test_inventory_single_item_sold(client: TestClient):
    """Sell 3 maggi: stock goes from 40 to 37."""
    payload = {
        "items": [
            {"action": "sold", "item_name": "maggi", "quantity": 3}
        ]
    }
    res = client.post("/api/inventory/transaction", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "Updated: Maggi 40 → 37" in data["confirmation"]
    assert data["updates"][0]["resulting_stock"] == 37.0


def test_inventory_multiple_items_batch(client: TestClient):
    """Support multiple items in one request: sold 3 maggi, 2 milk."""
    payload = {
        "items": [
            {"action": "sold", "item_name": "maggi", "quantity": 3},
            {"action": "sold", "item_name": "milk", "quantity": 2}
        ]
    }
    res = client.post("/api/inventory/transaction", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "Maggi 40 → 37" in data["confirmation"]
    assert "Milk 12 → 10" in data["confirmation"]


def test_inventory_receive_stock(client: TestClient):
    """Received 20 rice bags: stock goes from 25 to 45."""
    payload = {
        "items": [
            {"action": "received", "item_name": "rice", "quantity": 20}
        ]
    }
    res = client.post("/api/inventory/transaction", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["updates"][0]["previous_stock"] == 25.0
    assert data["updates"][0]["resulting_stock"] == 45.0


def test_inventory_damaged_and_returned(client: TestClient):
    """Damaged 1 oil (10 -> 9), Returned 2 soap (20 -> 22)."""
    payload = {
        "items": [
            {"action": "damaged", "item_name": "oil", "quantity": 1},
            {"action": "returned", "item_name": "soap", "quantity": 2}
        ]
    }
    res = client.post("/api/inventory/transaction", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["updates"][0]["resulting_stock"] == 9.0
    assert data["updates"][1]["resulting_stock"] == 22.0


def test_atomic_rollback_on_insufficient_stock(client: TestClient):
    """
    If one item in a batch has insufficient stock, the ENTIRE batch must be rejected.
    Neither item must have its stock changed.
    """
    # maggi has 40, milk has 12. Request 5 maggi (valid) and 50 milk (insufficient).
    payload = {
        "items": [
            {"action": "sold", "item_name": "maggi", "quantity": 5},
            {"action": "sold", "item_name": "milk", "quantity": 50}
        ]
    }
    res = client.post("/api/inventory/transaction", json=payload)
    assert res.status_code == 400
    assert "Insufficient stock for 'Milk'" in res.json()["detail"]

    # Verify that maggi stock remained 40 and was not partially decremented
    inv_res = client.get("/api/inventory")
    items = {i["name"]: i["quantity"] for i in inv_res.json()}
    assert items["maggi"] == 40.0
    assert items["milk"] == 12.0


def test_atomic_rollback_on_nonexistent_item(client: TestClient):
    """If an item does not exist, reject entire batch with no partial updates."""
    payload = {
        "items": [
            {"action": "sold", "item_name": "maggi", "quantity": 5},
            {"action": "sold", "item_name": "non_existent_biscuit_xyz", "quantity": 1}
        ]
    }
    res = client.post("/api/inventory/transaction", json=payload)
    assert res.status_code == 400
    assert "non_existent_biscuit_xyz" in res.json()["detail"]

    # Verify maggi was NOT modified
    inv_res = client.get("/api/inventory")
    items = {i["name"]: i["quantity"] for i in inv_res.json()}
    assert items["maggi"] == 40.0


def test_reject_zero_or_negative_quantity(client: TestClient):
    """Reject quantity <= 0 with validation error."""
    payload = {
        "items": [
            {"action": "sold", "item_name": "maggi", "quantity": 0}
        ]
    }
    res = client.post("/api/inventory/transaction", json=payload)
    assert res.status_code in [400, 422]
