# Kirana Chat Ledger

Kirana Chat Ledger is a chat-driven inventory and customer-credit ledger for neighbourhood kirana shops. Shopkeepers can record everyday stock and Udhaar activity in natural language, review business summaries, and prepare supplier orders for WhatsApp.

The project is a local-development MVP: the React frontend connects to a FastAPI backend, and the backend stores shop data in SQLite. Login and OTP screens are frontend demos; they do not authenticate against a real account service.

## Features

- **Chat-based shop updates:** Record sales, deliveries, damaged goods, returns, credit purchases, and Udhaar repayments using messages such as `sold 3 maggi, 2 milk`, `received 20 rice bags`, `Ramesh took 2 rice on credit`, and `Ramesh paid ₹200`.
- **Inventory management:** Browse and search products, view stock levels, add products, and adjust stock.
- **Low-stock alerts:** See products below their minimum stock levels and identify out-of-stock items.
- **Supplier ordering:** Type an order such as `Order 20 Maggi packets` in the assistant to prepare an order draft. Review the supplier and order, then open a prefilled WhatsApp message. A supplier phone number is optional: without one, WhatsApp opens its contact picker. Messages are not sent automatically.
- **Customer Udhaar:** Review customer balances, record credit purchases and payments, and see customer activity.
- **Transactions and reports:** Review ledger activity, daily sales summaries, stock movements, and credit collections.
- **Responsive interface:** Use the dashboard and assistant on desktop, tablet, or mobile.
- **Demo sign-in:** The login and OTP flows are frontend-only. Any valid-looking email or phone number and a password of at least six characters can enter the demo. The demo OTP is `123456`.

## Technology

| Area | Technology | Purpose |
| --- | --- | --- |
| Frontend | React 18 | Interactive, component-based user interface |
| Development and build | Vite 6 | Local dev server and production bundling |
| Routing | React Router 6 | Client-side application pages |
| Icons | Lucide React | Interface icons |
| Backend API | Python, FastAPI, Uvicorn | REST API and local development server |
| Data validation | Pydantic | API request and response schemas |
| Persistence | SQLAlchemy and SQLite | Relational models and local database |
| Tests | pytest and httpx | Backend unit and API tests |

The message parser is deterministic: it normalizes text, checks for ambiguity, identifies an intent, extracts entities, and returns structured actions. The chat API executes those actions through inventory and credit services. Supplier-order chat requests are prepared in the frontend and handed off to WhatsApp through a prefilled `wa.me` link; this is not a WhatsApp API integration.

## Architecture

```text
Shopkeeper
    │
    ▼
React app (Vite) ── /api requests ──► FastAPI application
    │                                      │
    │                                      ├── Chat router ──► Message parser
    │                                      ├── Inventory / alerts / summary routers
    │                                      ├── Credit router
    │                                      └── Services and Pydantic schemas
    │                                                  │
    │                                                  ▼
    │                                           SQLAlchemy ──► SQLite
    │
    └── Prepared supplier order ──► WhatsApp click-to-chat link
```

### Main project directories

```text
.
├── backend/
│   ├── app/
│   │   ├── models/       # Inventory, transactions, customers, and credit records
│   │   ├── parser/       # Text normalization, intent/entity parsing, ambiguity checks
│   │   ├── routers/      # FastAPI endpoint definitions
│   │   ├── schemas/      # Pydantic API contracts
│   │   ├── services/     # Inventory, credit, and summary business operations
│   │   ├── config.py     # Application and database configuration
│   │   └── database.py   # SQLAlchemy engine, initialization, and seed data
│   ├── tests/            # Backend unit and API tests
│   ├── requirements.txt
│   └── run.py            # Backend development entry point
├── src/
│   ├── App.jsx           # Frontend routes, app shell, pages, and interactions
│   ├── main.jsx          # React entry point
│   └── styles.css        # Responsive design system and component styles
├── index.html
├── package.json
└── vite.config.js        # Vite configuration and /api development proxy
```

## Requirements

- Python 3.10 or newer
- Node.js 18 or newer
- npm

## Run locally

Run the backend and frontend in separate terminals from the repository root.

### 1. Start the backend

Create and activate a virtual environment, then install the backend dependencies:

**Windows PowerShell**

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
python backend\run.py
```

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
python backend/run.py
```

The API is available at `http://127.0.0.1:8000`. Interactive API documentation is at `http://127.0.0.1:8000/docs`, with ReDoc at `http://127.0.0.1:8000/redoc`.

On first startup, the backend creates its database tables and seeds sample inventory and customer data if those tables are empty. By default, the SQLite database is stored at `backend/kirana.db`. Set the `DATABASE_URL` environment variable before starting the backend to use a different SQLAlchemy database URL.

### 2. Start the frontend

In another terminal, from the repository root:

```sh
npm install
npm run dev
```

Open `http://localhost:5173`. Vite proxies requests made to `/api` to the backend at `http://127.0.0.1:8000`; keep the backend running for chat, inventory, customer, and summary API features.

## Useful commands

Run these from the repository root:

```sh
npm run dev                         # Start the Vite development server
npm run build                       # Create the production frontend in dist/
npm run preview                     # Preview the production frontend
python -m pytest backend/tests -v   # Run the backend test suite
```

## API overview

All application endpoints are mounted under `/api`.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Check API health |
| `GET` | `/api/inventory` | List inventory and stock status |
| `POST` | `/api/inventory/item` | Add or configure an inventory item |
| `POST` | `/api/inventory/transaction` | Apply inventory actions such as sold, received, damaged, or returned |
| `POST` | `/api/inventory/transaction/{id}/reverse` | Reverse an inventory transaction |
| `GET` | `/api/alerts/low-stock` | Retrieve low-stock and out-of-stock alerts |
| `GET` | `/api/supplier/reorder` | Generate a reorder draft and WhatsApp URL |
| `GET` | `/api/summary/daily` | Get sales, stock movement, and credit summary |
| `GET` | `/api/credit/customers` | List customers and outstanding balances |
| `POST` | `/api/credit/transaction` | Record a credit purchase or payment |
| `GET` | `/api/credit/customers/{name}/verify` | Verify a customer balance against transaction history |
| `POST` | `/api/chat` | Parse and process a natural-language shop update |
| `POST` | `/api/parser/parse` | Parse a message and return structured actions |

For exact request and response schemas, use the interactive Swagger documentation at `/docs`.

## Notes

- Login, OTP, and password reset are demo UI flows, not real authentication or account recovery.
- WhatsApp handoff opens an external click-to-chat link with a draft message. The shopkeeper reviews and sends the message in WhatsApp.
- The default development database is local and is intended for development/demo use.
