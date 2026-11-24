"""
routers/summary.py - one endpoint that returns all dashboard numbers.

Owner: Member A (API). The calculation itself lives in app/summary.py (Member B).

    GET /api/summary?month=2026-11
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..schemas import MONTH_PATTERN
from ..security import get_current_user
from ..summary import build_summary

router = APIRouter(prefix="/api/summary", tags=["summary"])


@router.get("", response_model=schemas.SummaryOut)
def get_summary(
    month: str = Query(pattern=MONTH_PATTERN, examples=["2026-11"]),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    return build_summary(db, user.user_id, month)
