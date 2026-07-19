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
  const rawHtml = marked.parse(text, { breaks: true });
  return DOMPurify.sanitize(rawHtml);
}

function scrollToBottom() {
  requestAnimationFrame(() => {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  });
}

function addMessage(role, content, isError = false, offerVisualization = false, originalUserMessage = "") {
  const msg = document.createElement("div");
  msg.className = `msg ${role}`;
  const avatar = role === "assistant" ? "☀" : "🧑";
  const bodyHtml = (role === "assistant" && !isError)
    ? renderAssistantContent(content)
    : escapeHtml(content);

  const vizButtonHtml = offerVisualization
    ? `<button class="viz-trigger-btn" data-request="${escapeHtml(originalUserMessage)}">📊 Open in Insights</button>`
    : "";

  msg.innerHTML = `
    <div class="msg-avatar">${avatar}</div>
    <div class="msg-bubble ${role === "assistant" ? "md-content" : ""} ${isError ? "msg-error" : ""}">
      ${bodyHtml}
      ${vizButtonHtml}
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

  scrollToBottom();
  return msg;
}

function addTypingIndicator() {
  const msg = document.createElement("div");
  msg.className = "msg assistant";
  msg.id = "typing-indicator";
  msg.innerHTML = `
    <div class="msg-avatar">☀</div>
    <div class="msg-bubble">
      <div class="typing-indicator"><span></span><span></span><span></span></div>
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
  if (!text.trim()) return;
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
