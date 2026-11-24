// app.js - the behaviour of the page: forms, table, and refreshing data.
// Owner: Member C (Frontend)
//
// The core pattern, used everywhere:
//   1. the user does something (submit, click, change month)
//   2. we call the API (api.js)
//   3. we call refresh(), which asks the server for the latest list and
//      summary and redraws the table, cards and charts. No page reload.

const $ = (id) => document.getElementById(id);

const state = {
  categories: [],      // [{category_id, name, color}]
  expenses: [],        // expenses currently shown in the table
  editingId: null,     // expense_id being edited, or null when adding
  categoryTouched: false, // true once the user picked a category by hand
};

// ---------------- helpers ----------------

function currentMonth() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

function todayISO() {
  const now = new Date();
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset()); // local date, not UTC
  return now.toISOString().slice(0, 10);
}

let toastTimer;
function toast(message, isError = false) {
  const el = $("toast");
  el.textContent = message;
  el.classList.toggle("error", isError);
  el.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.add("hidden"), 3000);
}

function categoryById(id) {
  return state.categories.find((c) => c.category_id === id) || { name: "?", color: "#94a3b8" };
}

// Build an element safely. Using textContent (never innerHTML with user
// input) means a description like "<script>" is shown as text, not run.
function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  Object.assign(node, props);
  for (const child of children) node.append(child);
  return node;
}

// ---------------- screens ----------------

function showAuth() {
  $("app-screen").classList.add("hidden");
  $("auth-screen").classList.remove("hidden");
}

async function showApp(user) {
  $("auth-screen").classList.add("hidden");
  $("app-screen").classList.remove("hidden");
  $("user-name").textContent = `Signed in as ${user.username}`;
  if (!$("month").value) $("month").value = currentMonth();
  resetExpenseForm();
  await loadCategories();
  await Promise.all([refresh(), loadRules()]); // loadRules is in import.js
}

// ---------------- data loading ----------------

async function loadCategories() {
  state.categories = await api.categories();
  const options = () => state.categories.map((c) => el("option", { value: c.category_id, textContent: c.name }));

  $("expense-category").replaceChildren(...options());
  $("budget-category").replaceChildren(el("option", { value: "", textContent: "Overall (all categories)" }), ...options());
  $("filter-category").replaceChildren(el("option", { value: "", textContent: "All categories" }), ...options());
  $("rule-category").replaceChildren(...options());
}

async function refresh() {
  const month = $("month").value;
  const filter = $("filter-category").value;
  try {
    // Ask for both at the same time; wait until both have arrived.
    const [expenses, summary] = await Promise.all([api.expenses(month, filter), api.summary(month)]);
    state.expenses = expenses;
    renderTable(expenses);
    renderSummary(summary);
  } catch (err) {
    toast(err.message, true);
  }
}

// ---------------- rendering ----------------

function renderTable(expenses) {
  $("history-empty").classList.toggle("hidden", expenses.length > 0);
  const rows = expenses.map((e) => {
    const cat = categoryById(e.category_id);
    const editBtn = el("button", { className: "icon-btn", textContent: "Edit", onclick: () => startEdit(e) });
    const delBtn = el("button", { className: "icon-btn danger", textContent: "Delete", onclick: () => removeExpense(e) });
    const row = el("tr", {},
      el("td", { textContent: e.expense_date }),
      el("td", {}, e.description, e.source === "import" ? el("span", { className: "badge", textContent: "imported" }) : ""),
      el("td", {}, el("span", { className: "chip" }, el("span", { className: "dot", style: `background:${cat.color}` }), cat.name)),
      el("td", { className: "num", textContent: euro.format(e.amount) }),
      el("td", { className: "num" }, editBtn, delBtn),
    );
    if (e.expense_id === state.editingId) row.classList.add("editing");
    return row;
  });
  $("expense-rows").replaceChildren(...rows);
}

function renderSummary(s) {
  $("stat-total").textContent = euro.format(s.total);
  $("stat-count").textContent = s.count;
  $("stat-top").textContent = s.by_category.length ? s.by_category[0].name : "–";

  // Overall budget card
  const overall = s.budgets.find((b) => b.category_id === null);
  const bar = $("overall-bar");
  if (overall) {
    $("stat-remaining").textContent = euro.format(overall.remaining);
    $("stat-remaining").classList.toggle("over", overall.over_budget);
    bar.style.width = `${Math.min(overall.percent_used, 100)}%`;
    bar.classList.toggle("over", overall.over_budget);
    bar.classList.toggle("warn", !overall.over_budget && overall.percent_used >= 80);
  } else {
    $("stat-remaining").textContent = "No limit set";
    $("stat-remaining").classList.remove("over");
    bar.style.width = "0";
  }

  // Budget list under the chart (with a remove button per budget)
  $("budget-list").replaceChildren(...s.budgets.map((b) => {
    const text = el("span", {
      className: b.over_budget ? "over" : "",
      textContent: `${b.name}: ${euro.format(b.spent)} of ${euro.format(b.limit_amount)} (${b.percent_used}%)${b.over_budget ? " – over budget" : ""}`,
    });
    const remove = el("button", { className: "icon-btn danger", textContent: "Remove", onclick: () => removeBudget(b) });
    return el("li", {}, text, remove);
  }));

  drawCategoryChart(s.by_category);
  drawBudgetChart(s.budgets);
  drawDateChart(s.by_date);
}

// ---------------- expense form (add + edit) ----------------

function readExpenseForm() {
  const f = $("expense-form");
  return {
    amount: parseFloat(f.amount.value),
    description: f.description.value.trim(),
    category_id: Number(f.category_id.value),
    expense_date: f.expense_date.value,
  };
}

function resetExpenseForm() {
  const f = $("expense-form");
  f.reset();
  f.expense_date.value = todayISO();
  state.editingId = null;
  state.categoryTouched = false;
  $("category-hint").textContent = "";
  $("form-title").textContent = "Add expense";
  $("expense-submit").textContent = "Add expense";
  $("cancel-edit").classList.add("hidden");
}

function startEdit(expense) {
  const f = $("expense-form");
  f.amount.value = expense.amount;
  f.description.value = expense.description;
  f.category_id.value = expense.category_id;
  f.expense_date.value = expense.expense_date;
  state.editingId = expense.expense_id;
  state.categoryTouched = true; // keep the saved category, do not auto-suggest
  $("category-hint").textContent = "";
  $("form-title").textContent = "Edit expense";
  $("expense-submit").textContent = "Save changes";
  $("cancel-edit").classList.remove("hidden");
  renderTable(state.expenses);
  f.scrollIntoView({ behavior: "smooth", block: "center" });
}

$("expense-form").addEventListener("submit", async (event) => {
  event.preventDefault(); // stop the browser from reloading the page
  const data = readExpenseForm();
  try {
    if (state.editingId) {
      await api.updateExpense(state.editingId, data);
      toast("Expense updated");
    } else {
      await api.addExpense(data);
      toast("Expense added");
    }
    // If the expense is in another month, jump to that month so it is visible.
    const month = data.expense_date.slice(0, 7);
    if (month !== $("month").value) $("month").value = month;
    resetExpenseForm();
    await refresh();
  } catch (err) {
    toast(err.message, true);
  }
});

// Auto-categorize while typing: 400 ms after the user stops typing, ask the
// server which category the description belongs to (POST /api/categorize).
let suggestTimer;
$("expense-form").description.addEventListener("input", (event) => {
  clearTimeout(suggestTimer);
  const text = event.target.value.trim();
  if (state.categoryTouched || text.length < 3) return;
  suggestTimer = setTimeout(async () => {
    try {
      const result = await api.categorize(text);
      if (state.categoryTouched) return;
      $("expense-category").value = result.category_id;
      $("category-hint").textContent = result.matched_keyword
        ? `Suggested ${result.category_name} (keyword "${result.matched_keyword}")`
        : "No keyword matched; choose a category";
    } catch { /* suggestions are optional */ }
  }, 400);
});
$("expense-category").addEventListener("change", () => {
  state.categoryTouched = true;
  $("category-hint").textContent = "";
});

$("cancel-edit").addEventListener("click", () => {
  resetExpenseForm();
  renderTable(state.expenses);
});

async function removeExpense(expense) {
  if (!confirm(`Delete "${expense.description}" (${euro.format(expense.amount)})?`)) return;
  try {
    await api.deleteExpense(expense.expense_id);
    if (state.editingId === expense.expense_id) resetExpenseForm();
    toast("Expense deleted");
    await refresh();
  } catch (err) {
    toast(err.message, true);
  }
}

// ---------------- budgets ----------------

$("budget-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const f = event.target;
  try {
    await api.setBudget({
      limit_amount: parseFloat(f.limit_amount.value),
      period_month: $("month").value,
      category_id: f.category_id.value ? Number(f.category_id.value) : null,
    });
    f.limit_amount.value = "";
    toast("Budget saved");
    await refresh();
  } catch (err) {
    toast(err.message, true);
  }
});

async function removeBudget(budget) {
  try {
    await api.deleteBudget(budget.budget_id);
    toast("Budget removed");
    await refresh();
  } catch (err) {
    toast(err.message, true);
  }
}

// ---------------- filters ----------------

$("month").addEventListener("change", refresh);
$("filter-category").addEventListener("change", refresh);

// ---------------- login / register ----------------

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t === tab));
    $("login-form").classList.toggle("hidden", tab.dataset.tab !== "login");
    $("register-form").classList.toggle("hidden", tab.dataset.tab !== "register");
  });
});

$("login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const f = event.target;
  try {
    const result = await api.login(f.username.value.trim(), f.password.value);
    api.token = result.access_token;
    f.reset();
    await showApp(result.user);
  } catch (err) {
    toast(err.message, true);
  }
});

$("register-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const f = event.target;
  try {
    const result = await api.register({
      username: f.username.value.trim(),
      email: f.email.value.trim(),
      password: f.password.value,
      phone_number: f.phone_number.value.trim() || null,
    });
    api.token = result.access_token;
    f.reset();
    toast("Account created");
    await showApp(result.user);
  } catch (err) {
    toast(err.message, true);
  }
});

$("logout-btn").addEventListener("click", () => {
  api.token = null;
  showAuth();
});

window.addEventListener("logged-out", () => {
  toast("Please log in again", true);
  showAuth();
});

// ---------------- start ----------------

(async function start() {
  if (!api.token) return showAuth();
  try {
    await showApp(await api.me()); // token still valid -> straight to dashboard
  } catch {
    api.token = null;
    showAuth();
  }
})();
