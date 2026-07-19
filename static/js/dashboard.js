const fmtINR = (n) => "₹" + Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 });
const fmtPct = (n) => (n > 0 ? "+" : "") + n + "%";

document.getElementById("date-line").textContent = new Date().toLocaleDateString("en-IN", {
  weekday: "long", year: "numeric", month: "long", day: "numeric",
});

async function fetchJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url} failed: ${res.status}`);
  return res.json();
}

function statCard(label, value, deltaText, deltaClass, alertClass) {
  return `
    <div class="card ${alertClass || ""}">
      <div class="card-label">${label}</div>
      <div class="stat-value">${value}</div>
      ${deltaText ? `<div class="stat-delta ${deltaClass}">${deltaText}</div>` : ""}
    </div>`;
}

function renderSnapshot(s) {
  const grid = document.getElementById("snapshot-grid");
  grid.innerHTML = [
    statCard("Revenue Today", fmtINR(s.revenue), `${fmtPct(s.revenue_change_pct)} vs yesterday`, s.revenue_change_pct >= 0 ? "up" : "down"),
    statCard("Profit Today", fmtINR(s.profit), `${fmtPct(s.profit_change_pct)} vs yesterday`, s.profit_change_pct >= 0 ? "up" : "down"),
    statCard("Orders Today", s.orders, null, ""),
    statCard("Expiring Items", s.expiring_items_count, "within 90 days", "warn", s.expiring_items_count > 0 ? "warn-card" : ""),
    statCard("Low Stock Items", s.low_stock_count, "at/near reorder level", "warn"),
    statCard("Dead Stock Value", fmtINR(s.dead_stock_value), "no recent sales", "down"),
    statCard("Stock-Out Items", s.stock_out_count, "currently unavailable", "down", s.stock_out_count > 0 ? "alert" : ""),
    statCard("Opportunities", fmtINR(s.opportunity_value), "recoverable this month", "up"),
  ].join("");
}

function renderHealthScore(h) {
  document.getElementById("health-score-num").textContent = h.score;
  const circumference = 2 * Math.PI * 54;
  const filled = (h.score / 100) * circumference;
  const arc = document.getElementById("gauge-arc");
  arc.setAttribute("stroke-dasharray", `${filled} ${circumference}`);

  let color = "#3DDC97";
  if (h.score < 60) color = "#FF6B6B";
  else if (h.score < 80) color = "#F5B942";
  arc.setAttribute("stroke", color);
  document.getElementById("health-score-num").style.color = color;

  const compWrap = document.getElementById("health-components");
  const labels = {
    profitability: "Profitability",
    inventory: "Inventory",
    sales_trend: "Sales Trend",
    expiry_risk: "Expiry Risk",
    stock_availability: "Stock Availability",
  };
  let html = `<div class="card-label">Business Health Score — ${h.label}</div>`;
  for (const [key, val] of Object.entries(h.components)) {
    html += `<div class="health-component-row"><span>${labels[key] || key}</span><b>${val}</b></div>`;
  }
  compWrap.innerHTML = html;
}

function renderList(elId, items, renderFn, emptyMsg) {
  const el = document.getElementById(elId);
  if (!items || items.length === 0) {
    el.innerHTML = `<div class="empty-state">${emptyMsg}</div>`;
    return;
  }
  el.innerHTML = items.map(renderFn).join("");
}

function renderExpiry(items) {
  renderList("expiry-list", items, (i) => `
    <div class="list-row">
      <div class="list-row-main">
        <span class="list-row-title">${i.medicine_name}</span>
        <span class="list-row-sub">${i.quantity} units · batch ${i.batch_number || "—"}</span>
      </div>
      <span class="pill ${i.days_to_expiry <= 15 ? "red" : "gold"}">${i.days_to_expiry}d left</span>
    </div>`, "Nothing expiring soon. 🎉");
}

function renderLowStock(items) {
  renderList("lowstock-list", items, (i) => `
    <div class="list-row">
      <div class="list-row-main">
        <span class="list-row-title">${i.medicine_name}</span>
        <span class="list-row-sub">Reorder level: ${i.reorder_level}</span>
      </div>
      <span class="pill red">${i.current_stock} left</span>
    </div>`, "All stock levels healthy.");
}

function renderDeadStock(items) {
  renderList("deadstock-list", items, (i) => `
    <div class="list-row">
      <div class="list-row-main">
        <span class="list-row-title">${i.medicine_name}</span>
        <span class="list-row-sub">${i.current_stock} units on hand</span>
      </div>
      <span class="pill gold">${fmtINR(i.value)}</span>
    </div>`, "No dead stock detected.");
}

function renderProfitLeak(data) {
  const el = document.getElementById("profit-leak-content");
  if (!data.reasons || data.reasons.length === 0) {
    el.innerHTML = `<div class="empty-state">No significant profit leaks detected right now.</div>`;
    return;
  }
  el.innerHTML = `
    <div style="margin-bottom:12px;">
      <span class="card-label">Total estimated loss</span>
      <div class="stat-value" style="color: var(--danger-red); font-size:22px;">${fmtINR(data.total_estimated_loss)}</div>
    </div>
    ${data.reasons.map(r => `
      <div class="list-row">
        <div class="list-row-main">
          <span class="list-row-title">${r.description}</span>
        </div>
        <span class="pill red">${fmtINR(r.estimated_loss)}</span>
      </div>`).join("")}
  `;
}

function renderPurchasePlan(items) {
  renderList("purchase-plan-content", items, (i) => `
    <div class="list-row">
      <div class="list-row-main">
        <span class="list-row-title">${i.medicine_name}</span>
        <span class="list-row-sub">${i.days_of_stock_remaining ?? "?"} days of stock left</span>
      </div>
      <span class="pill gold">Order ~${i.recommended_order_qty}</span>
    </div>`, "No urgent purchases needed this week.");
}

let salesChart;
function getThemeColor(varName, fallback) {
  const value = getComputedStyle(document.documentElement).getPropertyValue(varName).trim();
  return value || fallback;
}

function renderSalesChart(trend) {
  try {
    const ctx = document.getElementById("salesChart");
    const labels = trend.labels.map((d) => {
      const dt = new Date(d + "T00:00:00");
      return dt.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
    });

    const inkColor = getThemeColor("--ink-60", "#6B759E");
    const lineColor = getThemeColor("--navy-line", "#24305E");
    const goldColor = getThemeColor("--gold", "#F5B942");
    const okGreenColor = getThemeColor("--ok-green", "#3DDC97");

    if (salesChart) salesChart.destroy();

    salesChart = new Chart(ctx, {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: "Revenue",
            data: trend.revenue,
            borderColor: goldColor,
            backgroundColor: goldColor + "15",
            tension: 0.35,
            fill: true,
            pointRadius: 0,
          },
          {
            label: "Profit",
            data: trend.profit,
            borderColor: okGreenColor,
            backgroundColor: okGreenColor + "0f",
            tension: 0.35,
            fill: true,
            pointRadius: 0,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { labels: { color: inkColor, font: { size: 11 } } } },
        scales: {
          x: { ticks: { color: inkColor, font: { size: 10 } }, grid: { color: lineColor } },
          y: { ticks: { color: inkColor, font: { size: 10 } }, grid: { color: lineColor } },
        },
      },
    });
  } catch (e) {
    console.error("Chart render failed", e);
  }
}

let lastSalesTrend = null;
document.addEventListener("aloksaar-theme-changed", () => {
  if (lastSalesTrend) renderSalesChart(lastSalesTrend);
});

async function init() {
  try {
    const data = await fetchJSON("/api/dashboard/all");
    renderSnapshot(data.snapshot);
    renderHealthScore(data.health_score);
    renderExpiry(data.expiry_at_risk);
    renderLowStock(data.low_stock);
    renderDeadStock(data.dead_stock);
    renderProfitLeak(data.profit_leak);
    renderPurchasePlan(data.purchase_plan);
    lastSalesTrend = data.sales_trend;
    renderSalesChart(data.sales_trend);
  } catch (e) {
    console.error("Dashboard load failed", e);
    document.getElementById("snapshot-grid").innerHTML =
      `<div class="card alert"><div class="card-label">Error</div><div class="empty-state">Couldn't load dashboard data. Check the server is running and the database is reachable.</div></div>`;
  }
}

init();
