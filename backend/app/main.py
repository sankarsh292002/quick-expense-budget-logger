import datetime as dt
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .database import Base, SessionLocal, engine, get_db
from .models import Category, Expense

app = FastAPI(title="Quick Expense & Budget Logger")

# --- Create tables and default categories on startup ---
Base.metadata.create_all(bind=engine)

DEFAULT_CATEGORIES = {"Food": 150.0, "Transit": 60.0, "Utilities": 100.0}

with SessionLocal() as db:
    if db.scalar(select(func.count(Category.id))) == 0:
        db.add_all(Category(name=n, budget_limit=l) for n, l in DEFAULT_CATEGORIES.items())
        db.commit()


# --- Schemas (what the API accepts and returns) ---
class ExpenseIn(BaseModel):
    amount: float = Field(gt=0)
    description: str = Field(min_length=1, max_length=200)
    spent_on: dt.date
    category_id: int


class ExpenseOut(ExpenseIn):
    id: int
    category_name: str


def to_out(e: Expense) -> ExpenseOut:
    return ExpenseOut(
        id=e.id,
        amount=e.amount,
        description=e.description,
        spent_on=e.spent_on,
        category_id=e.category_id,
        category_name=e.category.name,
    )


# --- API endpoints ---
@app.get("/api/categories")
def list_categories(db: Session = Depends(get_db)):
    cats = db.scalars(select(Category).order_by(Category.name)).all()
    return [{"id": c.id, "name": c.name, "budget_limit": c.budget_limit} for c in cats]


@app.get("/api/expenses", response_model=list[ExpenseOut])
def list_expenses(db: Session = Depends(get_db)):
    rows = db.scalars(select(Expense).order_by(Expense.spent_on.desc(), Expense.id.desc())).all()
    return [to_out(e) for e in rows]


@app.post("/api/expenses", response_model=ExpenseOut, status_code=201)
def create_expense(data: ExpenseIn, db: Session = Depends(get_db)):
    if db.get(Category, data.category_id) is None:
        raise HTTPException(status_code=400, detail="Category does not exist")
    expense = Expense(**data.model_dump())
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return to_out(expense)


@app.delete("/api/expenses/{expense_id}", status_code=204)
def delete_expense(expense_id: int, db: Session = Depends(get_db)):
    expense = db.get(Expense, expense_id)
    if expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    db.delete(expense)
    db.commit()


@app.get("/api/summary")
def summary(db: Session = Depends(get_db)):
    rows = db.execute(
        select(
            Category.id,
            Category.name,
            Category.budget_limit,
            func.coalesce(func.sum(Expense.amount), 0.0).label("spent"),
        )
        .outerjoin(Expense, Expense.category_id == Category.id)
        .group_by(Category.id)
        .order_by(Category.name)
    ).all()

    categories = [
        {
            "id": r.id,
            "name": r.name,
            "budget_limit": r.budget_limit,
            "spent": round(r.spent, 2),
            "remaining": round(r.budget_limit - r.spent, 2),
            "over_budget": r.spent > r.budget_limit,
        }
        for r in rows
    ]
    total_spent = round(sum(c["spent"] for c in categories), 2)
    total_budget = round(sum(c["budget_limit"] for c in categories), 2)
    return {"categories": categories, "total_spent": total_spent, "total_budget": total_budget}


# --- Serve the frontend (must stay LAST so /api routes match first) ---
FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")