from datetime import datetime, timezone
from fastapi import APIRouter
from app.config import APP_TITLE, APP_VERSION

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Health check")
def health_check():
    """Verify backend status and operational health."""
    return {
        "status": "ok",
        "service": APP_TITLE,
        "version": APP_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
