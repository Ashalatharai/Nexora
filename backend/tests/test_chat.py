from fastapi.testclient import TestClient


def test_chat_structured_actions_from_parser_module(client: TestClient):
    """Verify that when message-parser sends structured actions, they execute seamlessly."""
    payload = {
        "message": "sold 3 maggi, 2 milk",
        "actions": [
            {
                "domain": "inventory",
                "action": "sold",
                "item_name": "maggi",
                "quantity": 3.0
            },
            {
                "domain": "inventory",
                "action": "sold",
                "item_name": "milk",
                "quantity": 2.0
            }
        ]
    }
    res = client.post("/api/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "Maggi 40 → 37" in data["reply"]
    assert "Milk 12 → 10" in data["reply"]
    assert len(data["inventory_updates"]) == 2


def test_chat_natural_language_inventory_sale(client: TestClient):
    """Natural message: 'sold 3 maggi, 2 milk' without pre-parsed actions."""
    payload = {
        "message": "sold 3 maggi, 2 milk"
    }
    res = client.post("/api/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "Maggi 40 → 37" in data["reply"]
    assert "Milk 12 → 10" in data["reply"]


def test_chat_natural_language_received(client: TestClient):
    """Natural message: 'received 20 rice bags'."""
    payload = {
        "message": "received 20 rice bags"
    }
    res = client.post("/api/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "Rice 25 → 45" in data["reply"]


def test_chat_natural_language_damaged(client: TestClient):
    """Natural message: 'damaged 1 oil'."""
    payload = {
        "message": "damaged 1 oil"
    }
    res = client.post("/api/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "Oil 10 → 9" in data["reply"]


def test_chat_natural_language_credit_payment(client: TestClient):
    """Natural message: 'Ramesh paid ₹200'."""
    payload = {
        "message": "Ramesh paid ₹200"
    }
    res = client.post("/api/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "Ramesh paid ₹200" in data["reply"]
    assert "₹350 → ₹150" in data["reply"]


def test_chat_unrecognized_message_guidance(client: TestClient):
    """When a message cannot be parsed, reply with helpful suggestions."""
    payload = {
        "message": "good morning how is the weather today"
    }
    res = client.post("/api/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False
    assert "I couldn't understand that command" in data["reply"]
