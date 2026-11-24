// charts.js - draws the three charts from the ER diagram using Chart.js.
// Owner: Member C (Frontend)
//
// The charts never calculate anything. They only draw the numbers that
// GET /api/summary returns (calculated on the server in app/summary.py).
//
//   drawCategoryChart  <- summary.by_category  (donut)
//   drawBudgetChart    <- summary.budgets      (horizontal bars)
//   drawDateChart      <- summary.by_date      (bars per day)

const euro = new Intl.NumberFormat("en-IE", { style: "currency", currency: "EUR" });
const charts = {}; // keep each chart so we can update it instead of redrawing

Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
Chart.defaults.color = "#64748b";

function upsertChart(id, config) {
  if (charts[id]) {
    charts[id].data = config.data;
    charts[id].options = config.options;
    charts[id].update();
  } else {
    charts[id] = new Chart(document.getElementById(id), config);
  }
}

function drawCategoryChart(byCategory) {
  const empty = byCategory.length === 0;
  document.getElementById("category-empty").classList.toggle("hidden", !empty);
  upsertChart("category-chart", {
    type: "doughnut",
    data: {
      labels: byCategory.map((c) => c.name),
      datasets: [{
        data: byCategory.map((c) => c.total),
        backgroundColor: byCategory.map((c) => c.color),
        borderWidth: 2,
        borderColor: "#fff",
      }],
    },
    options: {
      maintainAspectRatio: false,
      cutout: "62%",
      plugins: {
        legend: { position: "right", labels: { boxWidth: 12, padding: 12 } },
        tooltip: { callbacks: { label: (ctx) => ` ${ctx.label}: ${euro.format(ctx.parsed)}` } },
      },
    },
  });
}

// Budgets are shown as "% of limit used", not in euros: an overall limit of
// €1,100 and a €50 entertainment limit on one euro axis would make the
// small budgets unreadable. 100% (the dashed line) = the limit.
const limitLine = {
  id: "limitLine",
  afterDatasetsDraw(chart) {
    if (chart.canvas.id !== "budget-chart") return;
    const { ctx, chartArea, scales } = chart;
    const x = scales.x.getPixelForValue(100);
    ctx.save();
    ctx.strokeStyle = "#0f172a";
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(x, chartArea.top);
    ctx.lineTo(x, chartArea.bottom);
    ctx.stroke();
    ctx.restore();
  },
};

function drawBudgetChart(budgets) {
  const empty = budgets.length === 0;
  document.getElementById("budget-empty").classList.toggle("hidden", !empty);
  const box = document.getElementById("budget-chart").parentElement;
  box.classList.toggle("hidden", empty);
  box.style.height = `${Math.max(140, 44 * budgets.length + 50)}px`; // grow with the number of budgets
  const maxPercent = Math.max(100, ...budgets.map((b) => b.percent_used));

  upsertChart("budget-chart", {
    type: "bar",
    data: {
      labels: budgets.map((b) => b.name),
      datasets: [{
        label: "% of limit used",
        data: budgets.map((b) => b.percent_used),
        backgroundColor: budgets.map((b) =>
          b.over_budget ? "#dc2626" : b.percent_used >= 80 ? "#d97706" : "#16a34a"),
        borderRadius: 4,
        barThickness: 18,
      }],
    },
    options: {
      indexAxis: "y", // makes the bars horizontal
      maintainAspectRatio: false,
      scales: {
        x: {
          beginAtZero: true,
          suggestedMax: Math.ceil(maxPercent / 25) * 25,
          ticks: { callback: (v) => `${v}%` },
          grid: { color: "#f1f5f9" },
        },
        y: { grid: { display: false } },
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const b = budgets[ctx.dataIndex];
              return ` ${euro.format(b.spent)} of ${euro.format(b.limit_amount)} (${b.percent_used}%)`;
            },
          },
        },
      },
    },
    plugins: [limitLine],
  });
}

function drawDateChart(byDate) {
  upsertChart("date-chart", {
    type: "bar",
    data: {
      labels: byDate.map((d) => Number(d.date.slice(8))), // "2026-11-05" -> 5
      datasets: [{
        label: "Spent",
        data: byDate.map((d) => d.total),
        backgroundColor: "#2563eb",
        borderRadius: 3,
      }],
    },
    options: {
      maintainAspectRatio: false,
      scales: {
        x: { title: { display: true, text: "Day of month" }, grid: { display: false } },
        y: { beginAtZero: true, ticks: { callback: (v) => euro.format(v) }, grid: { color: "#f1f5f9" } },
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            title: (items) => byDate[items[0].dataIndex].date,
            label: (ctx) => ` ${euro.format(ctx.parsed.y)}`,
          },
        },
      },
    },
  });
}
