# Database design

## Overview
(2-3 sentences: which database, how many tables, how the app connects)

## Table: users
Purpose: Stores one row per person who registers
Primary key: user_id
Foreign keys: none (this table points to no other table)
Columns:
- user_id: integer, the primary key
- username: text up to 30 characters, must be unique, required
- email: text up to 120 characters, must be unique, required
- password_hash: text, required. Only a salted hash is stored, never the real password
- phone_number: text, optional
- created_at: timestamp, required

## Table: categories
Purpose: Stores the expense types (Food, Transit, Rent...) that expenses, budgets and rules point to
Primary key: category_id
Foreign keys: none
Columns:
- category_id: integer, the primary key
- name: text up to 40 characters, must be unique, required
- color: text of 7 characters (a hex colour used in the charts), required, default "#64748b"

## Table: expenses
Purpose: Stores one row per amount of money spent, entered by hand or imported from a bank file
Primary key: expense_id
Foreign keys:
- user_id -> users.user_id (who spent it)
- category_id -> categories.category_id (what type of spending it was)
Columns:
- expense_id: integer, the primary key
- user_id: integer, required
- category_id: integer, required
- amount: NUMERIC(12,2), required
- description: text up to 200 characters, required
- expense_date: date, required (when the money was spent)
- source: text up to 10 characters, required, default "manual" (either "manual" or "import")
- created_at: timestamp, required, set automatically (when the row was logged)

## Table: budgets
Purpose: Stores one monthly spending limit per user, either for one category or for everything
Primary key: budget_id
Foreign keys:
- user_id -> users.user_id (whose budget it is)
- category_id -> categories.category_id (which category it limits)
Columns:
- budget_id: integer, the primary key
- user_id: integer, required
- category_id: integer, optional. If empty, this is the overall monthly limit
- limit_amount: NUMERIC(12,2), required
- period_month: text of 7 characters in the form YYYY-MM, required
- Rule: a user can have only one budget per category per month

## Table: category_rules
Purpose: Stores one keyword that points to one category, used by the auto-categorizer
Primary key: rule_id
Foreign keys:
- user_id -> users.user_id (who owns the rule)
- category_id -> categories.category_id (the category the keyword leads to)
Columns:
- rule_id: integer, the primary key
- user_id: integer, optional. If empty, it is a built-in rule shared by all users
- category_id: integer, required
- keyword: text up to 60 characters, required, always stored in lowercase
- created_at: timestamp, required, set automatically
- Rule: a user can have only one rule per keyword

## Questions I should be able to answer
1. Why is money stored as NUMERIC(12,2) and not a float?
   Answer: NUMERIC stores exact decimal numbers with two digits after the point. A float stores an approximation, so adding prices like 0.10 and 0.20 can give a result off by a tiny fraction, and totals drift over many rows. NUMERIC(12,2) allows up to 10 digits before the point, which is far more than any expense needs.

2. What does it mean when category_rules.user_id is empty?
   Answer: An empty user_id means the rule is a built-in rule that belongs to nobody in particular, so every user gets it. A rule with a user_id belongs to one user, either because they added it or because the app learned it from their corrections. If a user's own rule and a built-in rule have the same keyword, the user's rule wins.

3. Why is budgets.category_id allowed to be empty?
   Answer: A budget with no category is the overall monthly limit that covers all of a user's spending. A budget with a category limits only that category, such as Food. Allowing it to be empty lets one table hold both kinds of budget.

4. What does .env do, and why is .env.example committed but .env not?
   Answer: .env holds the settings for one computer, mainly the DATABASE_URL with the real PostgreSQL password, and the app reads it when it starts. It is listed in .gitignore so the password never reaches GitHub. .env.example has the same lines with placeholder values and is safe to commit, so a teammate who clones the repo knows what to copy to .env and fill in.

## Where the database code lives
(one line each: database.py, models.py, schemas.py, services.py, summary.py)