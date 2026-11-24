"""Tests for monthly budgets (PUT/GET/DELETE /api/budgets). Owner: Member D."""
from conftest import register

MONTH = "2026-11"


def set_budget(client, auth, limit, month=MONTH, category_id=None):
    body = {"limit_amount": limit, "period_month": month}
    if category_id is not None:
        body["category_id"] = category_id
    return client.put("/api/budgets", headers=auth, json=body)


def list_budgets(client, auth, month=MONTH):
    res = client.get(f"/api/budgets?month={month}", headers=auth)
    assert res.status_code == 200
    return res.json()


def test_set_overall_budget(client, auth):
    res = set_budget(client, auth, 1400)
    assert res.status_code == 200
    budget = res.json()
    assert budget["limit_amount"] == 1400
    assert budget["period_month"] == MONTH
    assert budget["category_id"] is None  # no category = overall limit for the month


def test_category_budget_is_listed_only_for_its_month(client, auth, categories):
    set_budget(client, auth, 250, category_id=categories["Food"])
    assert [b["category_id"] for b in list_budgets(client, auth)] == [categories["Food"]]
    assert list_budgets(client, auth, month="2026-12") == []


def test_same_budget_twice_updates_the_limit(client, auth, categories):
    # PUT is an "upsert": same user + month + category updates the existing row
    first = set_budget(client, auth, 100, category_id=categories["Food"]).json()
    second = set_budget(client, auth, 180, category_id=categories["Food"]).json()
    budgets = list_budgets(client, auth)
    assert len(budgets) == 1
    assert second["budget_id"] == first["budget_id"]
    assert budgets[0]["limit_amount"] == 180


def test_overall_and_category_budgets_are_separate(client, auth, categories):
    set_budget(client, auth, 1400)
    set_budget(client, auth, 250, category_id=categories["Food"])
    assert len(list_budgets(client, auth)) == 2


def test_invalid_budgets_are_rejected(client, auth):
    assert set_budget(client, auth, 0).status_code == 422                  # limit must be > 0
    assert set_budget(client, auth, -50).status_code == 422                # negative limit
    assert set_budget(client, auth, 100, month="2026-13").status_code == 422  # no 13th month
    assert set_budget(client, auth, 100, month="11-2026").status_code == 422  # wrong format
    assert set_budget(client, auth, 100, category_id=9999).status_code == 422  # unknown category
    assert client.get("/api/budgets", headers=auth).status_code == 422     # month is required


def test_delete_budget_then_404(client, auth):
    budget_id = set_budget(client, auth, 300).json()["budget_id"]
    assert client.delete(f"/api/budgets/{budget_id}", headers=auth).status_code == 204
    assert list_budgets(client, auth) == []
    assert client.delete(f"/api/budgets/{budget_id}", headers=auth).status_code == 404


def test_other_user_cannot_delete_my_budget(client, auth):
    budget_id = set_budget(client, auth, 300).json()["budget_id"]
    mallory = register(client, "mallory")
    # logged in (so not 401), but not the owner -> 403 Forbidden
    assert client.delete(f"/api/budgets/{budget_id}", headers=mallory).status_code == 403
    assert [b["budget_id"] for b in list_budgets(client, auth)] == [budget_id]


def test_budgets_are_private(client, auth):
    set_budget(client, auth, 300)
    mallory = register(client, "mallory")
    assert list_budgets(client, mallory) == []


def test_budgets_need_login(client):
    assert client.get(f"/api/budgets?month={MONTH}").status_code == 401
    assert client.put("/api/budgets", json={"limit_amount": 100, "period_month": MONTH}).status_code == 401