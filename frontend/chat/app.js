import DOMPurify from "/vendor/purify.es.mjs";
import { marked } from "/vendor/marked.esm.js";

marked.setOptions({
  gfm: true,
  breaks: true,
});

const state = {
  sessions: [],
  activeSessionId: null,
  tools: [],
  attachments: [],
  sending: false,
};

const $ = (id) => document.getElementById(id);

const elements = {
  newSessionButton: $("new-session-button"),
  sessionCount: $("session-count"),
  sessionList: $("session-list"),
  toolCount: $("tool-count"),
  toolLinkList: $("tool-link-list"),
  activeMeta: $("active-meta"),
  activeTitle: $("active-title"),
  messages: $("messages"),
  attachments: $("attachments"),
  attachmentList: $("attachment-list"),
  form: $("message-form"),
  attachButton: $("attach-button"),
  attachmentFiles: $("attachment-files"),
  input: $("message-input"),
  useTools: $("use-tools"),
  sendButton: $("send-button"),
  error: $("error-message"),
  toolSuggestions: $("tool-suggestions"),
  toolSuggestionList: $("tool-suggestion-list"),
};

function setError(message) {
  elements.error.textContent = message;
  elements.error.hidden = !message;
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  if (response.status === 204) {
    return null;
  }
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "API request failed");
  }
  return data;
}

function jsonOptions(method, body) {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

function requestOptions(method) {
  return { method };
}

async function loadSessions() {
  state.sessions = await requestJson("/api/chat/sessions");
  renderSessions();
  if (!state.activeSessionId && state.sessions.length > 0) {
    await selectSession(state.sessions[0].id);
  }
  if (state.sessions.length === 0) {
    await createSession();
  }
}

async function loadTools() {
  try {
    state.tools = await requestJson("/api/chat/tools");
    renderToolMenu(state.tools);
  } catch (error) {
    setError(error.message);
  }
}

async function createSession() {
  setError("");
  const session = await requestJson(
    "/api/chat/sessions",
    jsonOptions("POST", { title: "新規チャット" }),
  );
  state.sessions.unshift(session);
  renderSessions();
  await selectSession(session.id);
}

async function deleteSession(sessionId) {
  const session = state.sessions.find((item) => item.id === sessionId);
  const title = session?.title || "このチャット";
  if (!window.confirm(`「${title}」を削除しますか？`)) {
    return;
  }

  setError("");
  await requestJson(`/api/chat/sessions/${sessionId}`, requestOptions("DELETE"));
  state.sessions = state.sessions.filter((item) => item.id !== sessionId);
  if (state.activeSessionId === sessionId) {
    state.activeSessionId = null;
    state.attachments = [];
    elements.activeTitle.textContent = "新規チャット";
    elements.messages.innerHTML = "";
    renderAttachments([]);
    renderToolSuggestions([]);
    if (state.sessions.length > 0) {
      await selectSession(state.sessions[0].id);
    } else {
      await createSession();
    }
  }
  renderSessions();
}

async function selectSession(sessionId) {
  setError("");
  state.activeSessionId = sessionId;
  const detail = await requestJson(`/api/chat/sessions/${sessionId}`);
  elements.activeTitle.textContent = detail.session.title;
  renderSessions();
  renderMessages(detail.messages);
  await loadAttachments(sessionId);
  renderToolSuggestions([]);
}

function renderSessions() {
  elements.sessionList.innerHTML = "";
  elements.sessionCount.textContent = String(state.sessions.length);
  for (const session of state.sessions) {
    const row = document.createElement("div");
    row.className = `session-row${session.id === state.activeSessionId ? " active" : ""}`;

    const button = document.createElement("button");
    button.type = "button";
    button.className = "session-item";
    button.textContent = session.title;
    button.title = session.title;
    button.addEventListener("click", () => selectSession(session.id));

    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "session-delete";
    deleteButton.setAttribute("aria-label", `${session.title}を削除`);
    deleteButton.textContent = "削除";
    deleteButton.addEventListener("click", (event) => {
      event.stopPropagation();
      deleteSession(session.id).catch((error) => setError(error.message));
    });

    row.append(button, deleteButton);
    elements.sessionList.appendChild(row);
  }
}

function renderToolMenu(tools) {
  elements.toolCount.textContent = `${tools.length}`;
  const cards = tools.map((tool) => {
    const link = document.createElement("a");
    link.className = "tool-link available";
    link.href = toolHref(tool.name);

    const title = document.createElement("strong");
    title.textContent = tool.display_name;
    const description = document.createElement("span");
    description.textContent = `${tool.status} / ${tool.description}`;

    link.append(title, description);
    return link;
  });
  elements.toolLinkList.replaceChildren(...cards);
}

function toolHref(toolName) {
  return (
    {
      minutes_tool: "/",
      document_search_tool: "/documents/",
      document_read_tool: "/documents/",
      document_compare_tool: "/compare/",
    }[toolName] || "/chat/"
  );
}

function renderMessages(messages) {
  elements.messages.innerHTML = "";
  if (messages.length === 0) {
    elements.messages.appendChild(createEmptyState());
    return;
  }
  for (const message of messages) {
    appendMessage(message);
  }
  scrollMessagesToBottom();
}

function appendMessage(message) {
  removeEmptyState();
  const wrapper = document.createElement("article");
  wrapper.className = `message ${message.role}`;

  const avatar = document.createElement("div");
  avatar.className = "message-avatar";
  avatar.textContent = message.role === "user" ? "ME" : "AI";

  const card = document.createElement("div");
  card.className = "message-card";

  const meta = document.createElement("div");
  meta.className = "message-meta";
  const role = document.createElement("span");
  role.textContent = message.role === "user" ? "あなた" : "AI";
  const time = document.createElement("span");
  time.textContent = formatMessageTime(message.created_at);
  meta.append(role, time);

  const body = document.createElement("div");
  body.className = message.role === "assistant" ? "message-body markdown-body" : "message-body";
  if (message.role === "assistant") {
    body.innerHTML = renderMarkdown(message.content);
  } else {
    body.textContent = message.content;
  }

  card.append(meta, body);
  wrapper.append(avatar, card);
  elements.messages.appendChild(wrapper);
}

function renderMarkdown(markdown) {
  return DOMPurify.sanitize(marked.parse(markdown || ""));
}

function createEmptyState() {
  const wrapper = document.createElement("div");
  wrapper.id = "empty-state";
  wrapper.className = "empty-state";
  wrapper.innerHTML = `
    <h3>何を手伝いましょうか？</h3>
    <div class="prompt-grid">
      <button type="button" data-prompt="校内資料を確認するための質問文を一緒に整理してください。">
        校内資料の確認
      </button>
      <button type="button" data-prompt="レポートを読む前に、確認すべき観点を整理してください。">
        レポート読解の準備
      </button>
      <button type="button" data-prompt="文書比較で見るべきポイントを短く教えてください。">
        文書比較の観点
      </button>
      <button type="button" data-prompt="保護者面談の議事録作成で注意する点を整理してください。">
        議事録作成の注意点
      </button>
    </div>
  `;
  return wrapper;
}

function removeEmptyState() {
  elements.messages.querySelector("#empty-state")?.remove();
}

function formatMessageTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString("ja-JP", { hour: "2-digit", minute: "2-digit" });
}

function renderToolSuggestions(tools) {
  elements.toolSuggestionList.innerHTML = "";
  elements.toolSuggestions.hidden = tools.length === 0;
  for (const tool of tools) {
    const chip = document.createElement("div");
    chip.className = "tool-chip";
    const title = document.createElement("strong");
    title.textContent = `${tool.display_name} (${tool.status})`;
    const description = document.createElement("span");
    description.textContent = tool.description;
    chip.append(title, description);
    elements.toolSuggestionList.appendChild(chip);
  }
}

async function loadAttachments(sessionId) {
  try {
    state.attachments = await requestJson(`/api/documents?scope=temporary&session_id=${sessionId}`);
    renderAttachments(state.attachments);
  } catch (error) {
    setError(error.message);
  }
}

function renderAttachments(attachments) {
  elements.attachments.hidden = attachments.length === 0;
  elements.attachmentList.replaceChildren(
    ...attachments.map((documentRecord) => {
      const item = document.createElement("div");
      item.className = "attachment-chip";
      item.title = documentRecord.original_filename;

      const body = document.createElement("a");
      body.href = "/documents/";
      body.className = "attachment-chip-body";
      const title = document.createElement("strong");
      title.textContent = `#${documentRecord.id} ${documentRecord.original_filename}`;
      const status = document.createElement("span");
      status.textContent = documentRecord.status;
      body.append(title, status);

      const removeButton = document.createElement("button");
      removeButton.type = "button";
      removeButton.className = "attachment-remove";
      removeButton.setAttribute("aria-label", `${documentRecord.original_filename} の添付を解除`);
      removeButton.title = "添付を解除";
      removeButton.textContent = "×";
      removeButton.addEventListener("click", () => detachAttachment(documentRecord.id));

      item.append(body, removeButton);
      return item;
    }),
  );
}

async function detachAttachment(documentId) {
  if (!state.activeSessionId) return;

  setError("");
  try {
    await requestJson(
      `/api/documents/${documentId}?session_id=${state.activeSessionId}`,
      requestOptions("DELETE"),
    );
    state.attachments = state.attachments.filter((documentRecord) => documentRecord.id !== documentId);
    renderAttachments(state.attachments);
  } catch (error) {
    setError(error.message);
  }
}

function scrollMessagesToBottom() {
  elements.messages.scrollTop = elements.messages.scrollHeight;
}

async function sendMessage(event) {
  event.preventDefault();
  const content = elements.input.value.trim();
  if (!content || !state.activeSessionId || state.sending) return;

  setError("");
  state.sending = true;
  elements.sendButton.disabled = true;
  elements.input.value = "";

  const optimisticUserMessage = {
    role: "user",
    content,
  };
  appendMessage(optimisticUserMessage);
  appendThinkingMessage();
  scrollMessagesToBottom();

  try {
    const response = await requestJson(
      `/api/chat/sessions/${state.activeSessionId}/messages`,
      jsonOptions("POST", {
        content,
        use_tools: elements.useTools.checked,
      }),
    );
    removeThinkingMessage();
    elements.messages.lastElementChild?.remove();
    appendMessage(response.user_message);
    appendMessage(response.assistant_message);
    renderToolSuggestions(response.tool_suggestions);
    elements.activeTitle.textContent = response.session.title;
    await refreshSessionsKeepingActive();
    scrollMessagesToBottom();
  } catch (error) {
    removeThinkingMessage();
    setError(error.message);
    await selectSession(state.activeSessionId);
  } finally {
    state.sending = false;
    elements.sendButton.disabled = false;
    elements.input.focus();
  }
}

function appendThinkingMessage() {
  const wrapper = document.createElement("article");
  wrapper.className = "message assistant thinking";
  wrapper.dataset.thinking = "true";

  const avatar = document.createElement("div");
  avatar.className = "message-avatar";
  avatar.textContent = "AI";

  const card = document.createElement("div");
  card.className = "message-card";

  const meta = document.createElement("div");
  meta.className = "message-meta";
  meta.innerHTML = "<span>AI</span><span></span>";

  const body = document.createElement("div");
  body.className = "message-body thinking-body";
  body.textContent = "考え中です";

  card.append(meta, body);
  wrapper.append(avatar, card);
  elements.messages.appendChild(wrapper);
}

function removeThinkingMessage() {
  const thinking = elements.messages.querySelector("[data-thinking='true']");
  thinking?.remove();
}

async function refreshSessionsKeepingActive() {
  state.sessions = await requestJson("/api/chat/sessions");
  renderSessions();
}

elements.newSessionButton.addEventListener("click", () => {
  createSession().catch((error) => setError(error.message));
});

elements.form.addEventListener("submit", sendMessage);

elements.attachButton.addEventListener("click", () => {
  if (!state.activeSessionId) {
    setError("先にチャットを作成してください。");
    return;
  }
  elements.attachmentFiles.click();
});

elements.attachmentFiles.addEventListener("change", async () => {
  const files = Array.from(elements.attachmentFiles.files);
  if (files.length === 0 || !state.activeSessionId) return;

  setError("");
  elements.attachButton.disabled = true;
  try {
    const formData = new FormData();
    formData.append("scope", "temporary");
    formData.append("session_id", String(state.activeSessionId));
    formData.append("collection", `chat-session-${state.activeSessionId}`);
    formData.append("process", "true");
    for (const file of files) {
      formData.append("files", file);
    }
    const response = await fetch("/api/documents/upload", { method: "POST", body: formData });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "文書の添付に失敗しました。");
    }
    await loadAttachments(state.activeSessionId);
  } catch (error) {
    setError(error.message);
  } finally {
    elements.attachmentFiles.value = "";
    elements.attachButton.disabled = false;
  }
});

elements.input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
    elements.form.requestSubmit();
  }
});

elements.messages.addEventListener("click", (event) => {
  const promptButton = event.target.closest("[data-prompt]");
  if (!promptButton) return;
  elements.input.value = promptButton.dataset.prompt || "";
  elements.input.focus();
});

loadTools();
loadSessions().catch((error) => setError(error.message));
