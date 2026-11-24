# Quick Expense & Budget Logger

A web application to log or **import** expenses, **categorize them automatically**, and
monitor them against monthly budgets with charts.
Built for the *Software Development and Applications* course,
M.Eng. Engineering and Sustainable Technology Management (Industry 4.0).

| Layer | Technology | Where |
| --- | --- | --- |
| Web interface | HTML, CSS, JavaScript, Chart.js | `static/` |
| REST API | Python, FastAPI | `app/main.py`, `app/security.py`, `app/routers/` |
| Processing engine | CSV reader, keyword categorizer, SQL aggregation | `app/importer.py`, `app/categorizer.py`, `app/summary.py` |
| Database | PostgreSQL via SQLAlchemy ORM (psycopg driver) | `app/database.py`, `app/models.py`, `app/crud.py` |
| API testing | Postman collection | `postman/` |
| Automated tests | pytest | `tests/` |

The full step-by-step guide (installing VS Code, PostgreSQL, pgAdmin, Postman, the
GitHub workflow and the schedule) is in the team's implementation guide document.

---

## 1. Run it

You need **Python 3.13**, **PostgreSQL** with a database called `expense_logger`
(create it in pgAdmin), and this folder open in a terminal.

| Step | Windows (cmd) | Mac (Terminal) |
| --- | --- | --- |
| Create the virtual environment | `py -V:3.13 -m venv venv` | `python3.13 -m venv venv` |
| Activate it | `venv\Scripts\activate` | `source venv/bin/activate` |
| Install packages | `pip install -r requirements.txt` | same |
| Create your settings file | `copy .env.example .env` | `cp .env.example .env` |
| Put your PostgreSQL password into `.env` | open `.env` in VS Code | same |
| (optional) Demo data | `python -m scripts.seed_demo` | same |
| Start the server | `uvicorn app.main:app --reload` | same |

Open **http://127.0.0.1:8000** (log in as `demo` / `demo1234`) and
**http://127.0.0.1:8000/docs** for the interactive API documentation.

- Tests: `pytest` (50 tests). They use a temporary SQLite file by default; see
  `tests/conftest.py` to run them against PostgreSQL.
- Postman: *Import* → `postman/ExpenseLogger.postman_collection.json` → run *Auth › Log in* first.
- Clean database: `python -m scripts.reset_db`.

---

## 2. How it fits together

```text
 Browser (static/)                      Server (app/)                                 PostgreSQL
 ┌──────────────────────┐   HTTP+JSON   ┌────────────────────────────────────────┐    ┌────────────────┐
 │ index.html  layout   │ ────────────► │ routers/*.py      REST endpoints       │    │ users          │
 │ style.css   look     │               │ security.py       login, tokens        │    │ categories     │
 │ app.js      forms    │               │ schemas.py        validation           │    │ category_rules │
 │ import.js   CSV flow │ ◄──────────── │ importer.py       reads CSV files      │──► │ expenses       │
 │ charts.js   Chart.js │               │ categorizer.py    keyword matching     │ORM │ budgets        │
 │ api.js      fetch()  │               │ crud.py / summary.py  read, write, sum │◄── │                │
 └──────────────────────┘               └────────────────────────────────────────┘    └────────────────┘
```

**Importing a bank file, step by step**

1. The user picks a CSV in *Import transactions*; `import.js` sends it to
   `POST /api/import/preview` as form-data.
2. `importer.py` finds the header row, the separator and the number/date formats,
   and turns each line into *date, description, amount*. Income rows are skipped.
3. `categorizer.py` suggests a category per row from the keyword rules in
   `category_rules`. Rows already in the database are flagged as duplicates.
   **Nothing is saved yet.**
4. The user checks the preview, changes categories where needed, and clicks *Import*.
   `POST /api/import/commit` saves the rows. Every correction becomes a new keyword rule
   for that user (e.g. `stadtbibliothek → Entertainment`), so the next import is right.
5. The dashboard refreshes: cards, three charts, history.

---

## 3. Database design (from our ER diagram, extended)

![ER diagram](docs/er-diagram.jpg)

| Table | Columns | Relationships |
| --- | --- | --- |
| `users` | **user_id** (PK), username (unique), email (unique), password_hash, phone_number (optional), created_at | 1 user → N expenses, budgets, rules |
| `categories` | **category_id** (PK), name (unique), color | 1 category → N expenses, budgets, rules |
| `expenses` | **expense_id** (PK), user_id (FK), category_id (FK), amount NUMERIC(12,2), description, expense_date, **source** (manual / import), created_at | belongs to 1 user, 1 category |
| `budgets` | **budget_id** (PK), user_id (FK), category_id (FK, nullable), limit_amount NUMERIC(12,2), period_month | belongs to 1 user, 0 or 1 category |
| `category_rules` *(new)* | **rule_id** (PK), user_id (FK, nullable), category_id (FK), keyword, created_at | belongs to 0 or 1 user, 1 category |

Design decisions:

- **Money is NUMERIC(12,2)**, exact to the cent, not a floating-point number.
- **`category_rules.user_id` NULL** = built-in rule for everyone; set = the user's own rule.
  Unique per user and keyword. A user's rule beats a built-in rule.
- **`budgets.category_id` NULL** = the overall monthly limit.
- **Passwords are hashed** (PBKDF2 with a random salt). The real password is never stored.
- **The database password is in `.env`**, which is never committed. `.env.example` shows the format.
- **Charts are not stored.** They are computed from stored data on every request (`summary.py`).

---

## 4. REST API

All endpoints except register/login need `Authorization: Bearer <token>`.

| Method | URL | Purpose | Success | Errors |
| --- | --- | --- | --- | --- |
| POST | `/api/auth/register` | Create an account, returns a token | 201 | 409, 422 |
| POST | `/api/auth/login` | Log in, returns a token | 200 | 401 |
| GET | `/api/auth/me` | Current user | 200 | 401 |
| GET / POST | `/api/categories` | List / add categories | 200 / 201 | 409, 422 |
| GET | `/api/expenses?month=YYYY-MM&category_id=` | List own expenses, newest first | 200 | 422 |
| POST | `/api/expenses` | Add an expense | 201 | 422 |
| GET / PUT / DELETE | `/api/expenses/{id}` | Read / edit / delete one | 200 / 200 / 204 | 404, 422 |
| GET | `/api/budgets?month=YYYY-MM` | Budgets of a month | 200 | 422 |
| PUT | `/api/budgets` | Set a limit (creates or updates) | 200 | 422 |
| DELETE | `/api/budgets/{id}` | Remove a limit | 204 | 404 |
| GET | `/api/summary?month=YYYY-MM` | Totals, per category, per day, budget status | 200 | 422 |
| POST | `/api/import/preview` | Upload CSV (form-data `file`), get suggested categories | 200 | 413, 422 |
| POST | `/api/import/commit` | Save confirmed rows, learn from corrections | 201 | 422 |
| GET / POST | `/api/rules` | List / add keyword rules | 200 / 201 | 409, 422 |
| DELETE | `/api/rules/{id}` | Delete own rule | 204 | 403 built-in, 404 |
| POST | `/api/categorize` | Which category would this description get? | 200 | 422 |

**Status codes:** 200 OK · 201 Created · 204 No Content · 401 not logged in ·
403 not allowed · 404 not found · 409 duplicate · 413 file too large · 422 invalid input.

---

## 5. CSV files the importer accepts

Minimum: a header row with a **date**, a **description** (or payee) and an **amount** column.
See `sample_data/` for two examples.

```csv
date,description,amount
2026-11-02,REWE groceries,34.80
2026-11-03,Deutsche Bahn ticket to Munich,39.90
```

Also understood: German bank exports (`Buchungstag`, `Verwendungszweck`,
`Beguenstigter/Zahlungspflichtiger`, `Betrag`), separators `; , tab |`, numbers like
`1.234,56` or `-12,50`, dates like `05.10.26`, lines before the header, Windows-1252
encoding, a separate debit column, and an optional `category` column. Negative
amounts are expenses; positive ones are skipped as income when a file has both.

---

## 6. Who owns what

| Member | Role | Files |
| --- | --- | --- |
| A | API Lead | `app/main.py`, `app/security.py`, `app/routers/*`, `postman/*` |
| B | Database Lead | `app/database.py`, `app/models.py`, `app/schemas.py`, `app/crud.py`, `app/summary.py`, `scripts/*`, `.env.example` |
| C | Frontend Lead | `static/*` |
| D | Processing Engine & Testing Lead | `app/importer.py`, `app/categorizer.py`, `sample_data/*`, `tests/*`, `README.md`, `requirements.txt`, `pytest.ini`, `.gitignore`, `.vscode/` |

Every file starts with a comment naming its owner and explaining the key idea.

---

## 7. Known limitations (be ready to discuss)

- **Keyword rules, not machine learning:** predictable and explainable, but a new
  merchant needs one correction before it is recognized. A next step could be a
  classifier trained on the user's corrected history.
- **CSV only:** Excel files must be saved as CSV first; PDF statements are not read.
- **Duplicates** are detected by same date + amount + description; two identical
  coffees on one day in a *new* file are both kept.
- **Simple tokens:** a simplified version of JWT, kept in the browser's localStorage.
- **No database migrations:** `create_all` makes missing tables but does not change
  existing ones; after a change to `models.py` run `python -m scripts.reset_db`.
  A real project would use Alembic.
- **Categories are shared** by all users (as in our ER diagram).

---

## 8. AI usage

*(Adapt this to what your professor asks for.)* The initial code was generated
with Claude (Anthropic) as permitted by the course instructor. Each team member
reviewed, ran and documented the files they own, and extended them with their
own changes, visible in the Git history.
