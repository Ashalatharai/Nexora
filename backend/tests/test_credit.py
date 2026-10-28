from fastapi.testclient import TestClient


def test_list_customers(client: TestClient):
    """GET /api/credit/customers returns customer list."""
    res = client.get("/api/credit/customers")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 1
    names = [c["name"] for c in data]
    assert "Ramesh" in names


def test_credit_purchase_increases_balance(client: TestClient):
    """Ramesh starts at 350. Takes 150 on credit -> balance 500."""
    payload = {
        "customer_name": "Ramesh",
        "action": "credit_purchase",
        "amount": 150.0,
        "details": "2 rice bags on credit"
    }
    res = client.post("/api/credit/transaction", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["previous_balance"] == 350.0
    assert data["resulting_balance"] == 500.0


def test_credit_purchase_creates_new_customer(client: TestClient):
    """If new customer takes credit, account is created and balance set."""
    payload = {
        "customer_name": "Ganesh",
        "action": "credit_purchase",
        "amount": 200.0,
        "details": "Oil and sugar"
    }
    res = client.post("/api/credit/transaction", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["customer_name"] == "Ganesh"
    assert data["previous_balance"] == 0.0
    assert data["resulting_balance"] == 200.0

    # Verify customer appears in customer list
    c_res = client.get("/api/credit/customers")
    names = [c["name"] for c in c_res.json()]
    assert "Ganesh" in names


def test_payment_reduces_balance(client: TestClient):
    """Ramesh has 350. Pays 200 -> balance becomes 150."""
    payload = {
        "customer_name": "Ramesh",
        "action": "payment",
        "amount": 200.0,
        "details": "Cash payment at shop"
    }
    res = client.post("/api/credit/transaction", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["previous_balance"] == 350.0
    assert data["resulting_balance"] == 150.0
    assert "Ramesh paid ₹200" in data["confirmation"]


def test_credit_idempotency_prevents_duplicate_charge(client: TestClient):
    """Submitting duplicate credit payment with same idempotency key does not deduct twice."""
    payload = {
        "customer_name": "Ramesh",
        "action": "payment",
        "amount": 100.0,
        "idempotency_key": "pay-key-ramesh-777"
    }
    res1 = client.post("/api/credit/transaction", json=payload)
    assert res1.status_code == 200
    assert res1.json()["is_duplicate_replay"] is False
    assert res1.json()["resulting_balance"] == 250.0

    res2 = client.post("/api/credit/transaction", json=payload)
    assert res2.status_code == 200
    assert res2.json()["is_duplicate_replay"] is True

    # Balance is still 250 (not 150)
    c_res = client.get("/api/credit/customers")
    ramesh = next(c for c in c_res.json() if c["name"] == "Ramesh")
    assert ramesh["outstanding_balance"] == 250.0


def test_customer_ledger_reconciliation(client: TestClient):
    """GET /api/credit/customers/{name}/verify recomputes balance from transactions."""
    # 1. Take credit
    client.post("/api/credit/transaction", json={
        "customer_name": "Ramesh",
        "action": "credit_purchase",
        "amount": 100.0
    })
    # 2. Pay debt
    client.post("/api/credit/transaction", json={
        "customer_name": "Ramesh",
        "action": "payment",
        "amount": 50.0
    })

    res = client.get("/api/credit/customers/Ramesh/verify")
    assert res.status_code == 200
    data = res.json()
    assert data["is_consistent"] is True
    assert data["total_purchases"] == 450.0
    assert data["total_payments"] == 50.0
    assert data["current_balance"] == 400.0


def test_reject_payment_exceeding_balance(client: TestClient):
    """Ramesh has 350. Attempting to pay 500 must be rejected."""
    payload = {
        "customer_name": "Ramesh",
        "action": "payment",
        "amount": 500.0
    }
    res = client.post("/api/credit/transaction", json=payload)
    assert res.status_code == 400
    assert "exceeds the outstanding balance" in res.json()["detail"]

    c_res = client.get("/api/credit/customers")
    ramesh = next(c for c in c_res.json() if c["name"] == "Ramesh")
    assert ramesh["outstanding_balance"] == 350.0


def test_reject_payment_for_unknown_customer(client: TestClient):
    """Payment from unknown customer should return 404."""
    payload = {
        "customer_name": "UnknownPerson99",
        "action": "payment",
        "amount": 100.0
    }
    res = client.post("/api/credit/transaction", json=payload)
    assert res.status_code == 404


def test_reject_negative_or_zero_amount(client: TestClient):
    """Payment or credit of 0 or negative must be rejected."""
    payload = {
        "customer_name": "Ramesh",
        "action": "payment",
        "amount": -50.0
    }
    res = client.post("/api/credit/transaction", json=payload)
    assert res.status_code in [400, 422]
