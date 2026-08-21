const messagesEl = document.getElementById("chat-messages");
const inputEl = document.getElementById("chat-input");
const sendBtn = document.getElementById("send-btn");
const promptsEl = document.getElementById("suggested-prompts");

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function renderAssistantContent(text) {
  if (typeof marked === "undefined" || typeof DOMPurify === "undefined") {
    return `<p>${escapeHtml(text).replace(/\n/g, "<br>")}</p>`;
  }
  const rawHtml = marked.parse(text, { breaks: true });
  return DOMPurify.sanitize(rawHtml);
}

async function copyMessage(button, content) {
  try {
    await navigator.clipboard.writeText(content);
  } catch (_) {
    const helper = document.createElement("textarea");
    helper.value = content;
    helper.style.position = "fixed";
    helper.style.opacity = "0";
    document.body.appendChild(helper);
    helper.select();
    document.execCommand("copy");
    helper.remove();
  }
  const original = button.textContent;
  button.textContent = "✓ Copied";
  window.setTimeout(() => { button.textContent = original; }, 1400);
}

function scrollToBottom() {
  requestAnimationFrame(() => {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  });
}

function addMessage(role, content, isError = false, offerVisualization = false, originalUserMessage = "") {
  const msg = document.createElement("div");
  msg.className = `msg ${role}`;
  msg.dataset.content = content;
  const avatar = role === "assistant" ? "☀" : "🧑";
  const bodyHtml = (role === "assistant" && !isError)
    ? renderAssistantContent(content)
    : escapeHtml(content);

  const vizButtonHtml = offerVisualization
    ? `<button class="viz-trigger-btn" data-request="${escapeHtml(originalUserMessage)}">📊 Open in Insights</button>`
    : "";

  const actionsHtml = role === "user"
    ? `<div class="msg-actions" aria-label="Message actions">
        <button type="button" class="msg-action msg-copy" title="Copy message">⧉ <span>Copy</span></button>
        <button type="button" class="msg-action msg-edit" title="Edit message">✎ <span>Edit</span></button>
        <button type="button" class="msg-action msg-resend" title="Resend message">↻ <span>Resend</span></button>
      </div>`
    : `<div class="msg-actions" aria-label="Message actions">
        <button type="button" class="msg-action msg-copy" title="Copy response">⧉ <span>Copy</span></button>
        ${isError ? "" : `<button type="button" class="msg-action msg-regenerate" title="Regenerate response">↻ <span>Regenerate</span></button>`}
      </div>`;

  msg.innerHTML = `
    <div class="msg-avatar">${avatar}</div>
    <div class="msg-content">
      <div class="msg-bubble ${role === "assistant" ? "md-content" : ""} ${isError ? "msg-error" : ""}">
        ${bodyHtml}
        ${vizButtonHtml}
      </div>
      ${actionsHtml}
    </div>
  `;
  messagesEl.appendChild(msg);

  const vizBtn = msg.querySelector(".viz-trigger-btn");
  if (vizBtn) {
    vizBtn.addEventListener("click", () => {
      sessionStorage.setItem("aloksaar_pending_viz_request", vizBtn.dataset.request);
      window.location.assign("/insights");
    });
  }

  msg.querySelector(".msg-copy")?.addEventListener("click", (event) => copyMessage(event.currentTarget, content));
  msg.querySelector(".msg-edit")?.addEventListener("click", () => {
    inputEl.value = content;
    inputEl.dispatchEvent(new Event("input"));
    inputEl.focus();
  });
  msg.querySelector(".msg-resend")?.addEventListener("click", () => sendMessage(content));
  msg.querySelector(".msg-regenerate")?.addEventListener("click", () => {
    let previous = msg.previousElementSibling;
    while (previous && !previous.classList.contains("user")) previous = previous.previousElementSibling;
    const request = previous?.dataset.content;
    if (request) sendMessage(request);
  });

  scrollToBottom();
  return msg;
}

function addTypingIndicator() {
  const msg = document.createElement("div");
  msg.className = "msg assistant";
  msg.id = "typing-indicator";
  msg.innerHTML = `
    <div class="msg-avatar">☀</div>
    <div class="msg-content">
      <div class="msg-bubble">
        <div class="typing-indicator"><span></span><span></span><span></span></div>
      </div>
    </div>
  `;
  messagesEl.appendChild(msg);
  scrollToBottom();
}

function removeTypingIndicator() {
  const el = document.getElementById("typing-indicator");
  if (el) el.remove();
}

async function loadHistory() {
  try {
    const res = await fetch("/api/chat/history");
    const history = await res.json();
    if (history.length === 0) {
      addMessage("assistant", "Hi! I'm AlokSaar, your AI pharmacy business copilot. Ask me anything — from a quick hello to your profit numbers, inventory, expiry risk, purchasing, or compliance questions.");
    } else {
      history.forEach((m) => addMessage(m.role, m.content));
    }
  } catch (e) {
    addMessage("assistant", "Hi! I'm AlokSaar. Ask me anything about your pharmacy business.");
  }
}

async function sendMessage(text) {
  if (!text.trim() || sendBtn.disabled) return;
  addMessage("user", text);
  inputEl.value = "";
  inputEl.style.height = "auto";
  sendBtn.disabled = true;
  addTypingIndicator();

  try {
    const res = await fetch("/api/chat/message", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text }),
    });
    const data = await res.json();
    removeTypingIndicator();

    if (!res.ok) {
      addMessage("assistant", data.error || "Something went wrong. Please try again.", true);
      return;
    }
    addMessage("assistant", data.assistant_message.content, false, data.offer_visualization, text);
  } catch (e) {
    removeTypingIndicator();
    addMessage("assistant", "Couldn't reach the AlokSaar backend. Check that the server is running.", true);
  } finally {
    sendBtn.disabled = false;
  }
}

sendBtn.addEventListener("click", () => sendMessage(inputEl.value));
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

promptsEl.addEventListener("click", (e) => {
  if (e.target.classList.contains("suggested-prompt")) {
    sendMessage(e.target.dataset.prompt);
  }
});

loadHistory();
