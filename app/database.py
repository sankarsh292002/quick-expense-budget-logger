"""
database.py - connection to the PostgreSQL database.

Owner: Member B (Database)

Key ideas
- DATABASE_URL: where the database is, and how to log in. It is read from
  the file `.env` (never committed to GitHub, because it holds a password).
  Format:  postgresql+psycopg://USER:PASSWORD@HOST:PORT/DATABASE
- ENGINE: the object that knows how to talk to PostgreSQL (via the psycopg driver).
- SESSION: a short "conversation" with the database. We open one per
  HTTP request, use it to read/write rows, and close it afterwards.
- BASE: the parent class of every table class in models.py.
"""
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()  # copies the values from .env into os.environ (existing values win)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres123@localhost:5432/expense_logger",
)

# SQLite (used by the automated tests) needs one extra setting; PostgreSQL does not.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

# pool_pre_ping: check a connection still works before using it, so a
# restarted PostgreSQL server does not cause errors.
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

Base = declarative_base()


def get_db():
    """Give each request its own session and always close it afterwards.

    FastAPI calls this automatically for any route that asks for
    `db: Session = Depends(get_db)`.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
