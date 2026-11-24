"""
main.py - the starting point of the application.

Owner: Member A (API)

Run it with:   uvicorn app.main:app --reload
Then open:     http://127.0.0.1:8000        (the dashboard)
               http://127.0.0.1:8000/docs   (interactive API documentation)

What happens at startup
1. The tables from models.py are created in PostgreSQL if they do not exist
   (the connection details come from the .env file, see app/database.py).
2. The default categories and keyword rules are inserted if they are missing.
3. The API routes are registered under /api/...
4. Everything else (/, /css/..., /js/...) is served from the static/ folder,
   so the frontend and the API share one address and we avoid CORS problems.
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .services import CategoryService, RuleService
from .database import Base, SessionLocal, engine
from .routers import auth, budgets, categories, expenses, imports, rules, summary

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "static"
SAMPLES_DIR = ROOT / "sample_data"


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        CategoryService.seed_defaults(db)
        RuleService.seed_defaults(db)
    yield


app = FastAPI(
    title="Quick Expense & Budget Logger",
    description="Log or import expenses, categorize them automatically, and monitor them against monthly budgets.",
    version="2.0.0",
    lifespan=lifespan,
)

app.include_router(auth.router)
app.include_router(categories.router)
app.include_router(expenses.router)
app.include_router(budgets.router)
app.include_router(summary.router)
app.include_router(imports.router)
app.include_router(rules.router)


@app.get("/api/health", tags=["health"])
def health():
    return {"status": "ok"}


# Example CSV files, downloadable from the dashboard ("Sample file").
app.mount("/samples", StaticFiles(directory=SAMPLES_DIR), name="samples")

# Must come LAST: it catches every path the API routes did not.
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
