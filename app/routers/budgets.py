"""
routers/budgets.py - monthly spending limits.

Owner: Member A (API)

    GET    /api/budgets?month=2026-11   budgets for that month
    PUT    /api/budgets                 set a limit (creates or updates)
    DELETE /api/budgets/{id}            remove a limit

PUT is used instead of POST because sending the same budget twice gives
the same result (it updates rather than creating a duplicate).
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..database import get_db
from ..schemas import MONTH_PATTERN
from ..auth import get_current_user

router = APIRouter(prefix="/api/budgets", tags=["budgets"])


@router.get("", response_model=list[schemas.BudgetOut])
def list_budgets(
    month: str = Query(pattern=MONTH_PATTERN),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    return crud.list_budgets(db, user.user_id, month)


@router.put("", response_model=schemas.BudgetOut)
def set_budget(
    data: schemas.BudgetCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    if data.category_id is not None and crud.get_category(db, data.category_id) is None:
        raise HTTPException(status_code=422, detail="Unknown category")
    return crud.upsert_budget(db, user.user_id, data)


@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_budget(budget_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    budget = crud.get_budget(db, user.user_id, budget_id)
    if budget is None:
        raise HTTPException(status_code=404, detail="Budget not found")
    crud.delete_budget(db, budget)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
