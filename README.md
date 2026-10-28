# Kirana Chat Ledger — Byte Race 2026

A modern, chat-driven inventory and credit management system designed specifically for small Indian retail shopkeepers (kirana stores).

Kirana stores need fast, effortless record-keeping during busy store hours. Kirana Chat Ledger allows shopkeepers to record inventory operations and customer Udhaar through natural language messages (or typed/voice input) with zero tedious form-filling.

---

## System Architecture

* **Frontend:** React 18, Vite 6, Tailwind CSS, Lucide Icons, React Router v6.
* **Backend:** Python 3.10+, FastAPI, Uvicorn, SQLAlchemy, SQLite (ACID compliant with atomic batch rollbacks & idempotency).
* **Message Parser:** Deterministic 4-phase NLP parsing engine (Normalization, Intent Matching, Entity Extraction, Ambiguity Resolution) supporting Hinglish/English retail vocabulary.

---

## Core Capabilities

1. **Natural-Language Inventory Updates:**
   - Multi-item batch sales (e.g. `"sold 3 maggi, 2 milk"`).
   - Stock receipts (e.g. `"received 20 rice bags"`).
   - Damaged item write-offs and customer restock returns.
2. **Customer Udhaar (Credit) Management:**
   - Record credit sales directly (e.g. `"Ramesh took 2 rice on credit"`).
   - Record debt repayments (e.g. `"Ramesh paid ₹200"`).
   - Strict audit trails and rejection of overpayments exceeding outstanding dues.
3. **Automated Inventory Alerts & Reorders:**
   - Immediate detection of `LOW_STOCK` and `OUT_OF_STOCK` conditions.
   - 1-click WhatsApp supplier reorder draft generation.
4. **Daily Ledger & Cash Summaries:**
   - End-of-day revenue, payments received, credit extended, and stock movement breakdown.
5. **Interactive Dashboard & Assistant:**
   - Clean, mobile-friendly shopkeeper interface with quick suggestions and voice-ready interaction.

---

## Quickstart & Local Setup

### 1. Prerequisites
* **Python 3.10+**
* **Node.js 18+** and **npm**

### 2. Backend Setup
1. Navigate to the `backend` directory:
   ```bash
   cd backend
   ```
2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the backend development server:
   ```bash
   python run.py
   ```
   The backend API will be running at **`http://127.0.0.1:8000`**.
   * **Swagger UI Documentation:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
   * **ReDoc Documentation:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

### 3. Frontend Setup
1. In the repository root:
   ```bash
   npm install
   ```
2. Start the Vite development server:
   ```bash
   npm run dev
   ```
   The application dashboard will be live at **`http://localhost:5173`**.

---

## Running Automated Tests

### Backend Test Suite
Run all 51 automated unit and integration tests (covering inventory, credit integrity, alerts, daily summaries, parser phases, and SQLite persistence):
```bash
python -m pytest backend/tests -v
```

### Frontend Production Build
```bash
npm run build
```

---

## API Specification

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Service health status check |
| `GET` | `/api/inventory` | List all inventory items, stock levels, and alert indicators |
| `POST` | `/api/inventory/transaction` | Atomically apply batch actions (`sold`, `received`, `damaged`, `returned`) |
| `POST` | `/api/inventory/transaction/{id}/reverse` | Auditably reverse an erroneous transaction with a compensating entry |
| `POST` | `/api/inventory/item` | Add new item or configure minimum stock threshold |
| `GET` | `/api/alerts/low-stock` | Retrieve items requiring reordering (`OUT_OF_STOCK` vs `LOW_STOCK`) |
| `GET` | `/api/summary/daily` | End-of-day sales revenue in INR, receipts, damages, and credit cash-flows |
| `GET` | `/api/credit/customers` | Customer Udhaar balances |
| `POST` | `/api/credit/transaction` | Record credit purchase or payment |
| `GET` | `/api/credit/customers/{name}/verify` | Audit and verify customer balance consistency against transaction history |
| `GET` | `/api/supplier/reorder` | Generate supplier order draft and WhatsApp click-to-chat URL |
| `POST` | `/api/chat` | Unified chat endpoint (structured actions or raw natural language) |
| `POST` | `/api/parser/parse` | Direct parser endpoint for tokenization, intent recognition, and entities |
