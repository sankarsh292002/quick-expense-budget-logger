"""
models.py - the database tables, written as Python classes (the ORM).

Owner: Member B (Database)

Each class below is one ENTITY from our ER diagram (docs/er-diagram.svg).
Each Column is one ATTRIBUTE. Each ForeignKey is one RELATIONSHIP line.

    User     1 --- records ------  N Expense
    User     1 --- sets ---------  N Budget
    User     1 --- teaches ------  N CategoryRule   (learned keywords)
    Category 1 --- belongs_to ---  N Expense
    Category 1 --- applies_to ---  N Budget   (category optional: none = overall budget)
    Category 1 --- matched_by ---  N CategoryRule

New in v2: CategoryRule (keyword -> category, used by the auto-categorizer)
and Expense.source ("manual" or "import").
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .database import Base

# Money is stored as NUMERIC(12, 2) in PostgreSQL: exactly two decimals, no
# floating-point rounding errors inside the database. asdecimal=False hands
# the value to Python as a normal float, which keeps the rest of the code simple.
Money = Numeric(12, 2, asdecimal=False)


def utc_now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, index=True)
    username = Column(String(30), unique=True, nullable=False, index=True)
    email = Column(String(120), unique=True, nullable=False)
    # We NEVER store the real password, only a salted hash (see auth.py).
    password_hash = Column(String(200), nullable=False)
    phone_number = Column(String(20), nullable=True)  # optional
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # These let us write user.expenses / user.budgets in Python.
    # cascade: deleting a user also deletes their expenses, budgets and rules.
    expenses = relationship("Expense", back_populates="user", cascade="all, delete-orphan")
    budgets = relationship("Budget", back_populates="user", cascade="all, delete-orphan")
    rules = relationship("CategoryRule", back_populates="user", cascade="all, delete-orphan")


class Category(Base):
    __tablename__ = "categories"

    category_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(40), unique=True, nullable=False)  # unique: no "Food" twice
    color = Column(String(7), nullable=False, default="#64748b")  # hex colour for charts

    expenses = relationship("Expense", back_populates="category")
    budgets = relationship("Budget", back_populates="category")
    rules = relationship("CategoryRule", back_populates="category", cascade="all, delete-orphan")


class Expense(Base):
    __tablename__ = "expenses"

    expense_id = Column(Integer, primary_key=True, index=True)
    # Foreign keys: the two relationship lines in the ER diagram.
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("categories.category_id"), nullable=False)

    amount = Column(Money, nullable=False)
    description = Column(String(200), nullable=False)
    expense_date = Column(Date, nullable=False, index=True)  # when the money was spent
    source = Column(String(10), nullable=False, default="manual")  # "manual" or "import"
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)  # when it was logged

    user = relationship("User", back_populates="expenses")
    category = relationship("Category", back_populates="expenses")


class Budget(Base):
    __tablename__ = "budgets"
    # One budget per user, per category, per month.
    __table_args__ = (
        UniqueConstraint("user_id", "category_id", "period_month", name="uq_budget_user_cat_month"),
    )

    budget_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    # nullable=True: a budget with no category is the OVERALL monthly limit.
    category_id = Column(Integer, ForeignKey("categories.category_id"), nullable=True)
    limit_amount = Column(Money, nullable=False)
    period_month = Column(String(7), nullable=False)  # "YYYY-MM", e.g. "2026-11"

    user = relationship("User", back_populates="budgets")
    category = relationship("Category", back_populates="budgets")


class CategoryRule(Base):
    """One keyword that points to one category, e.g. "rewe" -> Food.

    user_id is NULL for the built-in rules every user gets, and set for rules
    a user added or that were learned from their corrections. A user's own
    rule wins over a built-in rule for the same keyword.
    """
    __tablename__ = "category_rules"
    __table_args__ = (UniqueConstraint("user_id", "keyword", name="uq_rule_user_keyword"),)

    rule_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=True, index=True)
    category_id = Column(Integer, ForeignKey("categories.category_id"), nullable=False)
    keyword = Column(String(60), nullable=False)  # always stored in lowercase
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    user = relationship("User", back_populates="rules")
    category = relationship("Category", back_populates="rules")
