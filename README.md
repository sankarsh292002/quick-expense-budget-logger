# Quick Expense & Budget Logger

A web application to log or **import** expenses, **categorize them automatically**, and
monitor them against monthly budgets with charts.
Built for the *Software Development and Applications* course,
M.Eng. Engineering and Sustainable Technology Management (Industry 4.0).

| Layer | Technology | Where |
| --- | --- | --- |
| Web interface | HTML, CSS, JavaScript, Chart.js | `static/` |
| REST API | Python, FastAPI | `app/main.py`, `app/auth.py`, `app/routers/` |
| Processing engine | CSV reader, keyword categorizer, SQL aggregation | `app/importer.py`, `app/categorizer.py`, `app/summary.py` |
| Database | PostgreSQL via SQLAlchemy ORM (psycopg driver) | `app/database.py`, `app/models.py`, `app/services.py` |
| API testing | Postman collection | `postman/` |
| Automated tests | pytest | `tests/` |

## Key features

- Register and log in (hashed passwords, JWT tokens valid 24 h)
- Log, edit and delete expenses; live category suggestion while typing
- Import bank or spreadsheet CSV files with a preview: automatic categorization,
  duplicate detection, income rows skipped, nothing saved until confirmed
- Learns keyword rules from your corrections; manage your own rules in the dashboard
- Monthly budgets, overall or per category, with over-budget warnings
- Dashboard: 4 summary cards and 3 charts (by category, budget vs. spending, by day)
- Every user sees only their own data (401 / 403)
- 62 automated tests, Postman collection, SQL queries and a view for pgAdmin

Design notes: [docs/database.md](docs/database.md) (tables and design questions) and
[docs/queries.sql](docs/queries.sql) (example SQL queries and a view).

---

## 1. Run it

### What you need

- **Python 3.12 or 3.13** (from python.org, with "Add python.exe to PATH" ticked), or Anaconda
- **PostgreSQL** with **pgAdmin 4**, port 5432
- **Git**, **VS Code** and **Postman** (to test the API)
- In pgAdmin: Servers → PostgreSQL → Databases → Create → Database… named `expense_logger`

### Steps

| Step | Windows (PowerShell) | Mac (Terminal) |
| --- | --- | --- |
| Get the code | `git clone https://github.com/sankarsh292002/quick-expense-budget-logger.git` | same |
| Enter the folder | `cd quick-expense-budget-logger` | same |
| Create the virtual environment | `python -m venv venv` (or `py -3.13 -m venv venv`) | `python3 -m venv venv` |
| Activate it | `.\venv\Scripts\Activate.ps1` | `source venv/bin/activate` |
| Install packages | `python -m pip install -r requirements.txt` | same |
| Create your settings file | `copy .env.example .env` | `cp .env.example .env` |
| Generate a secret key | `python -c "import secrets; print(secrets.token_hex(32))"` | same |
| Edit `.env` | open `.env` in VS Code and set the two lines below | same |
| Load demo data | `python -m scripts.seed_demo` | same |
| Start the server | `python -m uvicorn app.main:app --reload` | same |

Before loading the demo data, open `.env` and set two lines:

```text
DATABASE_URL=postgresql+psycopg://postgres:YOUR_POSTGRES_PASSWORD@localhost:5432/expense_logger
SECRET_KEY=the 64 characters printed by the command above
```

`.env` is in `.gitignore`, so your password and key never reach GitHub. Every new terminal
needs the virtual environment activated again (you see `(venv)` at the start of the line).

Then open:

- **http://127.0.0.1:8000**: the dashboard; log in as `demo` / `demo1234`
- **http://127.0.0.1:8000/docs**: interactive API documentation (Swagger)

Stop the server with **Ctrl + C**. Reset the database with `python -m scripts.reset_db`.

### Tests

`python -m pytest -q` runs 62 automated tests: registration and login, JWT (forged and
expired tokens), 401 and 403, expense and budget CRUD and validation, the monthly summary,
the CSV importer and the import API. They use a temporary SQLite database, so they do not
touch your PostgreSQL data. To run them against PostgreSQL instead, see `tests/conftest.py`.

### Postman

1. Import → `postman/ExpenseLogger.postman_collection.json`
2. Collection → Variables → check that `baseUrl` is `http://127.0.0.1:8000` → Save
3. Right-click the collection → Run collection → Run. All checks should pass.
   The *Log in* request saves the token; every other request sends it automatically.
4. For *Import › Preview a CSV file*: Body → form-data → key `file` of type **File**
   → Select Files → `sample_data/transactions_simple.csv`. If Postman asks, enable
   Settings → General → Allow reading files outside working directory.

### Troubleshooting

| Error | Cause | Fix |
| --- | --- | --- |
| `python` is not recognized, or the Microsoft Store opens | Python is not installed or not in PATH | Install Python 3.13 from python.org with "Add python.exe to PATH"; turn off the Store aliases in Settings → Apps → Advanced app settings → App execution aliases; restart VS Code. Or use `py` instead of `python` |
| running scripts is disabled on this system | PowerShell blocks `Activate.ps1` | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then activate again. Or skip activation and use `.\venv\Scripts\python.exe` |
| `ModuleNotFoundError: No module named 'jwt'` (or `psycopg`, `dotenv`) | The wrong Python is active, e.g. another `.venv` auto-activated by VS Code | `deactivate`, then Ctrl+Shift+P → Python: Select Interpreter → the project's `venv`; run `python -m pip install -r requirements.txt` |
| `No module named 'conftest'` | A test file was run with the ▶️ button or saved outside `tests/` | Keep test files in `tests/` and run them with `python -m pytest` |
| `password authentication failed for user "postgres"` | Wrong password in `.env` | Fix `DATABASE_URL` in `.env`, save, restart the server |
| `connection refused` on port 5432 | PostgreSQL is not running | Windows: Services → postgresql-x64-… → Start |
| `database "expense_logger" does not exist` | Database not created | Create it in pgAdmin, spelled exactly `expense_logger` |
| `[Errno 10048]` / address already in use, or the page keeps loading | An old server is still running on port 8000 | Stop it with Ctrl + C or `taskkill /F /IM uvicorn.exe`, or use `python -m uvicorn app.main:app --reload --port 8001` |
| Postman: 401 on every request | Not logged in, or the token expired (24 h) | Run *Auth › Log in* again |
| Postman: *Request could not be sent* on Preview a CSV file | Postman cannot read the file | Select the CSV again (see Postman step 4) |

---

## 2. How it fits together

![Architecture](docs/architecture.png)

```text
 Browser (static/)                      Server (app/)                                 PostgreSQL
 ┌──────────────────────┐   HTTP+JSON   ┌────────────────────────────────────────┐    ┌────────────────┐
 │ index.html  layout   │ ────────────► │ routers/*.py      REST endpoints       │    │ users          │
 │ style.css   look     │               │ auth.py           hashing, JWT, 401    │    │ categories     │
 │ app.js      forms    │               │ schemas.py        validation           │    │ category_rules │
 │ import.js   CSV flow │ ◄──────────── │ importer.py       reads CSV files      │──► │ expenses       │
 │ charts.js   Chart.js │               │ categorizer.py    keyword matching     │ORM │ budgets        │
 │ api.js      fetch()  │               │ services.py       CRUD service classes │◄── │                │
 │                      │               │ summary.py        chart calculations   │    │                │
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

![ER diagram](docs/er-diagram.svg)

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

### Querying the database in pgAdmin

The PostgreSQL database `expense_logger` has the five tables above. The file
[docs/queries.sql](docs/queries.sql) contains example queries (category totals, spending
per day, budget vs. spending, built-in vs. user rules) and a view
`v_category_totals_by_month`. In pgAdmin: right-click `expense_logger` → Query Tool →
open the file, select one query and run it with **F5**. Run the demo data first
(`python -m scripts.seed_demo`) so the queries return rows.

---

## 4. REST API

All endpoints except register, login and `/api/health` need `Authorization: Bearer <token>`
(otherwise 401).

| Method | URL | Purpose | Success | Errors |
| --- | --- | --- | --- | --- |
| POST | `/api/auth/register` | Create an account, returns a token | 201 | 409, 422 |
| POST | `/api/auth/login` | Log in, returns a token | 200 | 401 |
| GET | `/api/auth/me` | Current user | 200 | 401 |
| GET / POST | `/api/categories` | List / add categories | 200 / 201 | 409, 422 |
| GET | `/api/expenses?month=YYYY-MM&category_id=` | List own expenses, newest first | 200 | 422 |
| POST | `/api/expenses` | Add an expense | 201 | 422 |
| GET / PUT / DELETE | `/api/expenses/{id}` | Read / edit / delete one | 200 / 200 / 204 | 403, 404, 422 |
| GET | `/api/budgets?month=YYYY-MM` | Budgets of a month | 200 | 422 |
| PUT | `/api/budgets` | Set a limit (creates or updates) | 200 | 422 |
| DELETE | `/api/budgets/{id}` | Remove a limit | 204 | 403, 404 |
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
| A | API Lead | `app/main.py`, `app/auth.py`, `app/routers/*`, `postman/*` |
| B | Database Lead | `app/database.py`, `app/models.py`, `app/schemas.py`, `app/services.py`, `app/summary.py`, `scripts/*`, `.env.example`, `docs/*` |
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
- **JWT tokens** (HS256, `sub` + `exp`), kept in the browser's localStorage. An HttpOnly cookie would protect the token better against XSS.
- **No server-side logout:** logging out only deletes the token in the browser; a
  token stays valid until it expires after 24 h.
- **No database migrations:** `create_all` makes missing tables but does not change
  existing ones; after a change to `models.py` run `python -m scripts.reset_db`.
  A real project would use Alembic.
- **Categories are shared** by all users (as in our ER diagram).

---

## 8. AI usage

The initial code was generated with Claude (Anthropic), as permitted by the course
instructor, and uploaded to the repository in one commit. After that, each member
reviewed, ran and documented the files they own, and made their own changes through
branches and reviewed pull requests (e.g. ER diagram v2, SQL queries and view, budget
tests, Postman authorization checks), visible in the Git history.