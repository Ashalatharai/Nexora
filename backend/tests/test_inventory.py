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


def test_item_alias_normalization(client: TestClient):
    """Alias 'maggi noodles' resolves cleanly to 'maggi'."""
    payload = {
        "items": [
            {"action": "sold", "item_name": "maggi noodles", "quantity": 2}
        ]
    }
    res = client.post("/api/inventory/transaction", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["updates"][0]["item_name"] == "maggi"
    assert data["updates"][0]["resulting_stock"] == 38.0


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

    inv_res = client.get("/api/inventory")
    items = {i["name"]: i["quantity"] for i in inv_res.json()}
    assert items["maggi"] == 40.0


def test_idempotency_prevents_duplicate_deduction(client: TestClient):
    """Submitting the same idempotency key twice returns replay and does not deduct stock twice."""
    payload = {
        "items": [
            {"action": "sold", "item_name": "maggi", "quantity": 5}
        ],
        "idempotency_key": "unique-client-key-12345"
    }

    # First request
    res1 = client.post("/api/inventory/transaction", json=payload)
    assert res1.status_code == 200
    assert res1.json()["is_duplicate_replay"] is False
    assert res1.json()["updates"][0]["resulting_stock"] == 35.0

    # Second duplicate request (e.g. user double-tapped or network retried)
    res2 = client.post("/api/inventory/transaction", json=payload)
    assert res2.status_code == 200
    assert res2.json()["is_duplicate_replay"] is True

    # Confirm stock was only deducted ONCE (35, not 30)
    inv_res = client.get("/api/inventory")
    maggi = next(i for i in inv_res.json() if i["name"] == "maggi")
    assert maggi["quantity"] == 35.0


def test_transaction_reversal(client: TestClient):
    """Auditably reverse a transaction and restore stock safely."""
    # 1. Sell 10 maggi (40 -> 30)
    res = client.post("/api/inventory/transaction", json={
        "items": [{"action": "sold", "item_name": "maggi", "quantity": 10}]
    })
    assert res.status_code == 200

    # 2. Query transactions to get ID
    from app.models.inventory import InventoryTransaction
    from app.database import SessionLocal
    # Get transaction ID from API through reversal
    # Since first transaction created is ID 1
    rev_res = client.post("/api/inventory/transaction/1/reverse", json={"reason": "Shopkeeper entered wrong number"})
    assert rev_res.status_code == 200
    rev_data = rev_res.json()
    assert rev_data["success"] is True
    assert rev_data["restored_stock"] == 40.0

    # Check stock restored in inventory
    inv_res = client.get("/api/inventory")
    maggi = next(i for i in inv_res.json() if i["name"] == "maggi")
    assert maggi["quantity"] == 40.0

    # Attempting to reverse the same transaction again must be rejected
    dup_rev = client.post("/api/inventory/transaction/1/reverse")
    assert dup_rev.status_code == 400
    assert "already been reversed" in dup_rev.json()["detail"]


def test_reject_zero_or_negative_quantity(client: TestClient):
    """Reject quantity <= 0 with validation error."""
    payload = {
        "items": [
            {"action": "sold", "item_name": "maggi", "quantity": 0}
        ]
    }
    res = client.post("/api/inventory/transaction", json=payload)
    assert res.status_code in [400, 422]
