"""
routers/expenses.py - the CRUD endpoints for expenses.

Owner: Member A (API)

    GET    /api/expenses?month=2026-11&category_id=1   list (filters optional)
    POST   /api/expenses                                create     -> 201
    GET    /api/expenses/{id}                           read one   -> 200 / 403 / 404
    PUT    /api/expenses/{id}                           update     -> 200 / 403 / 404
    DELETE /api/expenses/{id}                           delete     -> 204 / 403 / 404

Every route depends on get_current_user, so you must be logged in (else 401).
Authentication vs authorization (slide 64):
    404 Not Found  - the expense does not exist
    403 Forbidden  - it exists, but belongs to another user
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


def _get_own_expense(db: Session, user: models.User, expense_id: int) -> models.Expense:  # devuelve el gasto solo si es del usuario logueado
    expense = ExpenseService.get(db, expense_id)  # busca el gasto en PostgreSQL por su id
    if expense is None:  # no existe
        raise HTTPException(status_code=404, detail="Expense not found")  # 404: el recurso no existe
    if expense.user_id != user.user_id:  # existe, pero su dueño es otro usuario (autorización)
        raise HTTPException(status_code=403, detail="Forbidden: this expense belongs to another user")  # 403: autenticado, pero sin permiso
    return expense  # es suyo: la ruta puede continuar


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
    return _get_own_expense(db, user, expense_id)


@router.put("/{expense_id}", response_model=schemas.ExpenseOut)
def edit_expense(
    expense_id: int,
    data: schemas.ExpenseUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    expense = _get_own_expense(db, user, expense_id)
    _check_category(db, data.category_id)
    return ExpenseService.update(db, expense, data)


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_expense(expense_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    ExpenseService.delete(db, _get_own_expense(db, user, expense_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
