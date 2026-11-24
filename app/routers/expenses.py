"""
routers/expenses.py - the CRUD endpoints for expenses.

Owner: Member A (API)

    GET    /api/expenses?month=2026-11&category_id=1   list (filters optional)
    POST   /api/expenses                                create     -> 201
    GET    /api/expenses/{id}                           read one   -> 200 / 404
    PUT    /api/expenses/{id}                           update     -> 200 / 404
    DELETE /api/expenses/{id}                           delete     -> 204 / 404

Every route depends on get_current_user, so you must be logged in, and
you only ever see your own expenses.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..services import CategoryService, ExpenseService
from ..database import get_db
from ..schemas import MONTH_PATTERN
from ..auth import get_current_user

router = APIRouter(prefix="/api/expenses", tags=["expenses"])


def _check_category(db: Session, category_id: int) -> None:
    if CategoryService.get(db, category_id) is None:
        raise HTTPException(status_code=422, detail="Unknown category")


def _find_or_404(db: Session, user: models.User, expense_id: int) -> models.Expense:
    expense = ExpenseService.get_for_user(db, user.user_id, expense_id)
    if expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    return expense


@router.get("", response_model=list[schemas.ExpenseOut])
def list_expenses(
    month: str | None = Query(default=None, pattern=MONTH_PATTERN),
    category_id: int | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    return ExpenseService.list_for_user(db, user.user_id, month, category_id)


@router.post("", response_model=schemas.ExpenseOut, status_code=status.HTTP_201_CREATED)
def add_expense(
    data: schemas.ExpenseCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    _check_category(db, data.category_id)
    return ExpenseService.create(db, user.user_id, data)


@router.get("/{expense_id}", response_model=schemas.ExpenseOut)
def get_expense(expense_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return _find_or_404(db, user, expense_id)


@router.put("/{expense_id}", response_model=schemas.ExpenseOut)
def edit_expense(
    expense_id: int,
    data: schemas.ExpenseUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    expense = _find_or_404(db, user, expense_id)
    _check_category(db, data.category_id)
    return ExpenseService.update(db, expense, data)


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_expense(expense_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    ExpenseService.delete(db, _find_or_404(db, user, expense_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
