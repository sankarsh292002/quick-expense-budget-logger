const API = "/api";
const money = new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR" });

const form = document.getElementById("expense-form");
const amountInput = document.getElementById("amount");
const descInput = document.getElementById("description");
const dateInput = document.getElementById("spent_on");
const categorySelect = document.getElementById("category");
const errorEl = document.getElementById("form-error");
const summaryEl = document.getElementById("summary");
const totalEl = document.getElementById("total");
const historyEl = document.getElementById("history");
const emptyEl = document.getElementById("empty");

// Prevents HTML injection when showing user-typed text
function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

// Today's date in local time, format YYYY-MM-DD
function today() {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 10);
}

// One helper for all API calls, with readable error messages
async function api(path, options = {}) {
  const res = await fetch(API + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let message = `Error ${res.status}`;
    try {
      const body = await res.json();
      message = typeof body.detail === "string"
        ? body.detail
        : body.detail.map((d) => d.msg).join(", ");
    } catch { /* keep default message */ }
    throw new Error(message);
  }
  return res.status === 204 ? null : res.json();
}

async function loadCategories() {
  const categories = await api("/categories");
  categorySelect.innerHTML = categories
    .map((c) => `<option value="${c.id}">${escapeHtml(c.name)}</option>`)
    .join("");
}

async function loadSummary() {
  const s = await api("/summary");
  totalEl.textContent = `Spent ${money.format(s.total_spent)} of ${money.format(s.total_budget)}`;
  summaryEl.innerHTML = s.categories.map((c) => {
    const pct = c.budget_limit > 0 ? Math.min(100, (c.spent / c.budget_limit) * 100) : 0;
    const status = c.over_budget
      ? `Over by ${money.format(-c.remaining)}`
      : `${money.format(c.remaining)} left`;
    return `
      <div class="budget ${c.over_budget ? "over" : ""}">
        <div class="budget-row">
          <strong>${escapeHtml(c.name)}</strong>
          <span>${money.format(c.spent)} / ${money.format(c.budget_limit)}</span>
        </div>
        <div class="bar"><div class="fill" style="width:${pct}%"></div></div>
        <small>${status}</small>
      </div>`;
  }).join("");
}

async function loadHistory() {
  const expenses = await api("/expenses");
  emptyEl.hidden = expenses.length > 0;
  historyEl.innerHTML = expenses.map((e) => `
    <tr>
      <td>${e.spent_on}</td>
      <td>${escapeHtml(e.description)}</td>
      <td>${escapeHtml(e.category_name)}</td>
      <td class="num">${money.format(e.amount)}</td>
      <td><button class="delete" data-id="${e.id}">Delete</button></td>
    </tr>`).join("");
}

async function refresh() {
  await Promise.all([loadSummary(), loadHistory()]);
}

// Add expense
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorEl.textContent = "";
  try {
    await api("/expenses", {
      method: "POST",
      body: JSON.stringify({
        amount: parseFloat(amountInput.value),
        description: descInput.value.trim(),
        spent_on: dateInput.value,
        category_id: Number(categorySelect.value),
      }),
    });
    form.reset();
    dateInput.value = today();
    await refresh();
  } catch (err) {
    errorEl.textContent = err.message;
  }
});

// Delete expense (one listener for the whole table)
historyEl.addEventListener("click", async (event) => {
  const button = event.target.closest("button.delete");
  if (!button) return;
  if (!confirm("Delete this expense?")) return;
  try {
    await api(`/expenses/${button.dataset.id}`, { method: "DELETE" });
    await refresh();
  } catch (err) {
    alert(err.message);
  }
});

// Start
dateInput.value = today();
loadCategories()
  .then(refresh)
  .catch((err) => { errorEl.textContent = "Cannot reach the server: " + err.message; });