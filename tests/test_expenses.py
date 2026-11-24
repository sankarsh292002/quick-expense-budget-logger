"""Tests for expense CRUD and validation. Owner: Member D."""
from conftest import register


def add(client, auth, category_id, amount=10.0, day="2026-11-05", description="Test"):
    return client.post(
        "/api/expenses",
        headers=auth,
        json={"amount": amount, "description": description, "category_id": category_id, "expense_date": day},
    )


def test_default_categories_exist(client, categories):
    assert {"Food", "Transit", "Utilities"} <= set(categories)


def test_create_list_get(client, auth, categories):
    res = add(client, auth, categories["Food"], 3.5, description="Coffee")
    assert res.status_code == 201
    expense_id = res.json()["expense_id"]

    listed = client.get("/api/expenses?month=2026-11", headers=auth).json()
    assert [e["description"] for e in listed] == ["Coffee"]
    assert client.get(f"/api/expenses/{expense_id}", headers=auth).json()["amount"] == 3.5


def test_list_is_newest_first_and_filters_by_month(client, auth, categories):
    add(client, auth, categories["Food"], day="2026-11-01", description="early")
    add(client, auth, categories["Food"], day="2026-11-20", description="late")
    add(client, auth, categories["Food"], day="2026-10-31", description="october")
    listed = client.get("/api/expenses?month=2026-11", headers=auth).json()
    assert [e["description"] for e in listed] == ["late", "early"]


def test_filter_by_category(client, auth, categories):
    add(client, auth, categories["Food"], description="lunch")
    add(client, auth, categories["Transit"], description="bus")
    listed = client.get(f"/api/expenses?month=2026-11&category_id={categories['Transit']}", headers=auth).json()
    assert [e["description"] for e in listed] == ["bus"]


def test_update(client, auth, categories):
    expense_id = add(client, auth, categories["Food"], 5).json()["expense_id"]
    res = client.put(
        f"/api/expenses/{expense_id}",
        headers=auth,
        json={"amount": 7.25, "description": "Bigger lunch", "category_id": categories["Food"], "expense_date": "2026-11-06"},
    )
    assert res.status_code == 200
    assert res.json()["amount"] == 7.25


def test_delete_then_404(client, auth, categories):
    expense_id = add(client, auth, categories["Food"]).json()["expense_id"]
    assert client.delete(f"/api/expenses/{expense_id}", headers=auth).status_code == 204
    assert client.delete(f"/api/expenses/{expense_id}", headers=auth).status_code == 404


def test_invalid_input_returns_422(client, auth, categories):
    assert add(client, auth, categories["Food"], amount=-5).status_code == 422          # negative
    assert add(client, auth, categories["Food"], description="").status_code == 422     # empty text
    assert add(client, auth, 9999).status_code == 422                                   # unknown category
    assert client.get("/api/expenses?month=2026-13", headers=auth).status_code == 422   # bad month


def test_users_cannot_see_each_others_expenses(client, auth, categories):
    expense_id = add(client, auth, categories["Food"]).json()["expense_id"]
    other = register(client, "mallory")
    assert client.get("/api/expenses?month=2026-11", headers=other).json() == []
    # authenticated, but not the owner -> 403 Forbidden (slide 64)
    assert client.get(f"/api/expenses/{expense_id}", headers=other).status_code == 403
    update = {"amount": 1, "description": "hacked", "category_id": categories["Food"], "expense_date": "2026-11-05"}
    assert client.put(f"/api/expenses/{expense_id}", headers=other, json=update).status_code == 403
    assert client.delete(f"/api/expenses/{expense_id}", headers=other).status_code == 403
    # the owner still has the expense, unchanged
    assert client.get(f"/api/expenses/{expense_id}", headers=auth).json()["description"] != "hacked"


def test_missing_expense_is_404(client, auth):
    assert client.get("/api/expenses/999999", headers=auth).status_code == 404
