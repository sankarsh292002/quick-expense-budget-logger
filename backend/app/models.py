import datetime as dt

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    budget_limit: Mapped[float] = mapped_column(default=0.0)

    expenses: Mapped[list["Expense"]] = relationship(back_populates="category")


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    amount: Mapped[float]
    description: Mapped[str] = mapped_column(String(200))
    spent_on: Mapped[dt.date]
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))

    category: Mapped[Category] = relationship(back_populates="expenses")