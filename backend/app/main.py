from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.config import APP_TITLE, APP_DESCRIPTION, APP_VERSION, CORS_ORIGINS
from app.database import init_db
from app.routers import health, inventory, credit, alerts, summary, chat, parser


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure tables exist and seed baseline inventory if empty
    init_db(seed=True)
    yield


app = FastAPI(
    title=APP_TITLE,
    description=APP_DESCRIPTION,
    version=APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all feature routers under /api
app.include_router(health.router, prefix="/api")
app.include_router(inventory.router, prefix="/api")
app.include_router(credit.router, prefix="/api")
app.include_router(alerts.router, prefix="/api")
app.include_router(summary.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(parser.router, prefix="/api")


@app.get("/", include_in_schema=False)
def root():
    """Redirect root to interactive Swagger documentation."""
    return RedirectResponse(url="/docs")
