// api.js - every call from the browser to the FastAPI backend goes through here.
// Owner: Member C (Frontend)
//
// How it works
// - fetch() sends an HTTP request and returns a Promise; `await` waits for it.
// - After login the server gives us a token. We keep it in localStorage
//   (the browser's small key-value store) and send it in every request as
//   "Authorization: Bearer <token>". That is how the server knows who we are.

const TOKEN_KEY = "expense_logger_token";

const api = {
  get token() { return localStorage.getItem(TOKEN_KEY); },
  set token(value) {
    if (value) localStorage.setItem(TOKEN_KEY, value);
    else localStorage.removeItem(TOKEN_KEY);
  },

  // One helper for all requests: adds headers, turns JSON into objects,
  // and turns HTTP errors into readable messages.
  async request(method, path, body) {
    const headers = {};
    const isFile = body instanceof FormData; // file uploads are sent as form-data, not JSON
    if (body !== undefined && !isFile) headers["Content-Type"] = "application/json";
    if (this.token) headers["Authorization"] = `Bearer ${this.token}`;

    const res = await fetch(path, {
      method,
      headers,
      body: body === undefined ? undefined : isFile ? body : JSON.stringify(body),
    });

    if (res.status === 401 && !path.startsWith("/api/auth/")) {
      this.token = null;
      window.dispatchEvent(new Event("logged-out"));
    }
    if (res.status === 204) return null; // "No Content", e.g. after DELETE

    const data = await res.json().catch(() => null);
    if (!res.ok) throw new Error(errorMessage(data, res.status));
    return data;
  },

  // ----- auth -----
  register: (user) => api.request("POST", "/api/auth/register", user),
  login: (username, password) => api.request("POST", "/api/auth/login", { username, password }),
  me: () => api.request("GET", "/api/auth/me"),

  // ----- data -----
  categories: () => api.request("GET", "/api/categories"),
  expenses: (month, categoryId) => {
    const params = new URLSearchParams({ month });
    if (categoryId) params.set("category_id", categoryId);
    return api.request("GET", `/api/expenses?${params}`);
  },
  addExpense: (expense) => api.request("POST", "/api/expenses", expense),
  updateExpense: (id, expense) => api.request("PUT", `/api/expenses/${id}`, expense),
  deleteExpense: (id) => api.request("DELETE", `/api/expenses/${id}`),
  setBudget: (budget) => api.request("PUT", "/api/budgets", budget),
  deleteBudget: (id) => api.request("DELETE", `/api/budgets/${id}`),
  summary: (month) => api.request("GET", `/api/summary?month=${month}`),

  // ----- auto-categorization and import -----
  rules: () => api.request("GET", "/api/rules"),
  addRule: (rule) => api.request("POST", "/api/rules", rule),
  deleteRule: (id) => api.request("DELETE", `/api/rules/${id}`),
  categorize: (description) => api.request("POST", "/api/categorize", { description }),
  previewImport: (file) => {
    const form = new FormData();
    form.append("file", file);
    return api.request("POST", "/api/import/preview", form);
  },
  commitImport: (rows, learn) => api.request("POST", "/api/import/commit", { rows, learn }),
};

// FastAPI errors look like {"detail": "text"} or, for validation (422),
// {"detail": [{"loc": [...,"amount"], "msg": "..."}]}. Make both readable.
function errorMessage(data, status) {
  if (!data || !data.detail) return `Request failed (${status})`;
  if (typeof data.detail === "string") return data.detail;
  return data.detail
    .map((e) => `${e.loc[e.loc.length - 1]}: ${e.msg}`)
    .join("; ");
}
