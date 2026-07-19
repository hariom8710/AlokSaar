const CSV_TYPES = [
  { key: "suppliers", label: "1. Suppliers", desc: "supplier_name, contact, reliability_score, avg_delivery_days" },
  { key: "medicines", label: "2. Medicines", desc: "medicine_name, category, unit, reorder_level, ideal_stock_level, unit_cost, unit_price, supplier_name" },
  { key: "stock_batches", label: "3. Stock Batches", desc: "medicine_name, batch_number, quantity, expiry_date, received_date" },
  { key: "sales", label: "4. Sales", desc: "medicine_name, quantity, sale_price, cost_price, sale_date" },
  { key: "purchases", label: "5. Purchases", desc: "medicine_name, supplier_name, quantity, unit_cost, order_date, status" },
  { key: "stock_out_events", label: "6. Stock-Out Events", desc: "medicine_name, start_date, end_date, estimated_lost_sales" },
];

const container = document.getElementById("upload-cards");

async function uploadFile(key, resultEl, input) {
  if (!input.files.length) {
    resultEl.innerHTML = `<span style="color:var(--danger-red)">Choose a file first.</span>`;
    return;
  }
  const formData = new FormData();
  formData.append("file", input.files[0]);
  resultEl.innerHTML = `<span style="color:var(--ink-60)">Uploading…</span>`;

  try {
    const res = await fetch(`/api/upload/${key}`, { method: "POST", body: formData });
    const data = await res.json();

    if (!res.ok) {
      resultEl.innerHTML = `<span style="color:var(--danger-red)">${data.error || "Upload failed."}</span>`;
      return;
    }

    let html = `<span style="color:var(--ok-green)">✓ Uploaded — Inserted: ${data.inserted}, Skipped: ${data.skipped}</span>`;
    if (data.errors && data.errors.length) {
      html += `<details style="margin-top:6px;"><summary style="cursor:pointer; color:var(--gold)">${data.errors.length} issue(s)</summary>`;
      html += data.errors.slice(0, 20).map(e => `<div style="color:var(--ink-60); margin-top:4px;">${e}</div>`).join("");
      html += `</details>`;
    }
    resultEl.innerHTML = html;
  } catch (e) {
    resultEl.innerHTML = `<span style="color:var(--danger-red)">Upload failed: ${e.message || e}</span>`;
  }
}

CSV_TYPES.forEach((type) => {
  const card = document.createElement("div");
  card.className = "card";
  card.innerHTML = `
    <div class="card-label">${type.label}</div>
    <p style="font-size:12px; color:var(--ink-60); margin: 4px 0 14px;">${type.desc}</p>
    <input type="file" accept=".csv" class="file-input" style="color:var(--ink-70); font-size:13px;" />
    <button class="send-btn upload-btn" style="margin-top:12px;">Upload</button>
    <div class="result-area" style="margin-top:12px; font-size:12.5px;"></div>
  `;
  container.appendChild(card);

  const input = card.querySelector(".file-input");
  const button = card.querySelector(".upload-btn");
  const resultEl = card.querySelector(".result-area");

  button.addEventListener("click", () => uploadFile(type.key, resultEl, input));
});
