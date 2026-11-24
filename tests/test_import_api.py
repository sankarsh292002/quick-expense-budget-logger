"""Tests for the import and rules endpoints. Owner: Member D."""
from pathlib import Path

SAMPLE = Path(__file__).resolve().parent.parent / "sample_data" / "bank_export_de.csv"


def preview(client, auth, content=None, name="export.csv"):
    content = content if content is not None else SAMPLE.read_bytes()
    return client.post("/api/import/preview", headers=auth, files={"file": (name, content, "text/csv")})


def commit(client, auth, rows, learn=True):
    body = {"learn": learn, "rows": [
        {k: r[k] for k in ("expense_date", "description", "amount", "category_id")}
        | {"suggested_category_id": r.get("suggested_category_id", r["category_id"])}
        for r in rows
    ]}
    return client.post("/api/import/commit", headers=auth, json=body)


def test_preview_suggests_categories_and_saves_nothing(client, auth, categories):
    res = preview(client, auth)
    assert res.status_code == 200
    data = res.json()
    assert len(data["rows"]) == 25 and data["skipped_income"] == 2
    by_text = {r["description"].split(" - ")[0]: r for r in data["rows"]}
    assert by_text["REWE Markt GmbH"]["category_id"] == categories["Food"]
    assert by_text["REWE Markt GmbH"]["matched_keyword"] == "rewe"
    assert by_text["Stadtwerke Muenchen"]["category_id"] == categories["Utilities"]
    assert by_text["Stadtbibliothek Muenchen"]["category_id"] == categories["Other"]
    assert by_text["Stadtbibliothek Muenchen"]["match_source"] is None     # needs review
    assert client.get("/api/expenses?month=2026-10", headers=auth).json() == []  # nothing saved


def test_commit_then_preview_again_flags_duplicates(client, auth):
    rows = preview(client, auth).json()["rows"]
    res = commit(client, auth, rows)
    assert res.status_code == 201 and res.json()["imported"] == 25
    expenses = client.get("/api/expenses?month=2026-10", headers=auth).json()
    assert len(expenses) == 25 and all(e["source"] == "import" for e in expenses)
    assert all(r["duplicate"] for r in preview(client, auth).json()["rows"])
    assert client.get("/api/summary?month=2026-10", headers=auth).json()["total"] == round(sum(r["amount"] for r in rows), 2)


def test_correction_is_learned_for_next_import(client, auth, categories):
    rows = preview(client, auth).json()["rows"]
    library = next(r for r in rows if r["description"].startswith("Stadtbibliothek"))
    corrected = dict(library, suggested_category_id=library["category_id"], category_id=categories["Entertainment"])
    res = commit(client, auth, [corrected])
    assert res.json()["rules_learned"] == [{"keyword": "stadtbibliothek", "category_name": "Entertainment"}]

    again = next(r for r in preview(client, auth).json()["rows"] if r["description"].startswith("Stadtbibliothek"))
    assert again["category_id"] == categories["Entertainment"] and again["match_source"] == "learned"


def test_category_column_in_file_is_used(client, auth, categories):
    raw = b"date,description,amount,category\n2026-11-01,Something odd,10,Health\n"
    row = preview(client, auth, raw).json()["rows"][0]
    assert row["category_id"] == categories["Health"] and row["match_source"] == "file"


def test_unreadable_file_and_unknown_category(client, auth):
    assert preview(client, auth, b"just some text").status_code == 422
    bad = [{"expense_date": "2026-11-01", "description": "x", "amount": 1, "category_id": 9999}]
    assert commit(client, auth, bad).status_code == 422
    assert client.post("/api/import/preview", files={"file": ("a.csv", b"x", "text/csv")}).status_code == 401


def test_rules_crud_and_categorize(client, auth, categories):
    res = client.post("/api/rules", headers=auth, json={"keyword": "Copyshop", "category_id": categories["Shopping"]})
    assert res.status_code == 201 and res.json()["keyword"] == "copyshop" and res.json()["built_in"] is False
    rule_id = res.json()["rule_id"]
    assert client.post("/api/rules", headers=auth, json={"keyword": "copyshop", "category_id": 1}).status_code == 409

    test = client.post("/api/categorize", headers=auth, json={"description": "COPYSHOP Uni Druck"}).json()
    assert test["category_name"] == "Shopping" and test["match_source"] == "learned"

    rules = client.get("/api/rules", headers=auth).json()
    built_in = next(r for r in rules if r["built_in"])
    assert client.delete(f"/api/rules/{built_in['rule_id']}", headers=auth).status_code == 403
    assert client.delete(f"/api/rules/{rule_id}", headers=auth).status_code == 204


def test_other_users_rules_are_private(client, auth, categories):
    from conftest import register
    client.post("/api/rules", headers=auth, json={"keyword": "secretshop", "category_id": categories["Food"]})
    other = register(client, "ben")
    result = client.post("/api/categorize", headers=other, json={"description": "secretshop"}).json()
    assert result["matched_keyword"] is None
