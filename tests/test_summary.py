"""Tests for the calculations behind the dashboard. Owner: Member D (with Member B)."""
from test_expenses import add


def summary(client, auth, month="2026-11"):
    res = client.get(f"/api/summary?month={month}", headers=auth)
    assert res.status_code == 200
    return res.json()


def test_empty_month(client, auth):
    s = summary(client, auth)
    assert s["total"] == 0 and s["count"] == 0
    assert s["by_category"] == [] and s["budgets"] == []
    assert len(s["by_date"]) == 30  # November has 30 days, all zero
    assert all(d["total"] == 0 for d in s["by_date"])


def test_totals_and_category_breakdown(client, auth, categories):
    add(client, auth, categories["Food"], 10.10)
    add(client, auth, categories["Food"], 0.20)
    add(client, auth, categories["Transit"], 49.00)
    add(client, auth, categories["Food"], 100, day="2026-12-01")  # other month, must be ignored
    s = summary(client, auth)
    assert s["total"] == 59.30
    assert s["count"] == 3
    # biggest category first
    assert [(c["name"], c["total"]) for c in s["by_category"]] == [("Transit", 49.0), ("Food", 10.3)]


def test_by_date(client, auth, categories):
    add(client, auth, categories["Food"], 5, day="2026-11-03")
    add(client, auth, categories["Food"], 7, day="2026-11-03")
    by_date = {d["date"]: d["total"] for d in summary(client, auth)["by_date"]}
    assert by_date["2026-11-03"] == 12
    assert by_date["2026-11-04"] == 0


def test_budget_status_overall_and_category(client, auth, categories):
    add(client, auth, categories["Food"], 120)
    add(client, auth, categories["Transit"], 30)
    client.put("/api/budgets", headers=auth, json={"limit_amount": 200, "period_month": "2026-11"})
    client.put("/api/budgets", headers=auth, json={"limit_amount": 100, "period_month": "2026-11", "category_id": categories["Food"]})

    budgets = {b["name"]: b for b in summary(client, auth)["budgets"]}
    assert budgets["Overall"]["spent"] == 150 and budgets["Overall"]["over_budget"] is False
    assert budgets["Overall"]["percent_used"] == 75.0
    assert budgets["Food"]["spent"] == 120 and budgets["Food"]["over_budget"] is True
    assert budgets["Food"]["remaining"] == -20


def test_exactly_at_limit_is_not_over(client, auth, categories):
    add(client, auth, categories["Food"], 50)
    client.put("/api/budgets", headers=auth, json={"limit_amount": 50, "period_month": "2026-11"})
    assert summary(client, auth)["budgets"][0]["over_budget"] is False


def test_setting_budget_twice_updates_instead_of_duplicating(client, auth):
    client.put("/api/budgets", headers=auth, json={"limit_amount": 100, "period_month": "2026-11"})
    client.put("/api/budgets", headers=auth, json={"limit_amount": 250, "period_month": "2026-11"})
    budgets = client.get("/api/budgets?month=2026-11", headers=auth).json()
    assert len(budgets) == 1 and budgets[0]["limit_amount"] == 250


def test_december_rolls_over_to_next_year(client, auth, categories):
    add(client, auth, categories["Food"], 9, day="2026-12-31")
    add(client, auth, categories["Food"], 99, day="2027-01-01")
    s = summary(client, auth, "2026-12")
    assert s["total"] == 9 and len(s["by_date"]) == 31
