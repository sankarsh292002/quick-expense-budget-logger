"""
summary.py - the processing engine: all server-side calculations.

Owner: Member B (Database), reviewed by Member D

The browser never adds up money itself. It asks GET /api/summary and
draws whatever this function returns. That way there is one trusted
result, and the calculation logic is testable in Python.

One call produces the data for all three charts in the ER diagram:
  by_category -> donut chart        "Expenses vs. Category"
  budgets     -> horizontal bars    "Budget vs. Expense"
  by_date     -> bar chart          "Expense by date"
"""
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models
from .crud import month_range


def build_summary(db: Session, user_id: int, month: str) -> dict:
    start, end = month_range(month)

    # Conditions shared by every query: this user, this month.
    in_month = (
        models.Expense.user_id == user_id,
        models.Expense.expense_date >= start,
        models.Expense.expense_date < end,
    )

    # 1) Grand total and number of expenses.
    #    SQL: SELECT SUM(amount), COUNT(*) FROM expenses WHERE ...
    total, count = db.execute(
        select(func.coalesce(func.sum(models.Expense.amount), 0.0), func.count(models.Expense.expense_id))
        .where(*in_month)
    ).one()

    # 2) Total per category (JOIN expenses with categories, GROUP BY category).
    category_rows = db.execute(
        select(
            models.Category.category_id,
            models.Category.name,
            models.Category.color,
            func.sum(models.Expense.amount).label("total"),
        )
        .join(models.Expense, models.Expense.category_id == models.Category.category_id)
        .where(*in_month)
        .group_by(models.Category.category_id, models.Category.name, models.Category.color)
        .order_by(func.sum(models.Expense.amount).desc())
    ).all()
    by_category = [
        {"category_id": r.category_id, "name": r.name, "color": r.color, "total": round(r.total, 2)}
        for r in category_rows
    ]
    spent_per_category = {row["category_id"]: row["total"] for row in by_category}

    # 3) Total per day. Days with no spending are filled with 0 so the
    #    chart shows every day of the month, not just the busy ones.
    day_rows = db.execute(
        select(models.Expense.expense_date, func.sum(models.Expense.amount))
        .where(*in_month)
        .group_by(models.Expense.expense_date)
    ).all()
    spent_per_day = {day: amount for day, amount in day_rows}
    by_date = []
    day = start
    while day < end:
        by_date.append({"date": day, "total": round(spent_per_day.get(day, 0.0), 2)})
        day += timedelta(days=1)

    # 4) Budget vs. actual spending.
    budgets = db.scalars(
        select(models.Budget).where(models.Budget.user_id == user_id, models.Budget.period_month == month)
    ).all()
    budget_status = []
    for b in budgets:
        if b.category_id is None:  # overall budget compares with the grand total
            name, color, spent = "Overall", "#334155", total
        else:
            name, color = b.category.name, b.category.color
            spent = spent_per_category.get(b.category_id, 0.0)
        budget_status.append({
            "budget_id": b.budget_id,
            "category_id": b.category_id,
            "name": name,
            "color": color,
            "limit_amount": round(b.limit_amount, 2),
            "spent": round(spent, 2),
            "remaining": round(b.limit_amount - spent, 2),
            "percent_used": round(spent / b.limit_amount * 100, 1),
            "over_budget": spent > b.limit_amount,
        })
    # Overall first, then categories alphabetically
    budget_status.sort(key=lambda s: (s["category_id"] is not None, s["name"]))

    return {
        "month": month,
        "total": round(total, 2),
        "count": count,
        "by_category": by_category,
        "by_date": by_date,
        "budgets": budget_status,
    }
