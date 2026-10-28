# Kirana Chat Ledger

Kirana Chat Ledger is a modern, chat-driven inventory and customer-credit ledger designed specifically for neighbourhood kirana shops. Shopkeepers can record everyday stock and Udhaar activity in natural language, review business summaries, query live store performance, and dispatch official supplier restock orders via natural language messages with zero tedious form-filling.

The project is a local-development MVP: the React frontend connects to a FastAPI backend, and the backend stores shop data in SQLite. Login and OTP screens are frontend demos; they do not authenticate against a real account service.

---

## Features

- **Chat-Based Shop Updates:** Record sales, deliveries, damaged goods, returns, credit purchases, and Udhaar repayments using natural language messages such as `sold 3 maggi, 2 milk`, `received 20 rice bags`, `Ramesh took 2 rice on credit`, and `Ramesh paid ₹200`.
- **Read-Only Conversational Queries (Zero DB Mutations):** Live stock inquiries (`"How much rice do I have?"`, `"check stock of milk"`), customer debt balance (`"How much does Ramesh owe?"`), and storewide audit queries (`"What items are low on stock?"`, `"What were today's sales?"`, `"Who owes money?"`).
- **Contextual Follow-Ups & Confirmations:** Multi-turn conversational memory tracking active items and customers with a confirmation state machine before committing database mutations.
- **Meta WhatsApp Business Cloud API Integration:** Automated restock draft generation from live low-stock items with direct dispatch via official Meta Graph API v18.0, webhook status receiver, and universal `https://wa.me/` fallback.
- **Inventory Management:** Browse and search products, view stock levels, add products, and adjust stock with atomic transaction rollbacks.
- **Low-Stock Alerts:** Automatically detect `LOW_STOCK` and `OUT_OF_STOCK` conditions against minimum thresholds.
- **Customer Udhaar Management:** Review customer balances, record credit purchases and repayments, with strict audit reconciliation preventing overpayments.
- **Daily Ledger & Reports:** Review end-of-day revenue, payments received, credit extended, and stock movement breakdown.
- **Accessible Responsive Interface:** Clean, high-legibility interface with comfortable typography (15px–32px), 280px sidebar, and 44–46px touch targets on desktop, tablet, and mobile.
- **Demo Sign-In:** Frontend authentication demo with password visibility toggling and demo OTP verification (`123456`).

---

## Technology Stack

| Area | Technology | Purpose |
| --- | --- | --- |
| Frontend | React 18 | Interactive, component-based user interface |
| Development & Build | Vite 6 | Local dev server and production bundling |
| Routing | React Router 6 | Client-side application pages |
| Icons | Lucide React | Interface icons |
| Backend API | Python 3.10+, FastAPI, Uvicorn | High-performance REST API and local dev server |
| Data Validation | Pydantic v2 | API request and response validation contracts |
| Persistence | SQLAlchemy & SQLite | ACID-compliant relational persistence with atomic rollback & idempotency |
| Conversational AI | Deterministic NLP + Optional Gemini API | Entity extraction, contextual intent parsing, and confirmation state machine |
| Messaging | Meta WhatsApp Cloud API v18.0 | Automated supplier reorder dispatch and webhook receiver |
| Automated Tests | pytest & httpx | Backend unit and API test suite (63 passing tests) |

---

## Architecture

```text
Shopkeeper
    │
    ▼
React app (Vite) ── /api requests ──► FastAPI application
    │                                      │
    │                                      ├── Chat router ──► Conversational Parser & Context Memory
    │                                      ├── WhatsApp router ──► Meta Cloud API v18.0 & Webhooks
    │                                      ├── Inventory / alerts / summary routers
    │                                      ├── Credit router
    │                                      └── Services and Pydantic schemas
    │                                                  │
    │                                                  ▼
    │                                           SQLAlchemy ──► SQLite (kirana.db)
    │
    └── Prepared supplier order ──► WhatsApp Cloud API / wa.me click-to-chat fallback
```

---

## Main Project Directories

```text
.
├── backend/
│   ├── app/
│   │   ├── models/       # Inventory, transactions, customers, and credit records
│   │   ├── parser/       # Multi-phase NLP, query recognition, entity extraction, AI fallback
│   │   ├── routers/      # FastAPI endpoint definitions (chat, inventory, credit, whatsapp, summary)
│   │   ├── schemas/      # Pydantic API contracts
│   │   ├── services/     # Inventory, credit, summary, context, and WhatsApp operations
│   │   ├── config.py     # Application, WhatsApp API, and Gemini configuration
│   │   └── database.py   # SQLAlchemy engine, initialization, and seed data
│   ├── tests/            # Automated unit and API test suite (63 tests)
│   ├── requirements.txt
│   └── run.py            # Backend development entry point
├── src/
│   ├── App.jsx           # Frontend routes, app shell, pages, chat assistant, and modals
│   ├── main.jsx          # React entry point
│   └── styles.css        # Responsive design system, typography scale, and components
├── index.html
├── package.json
└── vite.config.js        # Vite configuration and /api development proxy
```

---

## Requirements

- Python 3.10 or newer
- Node.js 18 or newer
- npm

---

## Run Locally

Run the backend and frontend in separate terminals from the repository root.

### 1. Environment Configuration (Optional)

Copy `.env.example` to `.env` to configure WhatsApp Business Cloud API or Gemini API credentials:
```bash
cp .env.example .env
```
*Note: The application functions fully in local fallback mode if `.env` is omitted.*

### 2. Start the Backend

Create and activate a virtual environment, then install backend dependencies:

**Windows PowerShell:**
```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
python backend\run.py
```

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
python backend/run.py
```

On first startup, the backend creates its database tables and seeds sample inventory and customer data if those tables are empty. By default, the SQLite database is stored at `backend/kirana.db`.

* **Swagger UI Documentation:** `http://127.0.0.1:8000/docs`
* **ReDoc Documentation:** `http://127.0.0.1:8000/redoc`

### 3. Start the Frontend

In another terminal, from the repository root:
```bash
npm install
npm run dev
```
The application dashboard will be live at `http://localhost:5173`.

---

## Useful Commands

Run these from the repository root:

```bash
npm run dev                         # Start the Vite development server
npm run build                       # Create the production frontend build in dist/
npm run preview                     # Preview the production frontend
python -m pytest backend/tests -v   # Run all 63 automated tests
```

---

## API Overview

All application endpoints are mounted under `/api`.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Check API health and service version |
| `POST` | `/api/chat` | Conversational NLP assistant with session memory & confirmation flow |
| `GET` | `/api/whatsapp/status` | Meta WhatsApp Cloud API credentials and connection status |
| `GET` | `/api/whatsapp/preview/reorder` | Generate restock order message draft with supplier details |
| `POST` | `/api/whatsapp/send` | Dispatch message via Meta WhatsApp Business Cloud API |
| `GET` | `/api/whatsapp/webhook` | Meta webhook verification handshake (`hub.challenge`) |
| `POST` | `/api/whatsapp/webhook` | Inbound delivery status update receiver |
| `GET` | `/api/inventory` | List all inventory items, stock levels, and alert indicators |
| `POST` | `/api/inventory/item` | Add new item or configure minimum stock threshold |
| `POST` | `/api/inventory/transaction` | Atomically apply batch actions (`sold`, `received`, `damaged`, `returned`) |
| `POST` | `/api/inventory/transaction/{id}/reverse` | Auditably reverse an erroneous transaction with a compensating entry |
| `GET` | `/api/alerts/low-stock` | Retrieve items requiring reordering (`OUT_OF_STOCK` vs `LOW_STOCK`) |
| `GET` | `/api/summary/daily` | End-of-day sales revenue in INR, receipts, damages, and credit cash-flows |
| `GET` | `/api/credit/customers` | List customers and outstanding Udhaar balances |
| `POST` | `/api/credit/transaction` | Record credit purchase or payment |
| `GET` | `/api/credit/customers/{name}/verify` | Reconcile customer balance against transaction history with zero drift |
| `POST` | `/api/parser/parse` | Direct parser endpoint for tokenization, intent recognition, and entities |
| `GET` | `/api/supplier/reorder` | Generate supplier order draft and WhatsApp click-to-chat URL |

---

## Notes

- Login, OTP, and password reset are demo UI flows, not real authentication or account recovery.
- WhatsApp reorders support direct dispatch via Meta Graph API v18.0 when configured, with seamless fallback to `https://wa.me/` click-to-chat links.
- The default development database is SQLite and persists to `backend/kirana.db`.
