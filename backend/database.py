import sqlite3
import os
from contextlib import contextmanager
from datetime import datetime
from config import settings

def get_db_connection(db_path: str = None):
    path = db_path or settings.DATABASE_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

@contextmanager
def db_transaction(db_path: str = None):
    conn = get_db_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db(db_path: str = None):
    path = db_path or settings.DATABASE_PATH
    conn = get_db_connection(path)
    cursor = conn.cursor()

    cursor.executescript("""
    -- 1. Shop profile
    CREATE TABLE IF NOT EXISTS shop_profile (
        id INTEGER PRIMARY KEY DEFAULT 1,
        name TEXT NOT NULL,
        owner TEXT NOT NULL,
        phone TEXT NOT NULL,
        city TEXT NOT NULL,
        address TEXT NOT NULL
    );

    -- 2. Products Table
    CREATE TABLE IF NOT EXISTS products (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL COLLATE NOCASE,
        category TEXT NOT NULL,
        price REAL NOT NULL CHECK (price >= 0),
        cost_price REAL NOT NULL DEFAULT 0.0 CHECK (cost_price >= 0),
        stock INTEGER NOT NULL CHECK (stock >= 0),
        min_stock INTEGER NOT NULL DEFAULT 10 CHECK (min_stock >= 0),
        unit TEXT NOT NULL DEFAULT 'packet',
        sku TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- 3. Customers Table
    CREATE TABLE IF NOT EXISTS customers (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL COLLATE NOCASE,
        phone TEXT DEFAULT '',
        due REAL NOT NULL DEFAULT 0.0 CHECK (due >= 0),
        last_active TEXT DEFAULT 'Today',
        initials TEXT DEFAULT '',
        color TEXT DEFAULT 'mint',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- 4. Transactions Table
    CREATE TABLE IF NOT EXISTS transactions (
        id TEXT PRIMARY KEY,
        customer_id TEXT REFERENCES customers(id) ON DELETE SET NULL,
        title TEXT NOT NULL,
        detail TEXT NOT NULL,
        amount REAL NOT NULL CHECK (amount >= 0),
        profit REAL NOT NULL DEFAULT 0.0,
        type TEXT NOT NULL CHECK (type IN ('sale', 'credit', 'payment', 'restock')),
        time TEXT NOT NULL,
        date TEXT NOT NULL,
        raw_query TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- 5. Suppliers Table
    CREATE TABLE IF NOT EXISTS suppliers (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        initials TEXT DEFAULT '',
        color TEXT DEFAULT 'mint',
        delivery TEXT DEFAULT 'Next-day delivery',
        products INTEGER DEFAULT 0,
        minimum REAL DEFAULT 500
    );

    -- 6. Chat History (Session Memory)
    CREATE TABLE IF NOT EXISTS chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        role TEXT NOT NULL,
        text TEXT NOT NULL,
        action_taken TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Performance Indexes
    CREATE INDEX IF NOT EXISTS idx_products_name ON products(name);
    CREATE INDEX IF NOT EXISTS idx_customers_name ON customers(name);
    CREATE INDEX IF NOT EXISTS idx_transactions_created ON transactions(created_at);
    CREATE INDEX IF NOT EXISTS idx_chat_session ON chat_history(session_id);
    """)

    # Seed initial data if empty
    cursor.execute("SELECT COUNT(*) AS count FROM products")
    if cursor.fetchone()["count"] == 0:
        _seed_initial_data(cursor)

    conn.commit()
    conn.close()

def _seed_initial_data(cursor):
    # Shop profile
    cursor.execute("""
        INSERT OR REPLACE INTO shop_profile (id, name, owner, phone, city, address)
        VALUES (1, 'Sharma General Store', 'Ramesh Sharma', '+91 98765 43210', 'Pune', '42, Laxmi Road, Pune')
    """)

    # Products with cost_price to calculate true profit!
    products = [
        ("p1", "Amul Taaza Milk", "Dairy", 28.0, 24.0, 18, 20, "packet", "DAI-001"),
        ("p2", "Maggi 2-Minute Noodles", "Snacks", 14.0, 11.5, 42, 15, "packet", "SNK-014"),
        ("p3", "Tata Salt", "Essentials", 24.0, 19.0, 8, 12, "packet", "ESS-004"),
        ("p4", "Fortune Sunflower Oil", "Grocery", 145.0, 125.0, 26, 10, "litre", "GRC-008"),
        ("p5", "Aashirvaad Atta", "Grocery", 255.0, 220.0, 14, 8, "kg", "GRC-011"),
        ("p6", "Parle-G Biscuits", "Snacks", 10.0, 8.0, 64, 20, "packet", "SNK-002"),
        ("p7", "India Gate Basmati Rice", "Grocery", 120.0, 98.0, 6, 10, "kg", "GRC-016"),
        ("p8", "Surf Excel Easy Wash", "Household", 38.0, 31.0, 31, 10, "packet", "HOU-003"),
        ("p9", "Amul Butter", "Dairy", 58.0, 50.0, 12, 8, "pack", "DAI-009"),
        ("p10", "Good Day Cookies", "Snacks", 20.0, 16.0, 27, 12, "packet", "SNK-006")
    ]
    cursor.executemany("""
        INSERT INTO products (id, name, category, price, cost_price, stock, min_stock, unit, sku)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, products)

    # Customers
    customers = [
        ("c1", "Ramesh Patil", "+91 98220 11234", 1250.0, "Today", "RP", "lavender"),
        ("c2", "Sunita Deshmukh", "+91 97654 22411", 840.0, "Today", "SD", "peach"),
        ("c3", "Amit Kulkarni", "+91 98900 55123", 560.0, "Yesterday", "AK", "blue"),
        ("c4", "Meena Joshi", "+91 98230 99887", 2100.0, "Yesterday", "MJ", "mint"),
        ("c5", "Vikram More", "+91 94220 77331", 350.0, "2 days ago", "VM", "rose"),
        ("c6", "Kavita Shah", "+91 98901 34567", 0.0, "Today", "KS", "sand"),
        ("c7", "Deeksha", "+91 98221 55678", 0.0, "Today", "DB", "mint")
    ]
    cursor.executemany("""
        INSERT INTO customers (id, name, phone, due, last_active, initials, color)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, customers)

    # Transactions
    transactions = [
        ("t1", "c1", "Daily groceries", "Ramesh Patil · 3 items", 285.0, 48.0, "credit", "10:42 AM", "Today"),
        ("t2", None, "UPI payment", "Walk-in customer", 620.0, 110.0, "sale", "10:18 AM", "Today"),
        ("t3", "c2", "Credit payment received", "Sunita Deshmukh · UPI", 500.0, 0.0, "payment", "9:56 AM", "Today"),
        ("t4", None, "Milk & essentials", "Cash · 4 items", 182.0, 32.0, "sale", "9:32 AM", "Today"),
        ("t5", "c4", "Monthly groceries", "Meena Joshi · 6 items", 740.0, 125.0, "credit", "Yesterday", "Yesterday"),
        ("t6", None, "Cash sale", "Walk-in customer", 450.0, 80.0, "sale", "Yesterday", "Yesterday")
    ]
    cursor.executemany("""
        INSERT INTO transactions (id, customer_id, title, detail, amount, profit, type, time, date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, transactions)

    # Suppliers
    suppliers = [
        ("s1", "Shree Dairy Suppliers", "Dairy & milk", "SD", "mint", "Same-day delivery", 4, 500),
        ("s2", "Maharashtra Grocery Co.", "Grocery & staples", "MG", "sand", "Next-day delivery", 12, 1000),
        ("s3", "Pune General Distributors", "Snacks & household", "PG", "lavender", "Next-day delivery", 8, 750)
    ]
    cursor.executemany("""
        INSERT INTO suppliers (id, name, category, initials, color, delivery, products, minimum)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, suppliers)

def dict_from_row(row):
    return dict(row) if row else None

