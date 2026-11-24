"""
conftest.py - shared test setup. pytest loads this file automatically.

Owner: Member D (Processing engine and Tests)

Which database do the tests use?
- By default a temporary SQLite file: fast, nothing to set up, and it never
  touches your real PostgreSQL data.
- To run the same tests against PostgreSQL, create an EMPTY database called
  expense_logger_test in pgAdmin and set TEST_DATABASE_URL, e.g. (Windows cmd)
      set TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres123@localhost:5432/expense_logger_test
  (Mac: export TEST_DATABASE_URL=...) then run pytest. Every table in that
  database is deleted before each test.
"""
import os
import tempfile

import pytest

# Choose the database BEFORE the app is imported (database.py reads it on import).
_test_url = os.getenv("TEST_DATABASE_URL")
if not _test_url:
    _tmp_dir = tempfile.mkdtemp()
    _test_url = f"sqlite:///{os.path.join(_tmp_dir, 'test.db')}"
os.environ["DATABASE_URL"] = _test_url

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def client():
    Base.metadata.drop_all(bind=engine)
    with TestClient(app) as c:  # "with" runs the startup code (tables, categories, rules)
        yield c


def register(client, username="anna", password="secret123"):
    res = client.post(
        "/api/auth/register",
        json={"username": username, "email": f"{username}@example.com", "password": password},
    )
    assert res.status_code == 201, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture
def auth(client):
    """Headers of a logged-in user."""
    return register(client)


@pytest.fixture
def categories(client, auth):
    """Category name -> category_id, e.g. {"Food": 3, ...}"""
    return {c["name"]: c["category_id"] for c in client.get("/api/categories", headers=auth).json()}
