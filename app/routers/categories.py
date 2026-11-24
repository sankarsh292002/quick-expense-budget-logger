"""
routers/categories.py - list and add categories.

Owner: Member A (API)

    GET  /api/categories   all categories (fills the dropdown)
    POST /api/categories   add a new category, e.g. "Education"
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..database import get_db
from ..security import get_current_user

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("", response_model=list[schemas.CategoryOut])
def list_categories(db: Session = Depends(get_db), _: models.User = Depends(get_current_user)):
    return crud.list_categories(db)


@router.post("", response_model=schemas.CategoryOut, status_code=status.HTTP_201_CREATED)
def add_category(
    data: schemas.CategoryCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    if crud.get_category_by_name(db, data.name.strip()):
        raise HTTPException(status_code=409, detail="Category already exists")
    return crud.create_category(db, data)
