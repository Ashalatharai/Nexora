import os
from pathlib import Path

# Absolute directory of the backend folder
BACKEND_DIR = Path(__file__).resolve().parent.parent

# Persistent SQLite database file
DEFAULT_DB_PATH = BACKEND_DIR / "kirana.db"

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")

APP_TITLE = "Kirana Chat Ledger API"
APP_DESCRIPTION = (
    "A resilient inventory and credit management REST API for Kirana stores "
    "driven by natural-language chat inputs."
)
APP_VERSION = "1.0.0"

# CORS origins - allow local development frontend ports
CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "*"
]
