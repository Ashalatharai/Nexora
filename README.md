# Kirana Chat Ledger

A chat-based inventory and credit management system designed for small kirana stores.

## Problem Statement

Small retail shopkeepers often manage inventory, daily sales, stock receipts, damaged goods, and customer credit manually. This makes stock tracking and credit management difficult.

## Proposed Solution

Kirana Chat Ledger allows shopkeepers to record inventory operations and customer credit through simple, natural-language messages.

## Core Features

* Natural-language inventory updates
* Multiple products in a single message
* Stock tracking for sales, receipts, damage, and returns
* Low-stock and out-of-stock alerts
* Customer credit (Udhaar) management with audit trail
* Daily sales and inventory summaries with gross sales revenue calculation
* Supplier reorder messages with direct WhatsApp click-to-chat links
* Persistent SQLite database storage with idempotency safeguards
* Transaction reversal with compensating audit records

## Technology Stack

* Frontend: React and Tailwind CSS
* Backend: Python and FastAPI
* Database: SQLite and SQLAlchemy
* Message Parsing: Rule-based parsing and regular expressions

## Team

Four-member team participating in Byte Race 2026.

## Inventory & Credit Policies

1. **Returns Policy:**
   * `returned`: Used for customer returns where items are inspected, verified sellable, and restocked into active inventory (`+quantity`).
   * `damaged`: Used when goods are received damaged or customer-returned goods cannot be resold (`-quantity`).
2. **Customer Udhaar Integrity:**
   * Customer balances are maintained in synchronization with immutable credit ledger records. Every opening balance, purchase, and payment produces an auditable transaction.
   * Overpayments exceeding the outstanding debt are strictly rejected.
3. **Idempotency Safeguard:**
   * All inventory and credit endpoints accept an optional `idempotency_key` to prevent accidental double-billing or double-deduction on mobile network retries.

## Setup & Running the Backend

### Prerequisites
* Python 3.10+
* pip

### Installation

1. Navigate to the `backend` folder:
   ```bash
   cd backend
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Starting the Server

Run the development server:
```bash
python run.py
```
Or with Uvicorn directly:
```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

* **Interactive API Documentation (Swagger UI):** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* **Alternative API Documentation (ReDoc):** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

### Running Automated Tests

Run the complete test suite (33 tests covering inventory, credit, alerts, chat, reversal, and persistence):
```bash
pytest -v
```

## API Specification

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Service health status check |
| `GET` | `/api/inventory` | List all inventory items, stock levels, and alert indicators |
| `POST` | `/api/inventory/transaction` | Atomically apply batch actions (`sold`, `received`, `damaged`, `returned`) |
| `POST` | `/api/inventory/transaction/{id}/reverse` | Auditably reverse an erroneous transaction with a compensating entry |
| `POST` | `/api/inventory/item` | Add new item or configure minimum stock threshold |
| `GET` | `/api/alerts/low-stock` | Retrieve items requiring reordering (categorized as OUT_OF_STOCK vs LOW_STOCK) |
| `GET` | `/api/summary/daily` | End-of-day sales revenue in INR, receipts, damages, and credit cash-flows |
| `GET` | `/api/credit/customers` | Customer Udhaar balances |
| `POST` | `/api/credit/transaction` | Record credit purchase or payment |
| `GET` | `/api/credit/customers/{name}/verify` | Audit and verify customer balance consistency against transaction history |
| `GET` | `/api/supplier/reorder` | Generate supplier order draft and WhatsApp click-to-chat URL |
| `POST` | `/api/chat` | Unified chat endpoint (structured actions or raw natural language) |
