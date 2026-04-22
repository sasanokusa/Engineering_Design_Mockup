const $ = (id) => document.getElementById(id);

const elements = {
  form: $("document-upload-form"),
  scope: $("document-scope"),
  sessionId: $("session-id"),
  externalSessionId: $("external-session-id"),
  collectionName: $("collection-name"),
  collectionDescription: $("collection-description"),
  files: $("document-files"),
  processImmediately: $("process-immediately"),
  refreshCollections: $("refresh-collections"),
  collectionList: $("collection-list"),
  refreshDocuments: $("refresh-documents"),
  documentList: $("document-list"),
  resultList: $("document-result-list"),
  error: $("document-error"),
  searchForm: $("document-search-form"),
  searchQuery: $("document-search-query"),
  searchCollection: $("document-search-collection"),
  searchScope: $("document-search-scope"),
  searchSession: $("document-search-session"),
  searchExternalSession: $("document-search-external-session"),
  searchResults: $("document-search-results"),
  documentDetail: $("document-detail"),
};

function setError(message) {
  elements.error.textContent = message;
  elements.error.hidden = !message;
}

async function getJson(url) {
  const response = await fetch(url);
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || "API request failed");
  return data;
}

async function postJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || "API request failed");
  return data;
}

function buildQuery(params) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && String(value).trim() !== "") {
      search.set(key, value);
    }
  }
  const query = search.toString();
  return query ? `?${query}` : "";
}

async function loadCollections() {
  setError("");
  try {
    const collections = await getJson("/api/document-collections");
    elements.collectionList.replaceChildren(
      ...collections.map((collection) => {
        const item = document.createElement("li");
        item.textContent = `${collection.name} (#${collection.id})`;
        return item;
      }),
    );
  } catch (error) {
    setError(error.message);
  }
}

elements.refreshCollections.addEventListener("click", loadCollections);
elements.refreshDocuments.addEventListener("click", loadDocuments);

async function loadDocuments() {
  setError("");
  try {
    const documents = await getJson("/api/documents");
    renderDocumentList(documents);
  } catch (error) {
    setError(error.message);
  }
}

function renderDocumentList(documents) {
  if (documents.length === 0) {
    const item = document.createElement("li");
    item.textContent = "文書はまだ登録されていません。";
    elements.documentList.replaceChildren(item);
    return;
  }

  elements.documentList.replaceChildren(...documents.map(renderDocumentListItem));
}

function renderDocumentListItem(documentRecord) {
  const item = document.createElement("li");
  item.className = "document-list-item";

  const summary = document.createElement("span");
  summary.textContent = documentSummary(documentRecord);

  const actions = document.createElement("span");
  actions.className = "document-actions";

  const readButton = document.createElement("button");
  readButton.type = "button";
  readButton.textContent = "読む";
  readButton.addEventListener("click", () => loadDocumentDetail(documentRecord.id));
  actions.appendChild(readButton);

  if (documentRecord.status !== "processed") {
    const processButton = document.createElement("button");
    processButton.type = "button";
    processButton.textContent = "処理";
    processButton.addEventListener("click", () => processDocument(documentRecord.id));
    actions.appendChild(processButton);
  }

  item.append(summary, actions);
  return item;
}

function documentSummary(documentRecord) {
  const session = documentRecord.session_id ? ` / session=${documentRecord.session_id}` : "";
  const externalSession = documentRecord.external_session_id
    ? ` / openwebui=${documentRecord.external_session_id}`
    : "";
  return `#${documentRecord.id} ${documentRecord.original_filename}: ${documentRecord.status} / ${formatScope(
    documentRecord.scope,
  )}${session}${externalSession}`;
}

elements.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  setError("");
  elements.resultList.replaceChildren();

  const selectedFiles = Array.from(elements.files.files);
  if (selectedFiles.length === 0) {
    setError("資料ファイルを選択してください。");
    return;
  }

  try {
    await postJson("/api/document-collections", {
      name: elements.collectionName.value,
      description: elements.collectionDescription.value || null,
    });

    const formData = new FormData();
    formData.append("collection", elements.collectionName.value);
    formData.append("scope", elements.scope.value);
    formData.append("process", elements.processImmediately.checked ? "true" : "false");
    if (elements.sessionId.value) {
      formData.append("session_id", elements.sessionId.value);
    }
    if (elements.externalSessionId.value) {
      formData.append("external_session_id", elements.externalSessionId.value);
    }
    for (const file of selectedFiles) {
      formData.append("files", file);
    }

    const response = await fetch("/api/documents/upload", { method: "POST", body: formData });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "資料投入に失敗しました。");

    const lines = data.documents.map((record) => {
      const item = document.createElement("li");
      item.textContent = documentSummary(record);
      if (record.error_message) item.textContent += ` (${record.error_message})`;
      return item;
    });
    for (const failure of data.failures) {
      const item = document.createElement("li");
      item.textContent = `${failure.filename}: failed (${failure.error_message})`;
      lines.push(item);
    }
    elements.resultList.replaceChildren(...lines);
    elements.searchCollection.value = elements.collectionName.value;
    elements.searchScope.value = elements.scope.value;
    elements.searchSession.value = elements.sessionId.value;
    elements.searchExternalSession.value = elements.externalSessionId.value;
    await loadCollections();
    await loadDocuments();
  } catch (error) {
    setError(error.message);
  }
});

elements.searchForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  setError("");
  elements.searchResults.replaceChildren();

  try {
    const data = await postJson("/api/documents/search", {
      query: elements.searchQuery.value,
      collection: elements.searchCollection.value || null,
      scope: elements.searchScope.value || null,
      session_id: elements.searchSession.value ? Number(elements.searchSession.value) : null,
      external_session_id: elements.searchExternalSession.value || null,
      limit: 10,
    });
    const cards = data.results.map((result) => {
      const article = document.createElement("article");
      article.className = "search-result";
      const title = document.createElement("h3");
      title.textContent = `${result.original_filename} / chunk ${result.chunk_index}`;
      const excerpt = document.createElement("p");
      excerpt.textContent = result.text;
      const readButton = document.createElement("button");
      readButton.type = "button";
      readButton.textContent = "この文書を読む";
      readButton.addEventListener("click", () => loadDocumentDetail(result.document_id));
      article.append(title, excerpt, readButton);
      return article;
    });
    if (cards.length === 0) {
      const empty = document.createElement("p");
      empty.className = "assist-note";
      empty.textContent = "該当するchunkは見つかりませんでした。";
      elements.searchResults.replaceChildren(empty);
    } else {
      elements.searchResults.replaceChildren(...cards);
    }
  } catch (error) {
    setError(error.message);
  }
});

async function loadDocumentDetail(documentId) {
  setError("");
  try {
    const detail = await getJson(`/api/documents/${documentId}`);
    renderDocumentDetail(detail);
  } catch (error) {
    setError(error.message);
  }
}

async function processDocument(documentId) {
  setError("");
  try {
    const response = await postJson(`/api/documents/${documentId}/process`, {});
    renderDocumentDetail({
      document: response.document,
      collection: null,
      chunks: response.chunks,
    });
    await loadDocuments();
  } catch (error) {
    setError(error.message);
  }
}

function renderDocumentDetail(detail) {
  const documentRecord = detail.document;
  const heading = document.createElement("h3");
  heading.textContent = `#${documentRecord.id} ${documentRecord.original_filename}`;

  const meta = document.createElement("dl");
  meta.className = "metadata-list";
  appendMeta(meta, "状態", documentRecord.status);
  appendMeta(meta, "保存範囲", formatScope(documentRecord.scope));
  appendMeta(meta, "コレクション", detail.collection?.name || `#${documentRecord.collection_id}`);
  appendMeta(meta, "セッション", documentRecord.session_id || "-");
  appendMeta(meta, "Open WebUI会話ID", documentRecord.external_session_id || "-");
  appendMeta(meta, "正規化", documentRecord.normalization_backend || "-");

  const chunks = document.createElement("div");
  chunks.className = "document-chunks";
  if (detail.chunks.length === 0) {
    const empty = document.createElement("p");
    empty.className = "assist-note";
    empty.textContent = "表示できるchunkはまだありません。";
    chunks.appendChild(empty);
  } else {
    for (const chunk of detail.chunks) {
      const section = document.createElement("section");
      const title = document.createElement("h4");
      title.textContent = `chunk ${chunk.chunk_index}${chunk.heading ? ` / ${chunk.heading}` : ""}`;
      const text = document.createElement("p");
      text.textContent = chunk.text;
      section.append(title, text);
      chunks.appendChild(section);
    }
  }

  elements.documentDetail.replaceChildren(heading, meta, chunks);
}

function appendMeta(list, label, value) {
  const term = document.createElement("dt");
  term.textContent = label;
  const detail = document.createElement("dd");
  detail.textContent = String(value);
  list.append(term, detail);
}

function formatScope(scope) {
  return scope === "temporary" ? "一時文書" : "永続資料";
}

loadCollections();
loadDocuments();
