// import.js - CSV import with preview, and the keyword rules panel.
// Owner: Member C (Frontend)
//
// Import flow (two steps, so nothing is saved until the user agrees):
//   1. user picks a file -> api.previewImport(file)  (POST /api/import/preview)
//      the server reads the CSV and suggests a category for every row
//   2. user checks / corrects the rows -> api.commitImport(rows)  (POST /api/import/commit)
//      the server saves them and learns keywords from the corrections
//
// Uses helpers from app.js: $, el, state, euro, toast, refresh, categoryById.

const importState = {
  rows: [], // rows from the preview, each with .include and .category_id the user may change
};

// ---------------- step 1: preview ----------------

$("import-file").addEventListener("change", (event) => {
  const file = event.target.files[0];
  $("dropzone-text").innerHTML = "";
  $("dropzone-text").append(file ? el("strong", { textContent: file.name }) : "Choose a CSV file");
});

// Drag and drop onto the box
const dropzone = $("dropzone");
dropzone.addEventListener("dragover", (e) => { e.preventDefault(); dropzone.classList.add("over"); });
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("over"));
dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("over");
  if (e.dataTransfer.files.length) {
    $("import-file").files = e.dataTransfer.files;
    $("import-file").dispatchEvent(new Event("change"));
  }
});

$("import-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = $("import-file").files[0];
  if (!file) return toast("Choose a CSV file first", true);
  $("preview-btn").disabled = true;
  try {
    const result = await api.previewImport(file);
    importState.rows = result.rows.map((r) => ({
      ...r,
      suggested_category_id: r.category_id, // remember the suggestion, to detect corrections
      include: !r.duplicate,                // duplicates start unticked
    }));
    renderPreview(result);
  } catch (err) {
    toast(err.message, true);
  } finally {
    $("preview-btn").disabled = false;
  }
});

function whyText(row) {
  if (row.match_source === "file") return "category from file";
  if (row.match_source === "learned") return `your rule "${row.matched_keyword}"`;
  if (row.match_source === "built-in") return `keyword "${row.matched_keyword}"`;
  return "needs review";
}

function renderPreview(result) {
  const rows = importState.rows;
  const review = rows.filter((r) => !r.match_source).length;
  const duplicates = rows.filter((r) => r.duplicate).length;
  $("import-stats").textContent =
    `${rows.length} expenses read · ${review} need review · ${duplicates} already imported · ${result.skipped_income} income rows skipped`;

  $("import-errors").classList.toggle("hidden", result.errors.length === 0);
  $("import-errors").replaceChildren(
    ...result.errors.map((e) => el("li", { textContent: `Line ${e.line}: ${e.message} (row skipped)` })),
  );

  $("preview-rows").replaceChildren(...rows.map((row) => {
    const include = el("input", { type: "checkbox", checked: row.include });
    include.addEventListener("change", () => { row.include = include.checked; updateCommitButton(); });

    const select = el("select", {}, ...state.categories.map((c) =>
      el("option", { value: c.category_id, textContent: c.name, selected: c.category_id === row.category_id })));
    const why = el("span", { className: `why ${row.match_source ? "" : "review"}`, textContent: whyText(row) });
    select.addEventListener("change", () => {
      row.category_id = Number(select.value);
      const changed = row.category_id !== row.suggested_category_id;
      why.textContent = changed ? "changed by you" : whyText(row);
      why.className = `why ${changed ? "changed" : row.match_source ? "" : "review"}`;
    });

    const tr = el("tr", { className: row.duplicate ? "duplicate" : "" },
      el("td", {}, include),
      el("td", { textContent: row.expense_date }),
      el("td", {}, row.description, row.duplicate ? el("span", { className: "badge warn", textContent: "duplicate" }) : ""),
      el("td", { className: "num", textContent: euro.format(row.amount) }),
      el("td", {}, select),
      el("td", {}, why),
    );
    return tr;
  }));

  $("select-all").checked = rows.every((r) => r.include);
  updateCommitButton();
  $("import-preview").classList.remove("hidden");
  $("import-preview").scrollIntoView({ behavior: "smooth", block: "start" });
}

function updateCommitButton() {
  const count = importState.rows.filter((r) => r.include).length;
  $("commit-btn").textContent = `Import ${count} expense${count === 1 ? "" : "s"}`;
  $("commit-btn").disabled = count === 0;
}

$("select-all").addEventListener("change", (event) => {
  importState.rows.forEach((r) => { r.include = event.target.checked; });
  document.querySelectorAll("#preview-rows input[type=checkbox]").forEach((cb) => { cb.checked = event.target.checked; });
  updateCommitButton();
});

function closePreview() {
  importState.rows = [];
  $("import-preview").classList.add("hidden");
  $("import-form").reset();
  $("dropzone-text").innerHTML = "<strong>Choose a CSV file</strong> or drag it here";
}

$("cancel-import").addEventListener("click", closePreview);

// ---------------- step 2: commit ----------------

$("commit-btn").addEventListener("click", async () => {
  const chosen = importState.rows.filter((r) => r.include);
  if (!chosen.length) return;
  $("commit-btn").disabled = true; // prevents importing twice by double-clicking
  try {
    const result = await api.commitImport(
      chosen.map(({ expense_date, description, amount, category_id, suggested_category_id }) =>
        ({ expense_date, description, amount, category_id, suggested_category_id })),
      $("learn").checked,
    );
    const learned = result.rules_learned.map((r) => `"${r.keyword}" → ${r.category_name}`).join(", ");
    toast(`Imported ${result.imported} expenses${learned ? `. Learned: ${learned}` : ""}`);

    // Show the month that holds the most recent imported expense.
    const latest = chosen.map((r) => r.expense_date).sort().at(-1);
    $("month").value = latest.slice(0, 7);
    closePreview();
    await Promise.all([refresh(), loadRules()]);
  } catch (err) {
    toast(err.message, true);
    $("commit-btn").disabled = false;
  }
});

// ---------------- keyword rules panel ----------------

async function loadRules() {
  try {
    const rules = await api.rules();
    const mine = rules.filter((r) => !r.built_in);
    const builtIn = rules.filter((r) => r.built_in);

    $("rule-empty").classList.toggle("hidden", mine.length > 0);
    $("rule-list").replaceChildren(...mine.map((r) => {
      const cat = categoryById(r.category_id);
      const remove = el("button", { className: "icon-btn danger", textContent: "Remove", onclick: () => removeRule(r) });
      return el("li", {},
        el("span", {}, el("code", { textContent: r.keyword }), " → ",
          el("span", { className: "chip" }, el("span", { className: "dot", style: `background:${cat.color}` }), r.category_name)),
        remove);
    }));

    // Built-in rules grouped by category: "Food: rewe, edeka, aldi ..."
    $("builtin-summary").textContent = `Built-in rules (${builtIn.length})`;
    const groups = {};
    builtIn.forEach((r) => { (groups[r.category_name] ||= []).push(r.keyword); });
    $("builtin-list").replaceChildren(...Object.entries(groups).map(([name, words]) =>
      el("p", {}, el("strong", { textContent: `${name}: ` }), words.join(", "))));
  } catch (err) {
    toast(err.message, true);
  }
}

$("rule-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const f = event.target;
  try {
    const rule = await api.addRule({ keyword: f.keyword.value.trim(), category_id: Number(f.category_id.value) });
    toast(`Rule added: "${rule.keyword}" → ${rule.category_name}`);
    f.keyword.value = "";
    await loadRules();
  } catch (err) {
    toast(err.message, true);
  }
});

async function removeRule(rule) {
  try {
    await api.deleteRule(rule.rule_id);
    toast(`Rule "${rule.keyword}" removed`);
    await loadRules();
  } catch (err) {
    toast(err.message, true);
  }
}
