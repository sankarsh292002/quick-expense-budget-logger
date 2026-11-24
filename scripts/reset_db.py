"""
reset_db.py - delete ALL tables and data, then create them again, empty.

Owner: Member B (Database)

Use it when the tables are out of date (for example after someone changed
models.py) or you simply want a clean start:

    python -m scripts.reset_db
    python -m scripts.seed_demo      (optional: demo user again)

It asks for confirmation first, because the data cannot be recovered.
"""
from app.services import CategoryService, RuleService
from app.database import Base, SessionLocal, engine


def main():
    print(f"This deletes every table in: {engine.url.render_as_string(hide_password=True)}")
    if input("Type yes to continue: ").strip().lower() != "yes":
        print("Cancelled.")
        return
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        CategoryService.seed_defaults(db)
        RuleService.seed_defaults(db)
    print("Done: empty tables with default categories and keyword rules.")


if __name__ == "__main__":
    main()
