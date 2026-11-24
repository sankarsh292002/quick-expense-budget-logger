"""
routers/imports.py - upload a CSV file of transactions and import it.

Owner: Member A (API). Reading the file: app/importer.py; choosing categories:
app/categorizer.py (both Member D).

Importing is two steps, so the user stays in control:

  1. POST /api/import/preview   (form-data, field "file" = the CSV)
     -> reads the file, suggests a category for every row, flags duplicates.
        NOTHING is saved yet.
  2. POST /api/import/commit    (JSON: the rows the user confirmed)
     -> saves the expenses. Where the user changed a suggested category,
        a keyword rule is learned so the next import gets it right.
"""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..categorizer import merchant_key
from ..database import get_db
from ..importer import ImportFormatError, parse_transactions
from ..security import get_current_user

router = APIRouter(prefix="/api/import", tags=["import"])

MAX_FILE_BYTES = 2 * 1024 * 1024  # 2 MB is thousands of transactions


@router.post("/preview", response_model=schemas.ImportPreviewOut)
async def preview_import(
    file: UploadFile = File(..., description="CSV export from your bank or a spreadsheet"),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    raw = await file.read()
    if len(raw) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 2 MB)")
    try:
        parsed = parse_transactions(raw)
    except ImportFormatError as err:
        raise HTTPException(status_code=422, detail=str(err))

    categorizer = crud.build_categorizer(db, user.user_id)
    categories_by_name = {c.name.lower(): c.category_id for c in crud.list_categories(db)}
    other_id = categories_by_name["other"]

    existing = set()
    if parsed.rows:
        dates = [r.expense_date for r in parsed.rows]
        existing = crud.existing_expense_keys(db, user.user_id, min(dates), max(dates))

    rows = []
    for r in parsed.rows:
        hint_id = categories_by_name.get((r.category_hint or "").lower())
        match = None if hint_id else categorizer.categorize(r.description)
        rows.append({
            "line": r.line,
            "expense_date": r.expense_date,
            "description": r.description,
            "amount": r.amount,
            "category_id": hint_id or (match.category_id if match else other_id),
            "matched_keyword": match.keyword if match else None,
            "match_source": "file" if hint_id else (match.source if match else None),
            "duplicate": (r.expense_date, r.amount, r.description.lower()) in existing,
        })
    return {
        "rows": rows,
        "errors": [{"line": line, "message": msg} for line, msg in parsed.errors],
        "skipped_income": parsed.skipped_income,
    }


@router.post("/commit", response_model=schemas.ImportCommitOut, status_code=status.HTTP_201_CREATED)
def commit_import(
    data: schemas.ImportCommitIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    valid_ids = {c.category_id: c.name for c in crud.list_categories(db)}
    if any(row.category_id not in valid_ids for row in data.rows):
        raise HTTPException(status_code=422, detail="Unknown category in one of the rows")

    learned: dict[str, int] = {}
    for row in data.rows:
        db.add(models.Expense(
            user_id=user.user_id,
            category_id=row.category_id,
            amount=round(row.amount, 2),
            description=row.description.strip(),
            expense_date=row.expense_date,
            source="import",
        ))
        corrected = row.suggested_category_id is not None and row.suggested_category_id != row.category_id
        if data.learn and corrected:
            keyword = merchant_key(row.description)
            if keyword:
                learned[keyword] = row.category_id  # last correction wins

    for keyword, category_id in learned.items():
        crud.save_user_rule(db, user.user_id, keyword, category_id, commit=False)
    db.commit()  # all expenses and rules are saved together, or none of them

    return {
        "imported": len(data.rows),
        "rules_learned": [{"keyword": k, "category_name": valid_ids[c]} for k, c in learned.items()],
    }
