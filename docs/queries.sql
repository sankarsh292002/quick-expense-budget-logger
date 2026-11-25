-- =====================================================================
-- queries.sql - the SQL behind the dashboard charts (runnable in pgAdmin)
--
-- Owner: Member B (Database)
--
-- How to run: pgAdmin -> expense_logger -> Tools -> Query Tool.
-- Select ONE query (from its comment to its semicolon) and press F5.
--
-- Example parameters used below:
--   user  = 'demo'        (the demo user created by scripts/seed_demo.py)
--   month = '2026-11'     (November 2026; change the two DATE values to
--                          look at another month)
--
-- These queries mirror app/summary.py, so they return the same numbers
-- as the dashboard.
--
-- Tables used:
--   users, categories, expenses, budgets, category_rules
-- =====================================================================


-- ---------------------------------------------------------------------
-- 1) Spending per category for one month        (donut chart)
--
-- JOIN: every expense row stores only a category_id (a number). The JOIN
--       to categories looks up the matching category name.
-- WHERE: keeps only this user's expenses inside the month. The end date
--       is exclusive (< 1 Dec) so the whole of 30 Nov is included.
-- GROUP BY: collapses all expense rows of one category into one row, so
--       SUM(amount) adds up the money per category.
-- ORDER BY total DESC: biggest category first (Rent should be on top).
-- ---------------------------------------------------------------------
SELECT c.name        AS category,
       c.color       AS color,
       SUM(e.amount) AS total
FROM expenses e
JOIN categories c ON c.category_id = e.category_id
JOIN users u      ON u.user_id     = e.user_id
WHERE u.username = 'demo'
  AND e.expense_date >= DATE '2026-11-01'
  AND e.expense_date <  DATE '2026-12-01'
GROUP BY c.category_id, c.name, c.color
ORDER BY total DESC;


-- ---------------------------------------------------------------------
-- 2) Spending per day for one month             ("Spending by date")
--
-- generate_series creates one row for EVERY day of the month, and the
-- LEFT JOIN attaches that day's expenses. Days without spending stay in
-- the result with a total of 0 (COALESCE turns the empty SUM into 0),
-- exactly like the chart, which shows every day, not just busy ones.
-- The user filter sits in the JOIN condition, not in WHERE, so that the
-- empty days are not thrown away.
-- ---------------------------------------------------------------------
SELECT d.day::date                       AS day,
       COALESCE(SUM(e.amount), 0)        AS total
FROM generate_series(DATE '2026-11-01', DATE '2026-11-30', INTERVAL '1 day') AS d(day)
LEFT JOIN expenses e
       ON e.expense_date = d.day::date
      AND e.user_id = (SELECT user_id FROM users WHERE username = 'demo')
GROUP BY d.day
ORDER BY d.day;


-- ---------------------------------------------------------------------
-- 3) Budget vs spending for one month           (horizontal bar chart)
--
-- One row per budget. A budget with no category (category_id IS NULL)
-- is the OVERALL limit, so it is compared with everything the user
-- spent. A category budget is compared with that category only.
-- LEFT JOIN: a budget with no matching expenses still shows up, with
-- spent = 0 (never lose a row just because nothing was spent yet).
-- The month filter is inside the JOIN condition for the same reason.
-- percent_used = spent / limit * 100.
-- ---------------------------------------------------------------------
SELECT COALESCE(c.name, 'Overall')                              AS budget_for,
       b.limit_amount,
       COALESCE(SUM(e.amount), 0)                               AS spent,
       b.limit_amount - COALESCE(SUM(e.amount), 0)              AS remaining,
       ROUND(COALESCE(SUM(e.amount), 0) / b.limit_amount * 100, 1) AS percent_used
FROM budgets b
JOIN users u            ON u.user_id     = b.user_id
LEFT JOIN categories c  ON c.category_id = b.category_id
LEFT JOIN expenses e    ON e.user_id = b.user_id
                       AND (b.category_id IS NULL OR e.category_id = b.category_id)
                       AND e.expense_date >= DATE '2026-11-01'
                       AND e.expense_date <  DATE '2026-12-01'
WHERE u.username = 'demo'
  AND b.period_month = '2026-11'
GROUP BY b.budget_id, c.name, b.limit_amount, b.category_id
ORDER BY (b.category_id IS NOT NULL), c.name;   -- Overall first, then A-Z


-- ---------------------------------------------------------------------
-- 4) Keyword rules with their category          (auto-categorization)
--
-- category_rules.user_id is NULL for the built-in rules every user
-- gets, and set for rules a user added or the app learned from that
-- user's corrections. The LEFT JOIN to users keeps the built-in rules
-- (they have no user). A user's own rule beats a built-in rule.
-- ---------------------------------------------------------------------
SELECT r.keyword,
       c.name AS category,
       CASE WHEN r.user_id IS NULL THEN 'built-in'
            ELSE 'user: ' || u.username END AS rule_type
FROM category_rules r
JOIN categories c  ON c.category_id = r.category_id
LEFT JOIN users u  ON u.user_id     = r.user_id
ORDER BY (r.user_id IS NULL) DESC,   -- built-in rules first
         c.name, r.keyword;

-- 4b) How many built-in vs user rules are there?
SELECT CASE WHEN user_id IS NULL THEN 'built-in' ELSE 'user' END AS rule_type,
       COUNT(*) AS number_of_rules
FROM category_rules
GROUP BY (user_id IS NULL);


-- ---------------------------------------------------------------------
-- 5) A VIEW: category totals per user and month
--
-- A view is a saved SELECT with a name. It stores no data of its own:
-- every time you read from it, PostgreSQL runs the query again on the
-- current rows. So the totals are always up to date, and nobody has to
-- copy the long JOIN + GROUP BY. CREATE OR REPLACE lets you run this
-- script again without an error.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_category_totals_by_month AS
SELECT e.user_id,
       TO_CHAR(e.expense_date, 'YYYY-MM') AS month,
       c.name                             AS category,
       SUM(e.amount)                      AS total
FROM expenses e
JOIN categories c ON c.category_id = e.category_id
GROUP BY e.user_id, TO_CHAR(e.expense_date, 'YYYY-MM'), c.name;

-- Example: the same numbers as query 1, now with a short SELECT
SELECT category, total
FROM v_category_totals_by_month
WHERE user_id = (SELECT user_id FROM users WHERE username = 'demo')
  AND month = '2026-11'
ORDER BY total DESC;