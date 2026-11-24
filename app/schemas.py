"""
schemas.py - what the API accepts (input) and returns (output).

Owner: Member B (Database)

These are Pydantic models. FastAPI uses them to:
1. VALIDATE incoming JSON (e.g. amount must be > 0). Bad input is
   rejected automatically with HTTP 422 before our code even runs.
2. SHAPE outgoing JSON (e.g. we never send password_hash back).
3. Build the interactive documentation at /docs.

Schemas are NOT the same as models.py: models describe database
tables, schemas describe the data travelling over HTTP.
"""
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"  # "YYYY-MM"
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
COLOR_PATTERN = r"^#[0-9a-fA-F]{6}$"


# ---------- Users and login ----------

class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=30)
    email: str = Field(pattern=EMAIL_PATTERN, max_length=120)
    password: str = Field(min_length=6, max_length=100)
    phone_number: Optional[str] = Field(default=None, max_length=20)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # allows reading from ORM objects

    user_id: int
    username: str
    email: str
    phone_number: Optional[str] = None
    created_at: datetime


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------- Categories ----------

class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    color: str = Field(default="#64748b", pattern=COLOR_PATTERN)


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    category_id: int
    name: str
    color: str


# ---------- Expenses ----------

class ExpenseCreate(BaseModel):
    amount: float = Field(gt=0, le=1_000_000)
    description: str = Field(min_length=1, max_length=200)
    category_id: int
    expense_date: date


class ExpenseUpdate(ExpenseCreate):
    """Same fields as create. We send the full expense when editing."""


class ExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    expense_id: int
    amount: float
    description: str
    category_id: int
    expense_date: date
    source: str  # "manual" or "import"
    created_at: datetime


# ---------- Budgets ----------

class BudgetCreate(BaseModel):
    limit_amount: float = Field(gt=0, le=10_000_000)
    period_month: str = Field(pattern=MONTH_PATTERN)
    category_id: Optional[int] = None  # None = overall budget for the month


class BudgetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    budget_id: int
    limit_amount: float
    period_month: str
    category_id: Optional[int] = None


# ---------- Summary (feeds the three charts) ----------

class CategoryTotal(BaseModel):
    category_id: int
    name: str
    color: str
    total: float


class DayTotal(BaseModel):
    date: date
    total: float


class BudgetStatus(BaseModel):
    budget_id: int
    category_id: Optional[int]
    name: str  # category name, or "Overall"
    color: str
    limit_amount: float
    spent: float
    remaining: float
    percent_used: float
    over_budget: bool


class SummaryOut(BaseModel):
    month: str
    total: float
    count: int
    by_category: list[CategoryTotal]   # -> donut chart
    by_date: list[DayTotal]            # -> spending-by-date chart
    budgets: list[BudgetStatus]        # -> budget vs. expense bar chart


# ---------- Keyword rules (auto-categorization) ----------

class RuleCreate(BaseModel):
    keyword: str = Field(min_length=2, max_length=60)
    category_id: int


class RuleOut(BaseModel):
    rule_id: int
    keyword: str
    category_id: int
    category_name: str
    built_in: bool  # True = comes with the app, False = added or learned by this user


class CategorizeRequest(BaseModel):
    description: str = Field(min_length=1, max_length=200)


class CategorizeOut(BaseModel):
    category_id: int
    category_name: str
    matched_keyword: Optional[str]  # None = no rule matched, fell back to "Other"
    match_source: Optional[str]     # "learned", "built-in" or None


# ---------- CSV import ----------

class ImportRowOut(BaseModel):
    """One row of the preview: what we read, and the category we suggest."""
    line: int
    expense_date: date
    description: str
    amount: float
    category_id: int
    matched_keyword: Optional[str]
    match_source: Optional[str]  # "learned", "built-in", "file" or None (= needs review)
    duplicate: bool              # an identical expense already exists


class ImportIssue(BaseModel):
    line: int
    message: str


class ImportPreviewOut(BaseModel):
    rows: list[ImportRowOut]
    errors: list[ImportIssue]
    skipped_income: int


class ImportRowIn(BaseModel):
    """One row the user confirmed, possibly with a corrected category."""
    expense_date: date
    description: str = Field(min_length=1, max_length=200)
    amount: float = Field(gt=0, le=1_000_000)
    category_id: int
    suggested_category_id: Optional[int] = None  # what we suggested; used for learning


class ImportCommitIn(BaseModel):
    rows: list[ImportRowIn] = Field(min_length=1, max_length=5000)
    learn: bool = True  # learn new keyword rules from the user's corrections


class LearnedRule(BaseModel):
    keyword: str
    category_name: str


class ImportCommitOut(BaseModel):
    imported: int
    rules_learned: list[LearnedRule]
