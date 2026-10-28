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
* Low-stock alerts
* Customer credit (Udhaar) management
* Daily sales and inventory summaries
* Supplier reorder messages
* Persistent data storage

## Technology Stack

* Frontend: React and Tailwind CSS
* Backend: Python and FastAPI
* Database: SQLite
* Message Parsing: Rule-based parsing and regular expressions

## Team

Four-member team participating in Byte Race 2026.

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

Run the complete test suite (25 tests covering inventory, credit, alerts, chat, and persistence):
```bash
pytest -v
```

## API Specification

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Service health status check |
| `GET` | `/api/inventory` | List all inventory items and stock levels |
| `POST` | `/api/inventory/transaction` | Atomically apply batch actions (`sold`, `received`, `damaged`, `returned`) |
| `POST` | `/api/inventory/item` | Add new item or configure minimum stock threshold |
| `GET` | `/api/alerts/low-stock` | Retrieve items requiring reordering |
| `GET` | `/api/summary/daily` | End-of-day sales, receipts, damages, and credit movements |
| `GET` | `/api/credit/customers` | Customer Udhaar balances |
| `POST` | `/api/credit/transaction` | Record credit purchase or payment |
| `GET` | `/api/supplier/reorder` | Generate supplier order and WhatsApp click-to-chat URL |
| `POST` | `/api/chat` | Unified chat endpoint (structured actions or raw natural language) |
