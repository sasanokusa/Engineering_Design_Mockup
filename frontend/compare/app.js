const state = {
  documents: [],
  selectedIds: new Set(),
  pollTimer: null,
};

const $ = (id) => document.getElementById(id);

const elements = {
  form: $("compare-form"),
  picker: $("document-picker"),
  refreshDocuments: $("refresh-documents"),
  selectedCount: $("selected-count"),
  granularity: $("compare-granularity"),
  threshold: $("similarity-threshold"),
  limit: $("match-limit"),
  startCompare: $("start-compare"),
  jobList: $("compare-job-list"),
  pairResults: $("pair-results"),
  similarResults: $("similar-chunk-results"),
  error: $("compare-error"),
};

function setError(message) {
  elements.error.textContent = message;
  elements.error.hidden = !message;
}

function addJobLine(message) {
  const item = document.createElement("li");
  item.textContent = message;
  elements.jobList.prepend(item);
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
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

async function loadDocuments() {
  setError("");
  try {
    state.documents = await requestJson("/api/documents?status=processed");
    state.selectedIds = new Set(
      Array.from(state.selectedIds).filter((documentId) =>
        state.documents.some((document) => document.id === documentId),
      ),
    );
    renderDocuments();
  } catch (error) {
    setError(error.message);
  }
}

function renderDocuments() {
  elements.picker.replaceChildren();
  if (state.documents.length === 0) {
    const empty = document.createElement("p");
    empty.className = "assist-note";
    empty.textContent = "処理済み文書がまだありません。資料投入画面で文書を追加してください。";
    elements.picker.appendChild(empty);
    updateSelectedCount();
    return;
  }

  for (const documentRecord of state.documents) {
    const label = document.createElement("label");
    label.className = "document-choice";

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.value = String(documentRecord.id);
    checkbox.checked = state.selectedIds.has(documentRecord.id);
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) {
        state.selectedIds.add(documentRecord.id);
      } else {
        state.selectedIds.delete(documentRecord.id);
      }
      updateSelectedCount();
    });

    const body = document.createElement("span");
    const title = document.createElement("strong");
    title.textContent = `#${documentRecord.id} ${documentRecord.original_filename}`;
    const meta = document.createElement("small");
    meta.textContent = `collection_id=${documentRecord.collection_id} / ${documentRecord.status}`;
    body.append(title, meta);
    label.append(checkbox, body);
    elements.picker.appendChild(label);
  }
  updateSelectedCount();
}

function updateSelectedCount() {
  elements.selectedCount.textContent = `${state.selectedIds.size}件選択中`;
  elements.startCompare.disabled = state.selectedIds.size < 2;
}

elements.refreshDocuments.addEventListener("click", loadDocuments);

elements.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  setError("");
  elements.pairResults.replaceChildren();
  elements.similarResults.replaceChildren();

  const documentIds = Array.from(state.selectedIds);
  if (documentIds.length < 2) {
    setError("比較する文書を2件以上選択してください。");
    return;
  }

  try {
    const job = await requestJson(
      "/api/compare/jobs",
      jsonOptions("POST", {
        document_ids: documentIds,
        min_similarity: Number(elements.threshold.value),
        limit: Number(elements.limit.value),
        granularity: elements.granularity.value,
      }),
    );
    addJobLine(`比較: job_id=${job.id} queued`);
    pollCompareJob(job.id);
  } catch (error) {
    setError(error.message);
  }
});

function pollCompareJob(jobId) {
  if (state.pollTimer) {
    window.clearInterval(state.pollTimer);
  }

  state.pollTimer = window.setInterval(async () => {
    try {
      const response = await requestJson(`/api/compare/jobs/${jobId}`);
      addJobLine(`比較: ${response.job.status}`);
      if (response.job.status === "completed") {
        window.clearInterval(state.pollTimer);
        state.pollTimer = null;
        renderCompareResult(response.result);
      }
      if (response.job.status === "failed") {
        window.clearInterval(state.pollTimer);
        state.pollTimer = null;
        setError(response.job.error_message || "比較ジョブに失敗しました。");
      }
    } catch (error) {
      window.clearInterval(state.pollTimer);
      state.pollTimer = null;
      setError(error.message);
    }
  }, 1000);
}

function renderCompareResult(result) {
  if (!result) {
    setError("比較結果を取得できませんでした。");
    return;
  }

  const pairCards = result.pairs.map((pair) => {
    const article = document.createElement("article");
    article.className = "search-result compare-card";

    const title = document.createElement("h3");
    title.textContent = `${pair.left_filename} と ${pair.right_filename}`;

    const score = document.createElement("p");
    score.textContent = `全体類似度: ${formatPercent(pair.overall_similarity)} / 類似単位: ${
      pair.matched_chunk_count
    }件 / 粒度: ${formatGranularity(result.granularity)}`;

    const summary = document.createElement("dl");
    summary.className = "diff-summary";
    appendSummary(summary, "共通行", pair.diff_summary.equal_lines);
    appendSummary(summary, "追加行", pair.diff_summary.inserted_lines);
    appendSummary(summary, "削除行", pair.diff_summary.deleted_lines);
    appendSummary(summary, "置換前", pair.diff_summary.replaced_left_lines);
    appendSummary(summary, "置換後", pair.diff_summary.replaced_right_lines);

    article.append(title, score, summary);
    for (const block of pair.diff_excerpt) {
      article.appendChild(renderDiffBlock(block));
    }
    return article;
  });
  elements.pairResults.replaceChildren(...pairCards);

  const similarCards = result.similar_chunks.map((match) => {
    const article = document.createElement("article");
    article.className = "similar-card";

    const title = document.createElement("h3");
    title.textContent = `${formatPercent(match.similarity)} / ${match.method} / ${formatGranularity(
      match.left.unit_type,
    )}`;

    const grid = document.createElement("div");
    grid.className = "similar-grid";
    grid.append(renderChunk("左", match.left), renderChunk("右", match.right));
    article.append(title, grid);
    return article;
  });

  if (similarCards.length === 0) {
    const empty = document.createElement("p");
    empty.className = "assist-note";
    empty.textContent = "しきい値以上の類似chunkは見つかりませんでした。";
    elements.similarResults.replaceChildren(empty);
  } else {
    elements.similarResults.replaceChildren(...similarCards);
  }
}

function appendSummary(list, label, value) {
  const term = document.createElement("dt");
  term.textContent = label;
  const detail = document.createElement("dd");
  detail.textContent = String(value);
  list.append(term, detail);
}

function renderDiffBlock(block) {
  const wrapper = document.createElement("div");
  wrapper.className = "diff-block";

  const heading = document.createElement("strong");
  heading.textContent = `${block.operation} / 左${block.left_start_line}行目 / 右${block.right_start_line}行目`;

  const left = document.createElement("pre");
  left.textContent = block.left_text || "(なし)";
  const right = document.createElement("pre");
  right.textContent = block.right_text || "(なし)";

  wrapper.append(heading, left, right);
  return wrapper;
}

function renderChunk(label, chunk) {
  const wrapper = document.createElement("section");
  const heading = document.createElement("h4");
  heading.textContent = `${label}: #${chunk.document_id} ${chunk.original_filename} ${
    chunk.unit_label || `chunk ${chunk.chunk_index}`
  }`;
  const text = document.createElement("p");
  text.textContent = chunk.text;
  wrapper.append(heading, text);
  return wrapper;
}

function formatPercent(value) {
  return `${Math.round(Number(value) * 1000) / 10}%`;
}

function formatGranularity(value) {
  return (
    {
      chunk: "チャンク",
      paragraph: "段落",
      section: "節",
      full: "全文",
    }[value] || value
  );
}

loadDocuments();
