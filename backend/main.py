from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
from typing import Dict, Any

from config import settings
from database import init_db, get_db_connection, dict_from_row, db_transaction
from models import ChatRequest, ChatResponse, ProductCreate, CustomerCreate, PaymentCreate, StockAdjust
from llm_engine import ChatEngine
from parser import RuleParser

# Initialize FastAPI application
app = FastAPI(
    title="Kirana Chat Ledger API",
    description="Natural language ledger & inventory backend for Indian Kirana stores using FastAPI, SQLite & LLM",
    version="2.0.0"
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup event & module-level initialization to ensure database is created & seeded
init_db()

@app.on_event("startup")
def startup_event():
    init_db()

def _get_full_store_state() -> Dict[str, Any]:
    """Compile complete store state formatted for the React frontend."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Shop info
    cursor.execute("SELECT * FROM shop_profile WHERE id = 1")
    shop = dict_from_row(cursor.fetchone()) or {
        "name": "Sharma General Store",
        "owner": "Ramesh Sharma",
        "phone": "+91 98765 43210",
        "city": "Pune",
        "address": "42, Laxmi Road, Pune"
    }

    # Products
    cursor.execute("SELECT * FROM products ORDER BY name ASC")
    products = [
        {
            "id": r["id"],
            "name": r["name"],
            "category": r["category"],
            "price": r["price"],
            "costPrice": r["cost_price"],
            "stock": r["stock"],
            "minStock": r["min_stock"],
            "unit": r["unit"],
            "sku": r["sku"]
        }
        for r in cursor.fetchall()
    ]

    # Customers
    cursor.execute("SELECT * FROM customers ORDER BY due DESC, name ASC")
    customers = [
        {
            "id": r["id"],
            "name": r["name"],
            "phone": r["phone"],
            "due": r["due"],
            "lastActive": r["last_active"],
            "initials": r["initials"],
            "color": r["color"]
        }
        for r in cursor.fetchall()
    ]

    # Transactions
    cursor.execute("SELECT * FROM transactions ORDER BY created_at DESC LIMIT 50")
    transactions = [
        {
            "id": r["id"],
            "customerId": r["customer_id"] or "",
            "title": r["title"],
            "detail": r["detail"],
            "amount": r["amount"],
            "profit": r["profit"],
            "type": r["type"],
            "time": r["time"],
            "date": r["date"]
        }
        for r in cursor.fetchall()
    ]

    # Suppliers
    cursor.execute("SELECT * FROM suppliers")
    suppliers = [dict_from_row(r) for r in cursor.fetchall()]

    # Aggregations
    cursor.execute("SELECT COALESCE(SUM(amount), 0.0) as today_sales FROM transactions WHERE date = 'Today' AND type = 'sale'")
    today_sales = cursor.fetchone()["today_sales"]

    cursor.execute("SELECT COALESCE(SUM(profit), 0.0) as today_profit FROM transactions WHERE date = 'Today' AND type = 'sale'")
    today_profit = cursor.fetchone()["today_profit"]

    cursor.execute("SELECT COALESCE(SUM(due), 0.0) as total_udhaar FROM customers")
    total_udhaar = cursor.fetchone()["total_udhaar"]

    conn.close()

    return {
        "shop": shop,
        "products": products,
        "customers": customers,
        "transactions": transactions,
        "suppliers": suppliers,
        "todaySales": today_sales,
        "todayProfit": today_profit,
        "totalUdhaar": total_udhaar
    }


# -----------------------------------------------------------------------------
# 1. Health Check
# -----------------------------------------------------------------------------
@app.get("/api/health")
def health_check():
    """Verify backend status, database connectivity, and LLM readiness."""
    db_ok = False
    try:
        conn = get_db_connection()
        conn.execute("SELECT 1").fetchone()
        conn.close()
        db_ok = True
    except Exception:
        db_ok = False

    llm_provider = "none"
    if settings.GEMINI_API_KEY:
        llm_provider = f"gemini ({settings.GEMINI_MODEL})"
    elif settings.OPENAI_API_KEY:
        llm_provider = "openai (gpt-4o-mini)"
    else:
        llm_provider = "smart-local-nlp (built-in)"

    return {
        "status": "ok" if db_ok else "degraded",
        "app": "Kirana Chat Ledger",
        "framework": "FastAPI",
        "database": "connected" if db_ok else "error",
        "llm_enabled": bool(settings.GEMINI_API_KEY or settings.OPENAI_API_KEY),
        "llm_provider": llm_provider,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# -----------------------------------------------------------------------------
# 2. Store State
# -----------------------------------------------------------------------------
@app.get("/api/store/state")
def get_store_state():
    """Returns the complete, authoritative SQLite store state."""
    return _get_full_store_state()


# -----------------------------------------------------------------------------
# 3. Upgraded Natural Language Chat
# -----------------------------------------------------------------------------
@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Upgraded chat interface:
    - Flexible natural language understanding & conversational memory
    - Live database queries for business questions (sales, profit, stock, udhaar)
    - Safe transaction execution via rule parser
    - Clarification questions when input is ambiguous
    - Returns updated store_state for seamless frontend synchronization
    """
    res = await ChatEngine.process_chat(request.message, request.session_id)
    # Include updated store state so frontend instantly reflects changes
    res["store_state"] = _get_full_store_state()
    return res


# -----------------------------------------------------------------------------
# 4. Direct Entity APIs (for forms & modals)
# -----------------------------------------------------------------------------
@app.post("/api/products")
def create_product(product: ProductCreate):
    pid = f"p{int(datetime.now().timestamp() * 1000)}"
    sku = f"NEW-{pid[-4:]}"
    cost_price = product.cost_price if product.cost_price and product.cost_price > 0 else round(product.price * 0.82, 2)

    with db_transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO products (id, name, category, price, cost_price, stock, min_stock, unit, sku)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (pid, product.name.strip(), product.category, product.price, cost_price, product.stock, product.min_stock, product.unit, sku))

    return {"success": True, "product_id": pid, "store_state": _get_full_store_state()}


@app.post("/api/customers")
def create_customer(customer: CustomerCreate):
    res = RuleParser.execute_create_customer(customer.name, customer.phone or "")
    if not res["success"]:
        return {
            "success": False,
            "error": res["error"],
            "store_state": _get_full_store_state()
        }
    return {
        "success": True,
        "customer_id": res["customer_id"],
        "customer": res,
        "store_state": _get_full_store_state()
    }


@app.post("/api/transactions/payment")
def record_payment(payment: PaymentCreate):
    identifier = payment.customer_id or payment.customer_name
    if not identifier:
        raise HTTPException(status_code=400, detail="customer_id or customer_name is required")

    res = RuleParser.execute_payment(identifier, payment.amount, payment.notes or "")
    if not res["success"]:
        raise HTTPException(status_code=400, detail=res["error"])

    return {"success": True, "payment": res, "store_state": _get_full_store_state()}


@app.post("/api/inventory/adjust")
def adjust_inventory(adjust: StockAdjust):
    with db_transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products WHERE id = ?", (adjust.product_id,))
        p = cursor.fetchone()
        if not p:
            raise HTTPException(status_code=404, detail="Product not found")

        new_stock = max(0, p["stock"] + adjust.adjustment)
        cursor.execute("UPDATE products SET stock = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_stock, adjust.product_id))

    return {"success": True, "new_stock": new_stock, "store_state": _get_full_store_state()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=True)
