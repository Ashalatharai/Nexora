from datetime import date, datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.summary import DailySummaryResponse
from app.services.summary_service import SummaryService

router = APIRouter(prefix="/summary", tags=["Summary"])


@router.get("/daily", response_model=DailySummaryResponse, summary="Get daily business summary")
def get_daily_summary(
    day: Optional[str] = Query(None, description="Date in YYYY-MM-DD format (defaults to today)"),
    db: Session = Depends(get_db)
):
    """
    Returns end-of-day overview:
    - Items sold, received, damaged, returned
    - Current stock levels for all items
    - Total credit purchases and payments collected
    """
    parsed_date = None
    if day:
        try:
            parsed_date = datetime.strptime(day, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date format. Expected YYYY-MM-DD."
            )

    return SummaryService.get_daily_summary(db, target_date=parsed_date)
