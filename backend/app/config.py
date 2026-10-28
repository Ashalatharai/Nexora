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

# WhatsApp Business Cloud API Configuration
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_BUSINESS_ACCOUNT_ID = os.getenv("WHATSAPP_BUSINESS_ACCOUNT_ID", "")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
WHATSAPP_API_VERSION = os.getenv("WHATSAPP_API_VERSION", "v18.0")

# Optional AI / LLM Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
AI_API_KEY = os.getenv("AI_API_KEY", GEMINI_API_KEY)
AI_MODEL_NAME = os.getenv("AI_MODEL_NAME", "gemini-1.5-flash")
