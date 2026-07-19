const messagesEl = document.getElementById("insights-messages");
const inputEl = document.getElementById("insights-input");
const sendBtn = document.getElementById("insights-send-btn");
const canvasEl = document.getElementById("insights-canvas");
const refreshBtn = document.getElementById("refresh-canvas-btn");
const rangeEl = document.getElementById("filter-range");
const customRangeEl = document.getElementById("custom-range");
const startDateEl = document.getElementById("filter-start");
const endDateEl = document.getElementById("filter-end");
const addSummaryBtn = document.getElementById("add-summary-btn");
const addChartBtn = document.getElementById("add-chart-btn");
const downloadReportBtn = document.getElementById("download-report-btn");
const chatFab = document.getElementById("insights-chat-fab");
const chatPanel = document.getElementById("insights-chat-panel");
const chatCloseBtn = document.getElementById("insights-chat-close");

let lastVizRequest = null;
let canvasCharts = []; // track Chart.js instances so we can destroy on re-render
let currentBlocks = [];
const CANVAS_STORAGE_KEY = "aloksaar_insights_blocks";

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function renderMarkdown(text) {
  const rawHtml = marked.parse(text, { breaks: true });
  return DOMPurify.sanitize(rawHtml);
}

function scrollChatToBottom() {
  requestAnimationFrame(() => {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  });
}

function setChatDrawer(open) {
  chatPanel.classList.toggle("open", open);
  chatFab.setAttribute("aria-expanded", String(open));
  if (open) requestAnimationFrame(() => inputEl.focus());
}

function addMessage(role, content, isError = false) {
  const msg = document.createElement("div");
  msg.className = `msg ${role}`;
  msg.dataset.content = content;
  const avatar = role === "assistant" ? "☀" : "🧑";
  const bodyHtml = (role === "assistant" && !isError) ? renderMarkdown(content) : escapeHtml(content);
  const actionHtml = role === "user"
    ? `<div class="msg-actions"><button type="button" class="msg-action msg-rewrite" aria-label="Rewrite message" title="Rewrite">✎</button></div>`
    : `<div class="msg-actions"><button type="button" class="msg-action msg-retry" aria-label="Retry request" title="Retry">↻</button></div>`;
  msg.innerHTML = `
    <div class="msg-avatar">${avatar}</div>
    <div class="msg-bubble ${role === "assistant" ? "md-content" : ""} ${isError ? "msg-error" : ""}">${bodyHtml}</div>
    ${actionHtml}
  `;
  messagesEl.appendChild(msg);
  const rewriteBtn = msg.querySelector(".msg-rewrite");
  if (rewriteBtn) {
    rewriteBtn.addEventListener("click", () => {
      inputEl.value = msg.dataset.content || "";
      inputEl.dispatchEvent(new Event("input"));
      setChatDrawer(true);
    });
  }
  const retryBtn = msg.querySelector(".msg-retry");
  if (retryBtn) {
    retryBtn.addEventListener("click", () => {
      const userMessages = messagesEl.querySelectorAll(".msg.user");
      const previousRequest = userMessages[userMessages.length - 1]?.dataset.content;
      if (previousRequest) sendMessage(previousRequest);
    });
  }
  scrollChatToBottom();
  return msg;
}

function addTypingIndicator() {
  const msg = document.createElement("div");
  msg.className = "msg assistant";
  msg.id = "insights-typing";
  msg.innerHTML = `
    <div class="msg-avatar">☀</div>
    <div class="msg-bubble"><div class="typing-indicator"><span></span><span></span><span></span></div></div>
  `;
  messagesEl.appendChild(msg);
  scrollChatToBottom();
}

function removeTypingIndicator() {
  const el = document.getElementById("insights-typing");
  if (el) el.remove();
}

async function loadHistory() {
  try {
    const res = await fetch("/api/insights/history");
    const history = await res.json();
    if (history.length === 0) {
      addMessage("assistant", "Ask me for a chart, table, or comparison — e.g. \"show revenue trend\" or \"table of low stock items\" — and I'll build it on the canvas.");
    } else {
      history.forEach((m) => addMessage(m.role, m.content));
    }
  } catch (e) {
    addMessage("assistant", "Ask me for a chart, table, or comparison.");
  }
}

async function sendMessage(text) {
  if (!text.trim()) return;
  addMessage("user", text);
  inputEl.value = "";
  inputEl.style.height = "auto";
  sendBtn.disabled = true;
  addTypingIndicator();

  try {
    const res = await fetch("/api/insights/message", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text }),
    });
    const data = await res.json();
    removeTypingIndicator();

    if (!res.ok) {
      addMessage("assistant", data.error || "Something went wrong.", true);
      return;
    }
    addMessage("assistant", data.assistant_message.content);

    // Every message on the Insights page attempts to update the canvas —
    // this is the dedicated visualization workspace, so unlike the main
    // chat page (which only offers a link), here we generate directly.
    lastVizRequest = text;
    await generateCanvas(text);
  } catch (e) {
    removeTypingIndicator();
    addMessage("assistant", "Couldn't reach the AlokSaar backend.", true);
  } finally {
    sendBtn.disabled = false;
  }
}

function destroyCanvasCharts() {
  canvasCharts.forEach((c) => c.destroy());
  canvasCharts = [];
}

function blockToolbar(block, index) {
  const toolbar = document.createElement("div");
  toolbar.className = "canvas-block-toolbar";
  const edit = document.createElement("button");
  edit.type = "button";
  edit.textContent = "Edit title";
  edit.addEventListener("click", () => {
    const title = window.prompt("Block title", block.title || "");
    if (title !== null && title.trim()) {
      currentBlocks[index].title = title.trim();
      renderCanvas(currentBlocks);
    }
  });
  const editData = document.createElement("button");
  editData.type = "button";
  editData.textContent = "Edit data";
  editData.addEventListener("click", () => {
    const raw = window.prompt("Edit this block's JSON data", JSON.stringify(block, null, 2));
    if (raw === null) return;
    try {
      const updated = JSON.parse(raw);
      if (!updated.type) throw new Error("A block type is required.");
      currentBlocks[index] = updated;
      renderCanvas(currentBlocks);
    } catch (error) {
      window.alert(`Could not save this block: ${error.message}`);
    }
  });
  const remove = document.createElement("button");
  remove.type = "button";
  remove.className = "danger";
  remove.textContent = "Remove";
  remove.addEventListener("click", () => {
    currentBlocks.splice(index, 1);
    renderCanvas(currentBlocks);
  });
  toolbar.append(edit, editData, remove);
  return toolbar;
}

function renderChartBlock(block) {
  const wrap = document.createElement("div");
  wrap.className = "canvas-block";
  wrap.innerHTML = `
    <div class="canvas-block-title">${escapeHtml(block.title || "Chart")}</div>
    <div class="canvas-chart-wrap"><canvas></canvas></div>
  `;
  const ctx = wrap.querySelector("canvas");
  const palette = ["#F5B942", "#3DDC97", "#FF6B6B", "#8A8FE0"];
  const chart = new Chart(ctx, {
    type: block.chart_type === "bar" ? "bar" : "line",
    data: {
      labels: block.labels || [],
      datasets: (block.series || []).map((s, i) => ({
        label: s.name,
        data: s.data,
        borderColor: palette[i % palette.length],
        backgroundColor: block.chart_type === "bar" ? palette[i % palette.length] : `${palette[i % palette.length]}22`,
        tension: 0.35,
        fill: block.chart_type !== "bar",
        pointRadius: 0,
      })),
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { labels: { color: "#C3C9E8", font: { size: 11 } } } },
      scales: {
        x: { ticks: { color: "#6B759E", font: { size: 10 } }, grid: { color: "#24305E" } },
        y: { ticks: { color: "#6B759E", font: { size: 10 } }, grid: { color: "#24305E" } },
      },
    },
  });
  canvasCharts.push(chart);
  return wrap;
}

function renderTableBlock(block) {
  const wrap = document.createElement("div");
  wrap.className = "canvas-block";
  const cols = block.columns || [];
  const rows = block.rows || [];
  wrap.innerHTML = `
    <div class="canvas-block-title">${escapeHtml(block.title || "Table")}</div>
    <table class="canvas-table">
      <thead><tr>${cols.map(c => `<th>${escapeHtml(String(c))}</th>`).join("")}</tr></thead>
      <tbody>${rows.map(row => `<tr>${row.map(cell => `<td>${escapeHtml(String(cell))}</td>`).join("")}</tr>`).join("")}</tbody>
    </table>
  `;
  return wrap;
}

function renderCardGridBlock(block) {
  const wrap = document.createElement("div");
  wrap.className = "canvas-block";
  const cards = block.cards || [];
  wrap.innerHTML = `
    <div class="canvas-block-title">${escapeHtml(block.title || "Summary")}</div>
    <div class="canvas-card-grid">
      ${cards.map(c => `
        <div class="canvas-card">
          <div class="canvas-card-label">${escapeHtml(c.label || "")}</div>
          <div class="canvas-card-value ${c.trend === "up" ? "trend-up" : c.trend === "down" ? "trend-down" : ""}">${escapeHtml(String(c.value ?? ""))}</div>
        </div>
      `).join("")}
    </div>
  `;
  return wrap;
}

function renderCanvas(blocks) {
  destroyCanvasCharts();
  canvasEl.innerHTML = "";
  currentBlocks = Array.isArray(blocks) ? blocks : [];
  localStorage.setItem(CANVAS_STORAGE_KEY, JSON.stringify(currentBlocks));

  if (currentBlocks.length === 0) {
    canvasEl.innerHTML = `<div class="empty-state" style="padding: 60px 20px;">Nothing to show for that request yet — try being more specific, e.g. "bar chart of revenue by day" or "table of expiring medicines".</div>`;
    return;
  }

  currentBlocks.forEach((block, index) => {
    let el;
    if (block.type === "chart") el = renderChartBlock(block);
    else if (block.type === "table") el = renderTableBlock(block);
    else if (block.type === "card_grid") el = renderCardGridBlock(block);
    if (el) {
      el.prepend(blockToolbar(block, index));
      canvasEl.appendChild(el);
    }
  });
}

async function generateCanvas(message) {
  canvasEl.innerHTML = `<div class="empty-state" style="padding: 60px 20px;">Building your canvas…</div>`;
  try {
    const params = new URLSearchParams({ days: rangeEl.value });
    if (customRangeEl.value.trim()) params.set("range", customRangeEl.value.trim());
    if (startDateEl.value) params.set("start", startDateEl.value);
    if (endDateEl.value) params.set("end", endDateEl.value);
    const res = await fetch(`/api/insights/visualize?${params.toString()}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    const data = await res.json();
    if (!res.ok) {
      canvasEl.innerHTML = `<div class="empty-state" style="padding: 60px 20px; color: var(--danger-red);">${escapeHtml(data.error || "Could not build the canvas.")}</div>`;
      return;
    }
    renderCanvas(data.blocks);
    if (data.warning) addMessage("assistant", data.warning);
  } catch (e) {
    canvasEl.innerHTML = `<div class="empty-state" style="padding: 60px 20px; color: var(--danger-red);">Couldn't reach the backend.</div>`;
  }
}

sendBtn.addEventListener("click", () => sendMessage(inputEl.value));
chatFab.addEventListener("click", () => setChatDrawer(true));
chatCloseBtn.addEventListener("click", () => setChatDrawer(false));
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") setChatDrawer(false);
});
inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage(inputEl.value);
  }
});
inputEl.addEventListener("input", () => {
  inputEl.style.height = "auto";
  inputEl.style.height = Math.min(inputEl.scrollHeight, 120) + "px";
});

refreshBtn.addEventListener("click", () => {
  if (lastVizRequest) generateCanvas(lastVizRequest);
});

rangeEl.addEventListener("change", () => {
  customRangeEl.value = "";
  if (lastVizRequest) generateCanvas(lastVizRequest);
});

customRangeEl.addEventListener("change", () => {
  startDateEl.value = "";
  endDateEl.value = "";
  if (lastVizRequest) generateCanvas(lastVizRequest);
});

customRangeEl.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    customRangeEl.blur();
  }
});

[startDateEl, endDateEl].forEach((input) => input.addEventListener("change", () => {
  if (startDateEl.value && endDateEl.value) {
    customRangeEl.value = "";
    if (lastVizRequest) generateCanvas(lastVizRequest);
  }
}));

addSummaryBtn.addEventListener("click", () => {
  currentBlocks.push({
    type: "card_grid",
    title: "Custom Summary",
    cards: [
      { label: "New metric", value: "0", trend: "neutral" },
      { label: "Add a value", value: "—", trend: "neutral" },
    ],
  });
  renderCanvas(currentBlocks);
});

addChartBtn.addEventListener("click", () => {
  currentBlocks.push({
    type: "chart",
    chart_type: "line",
    title: "Custom Chart",
    labels: ["Point 1", "Point 2", "Point 3"],
    series: [{ name: "Metric", data: [0, 0, 0] }],
  });
  renderCanvas(currentBlocks);
});

downloadReportBtn.addEventListener("click", () => {
  if (!currentBlocks.length) return;
  const report = `<!doctype html><html><head><title>AlokSaar Insights Report</title><style>body{font:14px Arial;color:#111;padding:32px}h1{margin:0 0 8px}h2{margin-top:28px}table{width:100%;border-collapse:collapse}th,td{border:1px solid #bbb;padding:8px;text-align:left}.cards{display:flex;gap:12px;flex-wrap:wrap}.card{border:1px solid #bbb;padding:12px;min-width:140px}.label{color:#555;font-size:12px}</style></head><body><h1>AlokSaar Insights Report</h1><p>Generated ${new Date().toLocaleString()}</p>${currentBlocks.map(block => {
    if (block.type === "table") return `<h2>${escapeHtml(block.title || "Table")}</h2><table><thead><tr>${(block.columns || []).map(x => `<th>${escapeHtml(String(x))}</th>`).join("")}</tr></thead><tbody>${(block.rows || []).map(row => `<tr>${row.map(x => `<td>${escapeHtml(String(x))}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
    if (block.type === "card_grid") return `<h2>${escapeHtml(block.title || "Summary")}</h2><div class="cards">${(block.cards || []).map(card => `<div class="card"><div class="label">${escapeHtml(card.label || "")}</div><strong>${escapeHtml(String(card.value ?? ""))}</strong></div>`).join("")}</div>`;
    return `<h2>${escapeHtml(block.title || "Chart")}</h2><p>Chart data: ${(block.labels || []).length} data points. Open Insights Canvas to view the interactive chart.</p>`;
  }).join("")}</body></html>`;
  const url = URL.createObjectURL(new Blob([report], { type: "text/html" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `aloksaar-insights-${new Date().toISOString().slice(0, 10)}.html`;
  link.click();
  URL.revokeObjectURL(url);
});

// If the main /chat page linked here with a pre-filled request (via
// sessionStorage — see chat.js), pick it up and run it immediately.
const pendingRequest = sessionStorage.getItem("aloksaar_pending_viz_request");
if (pendingRequest) {
  sessionStorage.removeItem("aloksaar_pending_viz_request");
  loadHistory().then(() => sendMessage(pendingRequest));
} else {
  try {
    const savedBlocks = JSON.parse(localStorage.getItem(CANVAS_STORAGE_KEY) || "[]");
    if (Array.isArray(savedBlocks) && savedBlocks.length) renderCanvas(savedBlocks);
  } catch (_) {
    localStorage.removeItem(CANVAS_STORAGE_KEY);
  }
  loadHistory();
}
