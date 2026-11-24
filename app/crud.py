"""
crud.py - functions that Create, Read, Update and Delete rows.

Owner: Member B (Database)

The routes in app/routers/ call these functions. Keeping database code
here (and HTTP code in the routers) means each file has one job.

Every expense/budget function takes `user_id`, so one user can never see
or change another user's data.
"""
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models, schemas
from .categorizer import DEFAULT_RULES, Categorizer, Rule, normalize
from .security import hash_password

DEFAULT_CATEGORIES = [
    ("Food", "#f97316"),
    ("Transit", "#0ea5e9"),
    ("Utilities", "#8b5cf6"),
    ("Rent", "#ef4444"),
    ("Shopping", "#ec4899"),
    ("Health", "#22c55e"),
    ("Entertainment", "#eab308"),
    ("Other", "#64748b"),
]


def month_range(month: str) -> tuple[date, date]:
    """'2026-11' -> (2026-11-01, 2026-12-01). End date is exclusive."""
    year, mon = (int(part) for part in month.split("-"))
    start = date(year, mon, 1)
    end = date(year + 1, 1, 1) if mon == 12 else date(year, mon + 1, 1)
    return start, end


# ---------- Users ----------

def get_user_by_username(db: Session, username: str):
    return db.scalar(select(models.User).where(models.User.username == username))


def get_user_by_email(db: Session, email: str):
    return db.scalar(select(models.User).where(models.User.email == email))


def create_user(db: Session, data: schemas.UserCreate) -> models.User:
    user = models.User(
        username=data.username,
        email=data.email.lower(),
        password_hash=hash_password(data.password),
        phone_number=data.phone_number or None,
    )
    db.add(user)      # stage the new row
    db.commit()       # write it to the database file
    db.refresh(user)  # reload it so user.user_id is filled in
    return user


# ---------- Categories ----------

def seed_categories(db: Session) -> None:
    """Insert the default categories once, if the table is empty."""
    if db.scalar(select(models.Category).limit(1)) is None:
        db.add_all(models.Category(name=n, color=c) for n, c in DEFAULT_CATEGORIES)
        db.commit()


def list_categories(db: Session):
    return db.scalars(select(models.Category).order_by(models.Category.name)).all()


def get_category(db: Session, category_id: int):
    return db.get(models.Category, category_id)


def get_category_by_name(db: Session, name: str):
    return db.scalar(select(models.Category).where(models.Category.name.ilike(name)))


def create_category(db: Session, data: schemas.CategoryCreate) -> models.Category:
    category = models.Category(name=data.name.strip(), color=data.color)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


# ---------- Expenses ----------

def list_expenses(db: Session, user_id: int, month: str | None = None, category_id: int | None = None):
    query = select(models.Expense).where(models.Expense.user_id == user_id)
    if month:
        start, end = month_range(month)
        query = query.where(models.Expense.expense_date >= start, models.Expense.expense_date < end)
    if category_id:
        query = query.where(models.Expense.category_id == category_id)
    # newest first; created_at breaks ties between expenses on the same day
    query = query.order_by(models.Expense.expense_date.desc(), models.Expense.created_at.desc())
    return db.scalars(query).all()


def get_expense(db: Session, user_id: int, expense_id: int):
    expense = db.get(models.Expense, expense_id)
    if expense is None or expense.user_id != user_id:
        return None  # treat "someone else's expense" exactly like "not found"
    return expense


def create_expense(db: Session, user_id: int, data: schemas.ExpenseCreate, source: str = "manual") -> models.Expense:
    expense = models.Expense(user_id=user_id, source=source, **data.model_dump())
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


def update_expense(db: Session, expense: models.Expense, data: schemas.ExpenseUpdate) -> models.Expense:
    for field, value in data.model_dump().items():
        setattr(expense, field, value)
    db.commit()
    db.refresh(expense)
    return expense


def delete_expense(db: Session, expense: models.Expense) -> None:
    db.delete(expense)
    db.commit()


# ---------- Budgets ----------

def list_budgets(db: Session, user_id: int, month: str):
    query = select(models.Budget).where(
        models.Budget.user_id == user_id, models.Budget.period_month == month
    )
    return db.scalars(query).all()


def upsert_budget(db: Session, user_id: int, data: schemas.BudgetCreate) -> models.Budget:
    """Create the budget, or update the limit if one already exists for
    this user + category + month ("upsert" = update or insert).

    We check in Python because SQLite treats two NULL category_ids as
    different, so the unique constraint alone would not stop two
    "Overall" budgets in the same month.
    """
    existing = db.scalar(
        select(models.Budget).where(
            models.Budget.user_id == user_id,
            models.Budget.period_month == data.period_month,
            models.Budget.category_id.is_(None)
            if data.category_id is None
            else models.Budget.category_id == data.category_id,
        )
    )
    if existing:
        existing.limit_amount = data.limit_amount
        budget = existing
    else:
        budget = models.Budget(user_id=user_id, **data.model_dump())
        db.add(budget)
    db.commit()
    db.refresh(budget)
    return budget


def get_budget(db: Session, user_id: int, budget_id: int):
    budget = db.get(models.Budget, budget_id)
    if budget is None or budget.user_id != user_id:
        return None
    return budget


def delete_budget(db: Session, budget: models.Budget) -> None:
    db.delete(budget)
    db.commit()


# ---------- Keyword rules ----------

def seed_default_rules(db: Session) -> None:
    """Insert the built-in keyword rules once (user_id = NULL)."""
    if db.scalar(select(models.CategoryRule).where(models.CategoryRule.user_id.is_(None)).limit(1)):
        return
    categories = {c.name: c.category_id for c in list_categories(db)}
    for category_name, keywords in DEFAULT_RULES.items():
        if category_name in categories:
            db.add_all(
                models.CategoryRule(user_id=None, category_id=categories[category_name], keyword=k)
                for k in keywords
            )
    db.commit()


def list_rules(db: Session, user_id: int):
    """Built-in rules plus this user's own rules."""
    query = (
        select(models.CategoryRule)
        .where((models.CategoryRule.user_id.is_(None)) | (models.CategoryRule.user_id == user_id))
        .order_by(models.CategoryRule.user_id.is_(None), models.CategoryRule.keyword)
    )
    return db.scalars(query).all()


def get_user_rule(db: Session, user_id: int, keyword: str):
    return db.scalar(
        select(models.CategoryRule).where(
            models.CategoryRule.user_id == user_id, models.CategoryRule.keyword == keyword
        )
    )


def save_user_rule(db: Session, user_id: int, keyword: str, category_id: int, commit: bool = True):
    """Create the user's rule, or point an existing one to the new category."""
    keyword = normalize(keyword)
    rule = get_user_rule(db, user_id, keyword)
    if rule:
        rule.category_id = category_id
    else:
        rule = models.CategoryRule(user_id=user_id, keyword=keyword, category_id=category_id)
        db.add(rule)
    if commit:
        db.commit()
        db.refresh(rule)
    else:
        db.flush()  # so a second save of the same keyword in this batch finds it
    return rule


def delete_rule(db: Session, rule: models.CategoryRule) -> None:
    db.delete(rule)
    db.commit()


def build_categorizer(db: Session, user_id: int) -> Categorizer:
    rules = [Rule(r.keyword, r.category_id, r.user_id is not None) for r in list_rules(db, user_id)]
    return Categorizer(rules)


# ---------- Import helpers ----------

def existing_expense_keys(db: Session, user_id: int, start: date, end: date) -> set[tuple]:
    """(date, amount, lowercase description) of the user's expenses in a date
    range, used to flag rows in an import that were already imported."""
    rows = db.execute(
        select(models.Expense.expense_date, models.Expense.amount, func.lower(models.Expense.description))
        .where(
            models.Expense.user_id == user_id,
            models.Expense.expense_date >= start,
            models.Expense.expense_date <= end,
        )
    ).all()
    return {(d, round(a, 2), text) for d, a, text in rows}
