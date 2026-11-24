"""
seed_demo.py - fill the database with a demo user and realistic expenses,
so the dashboard looks alive during the presentation.

Owner: Member B (Database)

Run from the project folder:   python -m scripts.seed_demo
Log in with:                   username "demo"   password "demo1234"

Running it again deletes the old demo user's data and creates it fresh.

Only the CURRENT month gets expenses. The previous month is left empty on
purpose, so in the demo you can fill it by importing a bank file
(sample_data/bank_export_de.csv covers October 2026).
"""
import random
from datetime import date, timedelta

from app import models, schemas
from app.services import BudgetService, CategoryService, RuleService, UserService
from app.database import Base, SessionLocal, engine

DEMO_USER = schemas.UserCreate(username="demo", email="demo@example.com", password="demo1234")

# (description, category, typical amount)
TEMPLATES = [
    ("REWE groceries", "Food", 38), ("Lunch at the mensa", "Food", 6.5), ("Starbucks coffee", "Food", 3.2),
    ("Baeckerei Kamps", "Food", 4.8), ("Lieferando pizza", "Food", 18),
    ("Deutschlandticket", "Transit", 58), ("Uber ride", "Transit", 16), ("Deutsche Bahn ticket", "Transit", 39.9),
    ("Stadtwerke electricity", "Utilities", 62), ("Vodafone internet", "Utilities", 39.99), ("Telekom phone plan", "Utilities", 15),
    ("Rent", "Rent", 520),
    ("Zalando clothes", "Shopping", 45), ("Amazon order", "Shopping", 79),
    ("Apotheke", "Health", 12.5), ("McFit gym", "Health", 29.9),
    ("Cinemaxx", "Entertainment", 13), ("Netflix subscription", "Entertainment", 12.99),
]


def month_str(d: date) -> str:
    return d.strftime("%Y-%m")


def main():
    random.seed(42)  # same "random" data every time, so the demo is predictable
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        CategoryService.seed_defaults(db)
        RuleService.seed_defaults(db)
        old = UserService.get_by_username(db, DEMO_USER.username)
        if old:
            db.delete(old)
            db.commit()
        user = UserService.create(db, DEMO_USER)
        cats = {c.name: c.category_id for c in CategoryService.list_all(db)}

        today = date.today()
        this_month_start = today.replace(day=1)
        last_month_start = (this_month_start - timedelta(days=1)).replace(day=1)

        def add(desc, cat, amount, day):
            db.add(models.Expense(user_id=user.user_id, category_id=cats[cat],
                                  amount=round(amount, 2), description=desc, expense_date=day))

        for start, end in [(this_month_start, today)]:
            add("Rent", "Rent", 520, start)
            add("Deutschlandticket", "Transit", 58, start)
            add("Vodafone internet", "Utilities", 39.99, start + timedelta(days=min(2, (end - start).days)))
            days = (end - start).days + 1
            for _ in range(int(days * 0.9)):
                desc, cat, base = random.choice([t for t in TEMPLATES if t[0] not in ("Rent", "Deutschlandticket", "Vodafone internet")])
                add(desc, cat, base * random.uniform(0.7, 1.3), start + timedelta(days=random.randrange(days)))

        for month in (month_str(last_month_start), month_str(this_month_start)):
            BudgetService.upsert(db, user.user_id, schemas.BudgetCreate(limit_amount=1400, period_month=month))
            for cat, limit in [("Food", 250), ("Shopping", 200), ("Entertainment", 40), ("Transit", 220)]:
                BudgetService.upsert(db, user.user_id, schemas.BudgetCreate(
                    limit_amount=limit, period_month=month, category_id=cats[cat]))
        db.commit()
        count = db.query(models.Expense).filter_by(user_id=user.user_id).count()
    print(f"Demo data ready: {count} expenses. Log in as demo / demo1234")


if __name__ == "__main__":
    main()
