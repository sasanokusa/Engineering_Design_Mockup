const state = {
  audioFileId: null,
  transcriptId: null,
  cleanedId: null,
  minutesId: null,
  cleanedDirty: false,
  hasRevisionFlags: false,
  recordedBlob: null,
  mediaRecorder: null,
  chunks: [],
};

const $ = (id) => document.getElementById(id);

const elements = {
  form: $("meeting-form"),
  meetingName: $("meeting-name"),
  meetingDate: $("meeting-date"),
  meetingType: $("meeting-type"),
  participants: $("participants"),
  notes: $("notes"),
  audioFile: $("audio-file"),
  recordStart: $("record-start"),
  recordStop: $("record-stop"),
  preview: $("recording-preview"),
  transcribeButton: $("transcribe-button"),
  cleanupButton: $("cleanup-button"),
  minutesButton: $("minutes-button"),
  jobList: $("job-list"),
  error: $("error-message"),
  rawOutput: $("raw-output"),
  cleanedOutput: $("cleaned-output"),
  revisionSuggestionsButton: $("revision-suggestions-button"),
  saveCleanedButton: $("save-cleaned-button"),
  cleanedEditNote: $("cleaned-edit-note"),
  revisionPanel: $("revision-panel"),
  revisionSuggestions: $("revision-suggestions"),
  minutesOutput: $("minutes-output"),
};

elements.meetingDate.valueAsDate = new Date();

function setError(message) {
  elements.error.textContent = message;
  elements.error.hidden = !message;
}

function addJobLine(message) {
  const item = document.createElement("li");
  item.textContent = message;
  elements.jobList.prepend(item);
}

function setButtons() {
  elements.transcribeButton.disabled = !state.audioFileId;
  elements.cleanupButton.disabled = !state.transcriptId;
  elements.minutesButton.disabled = !state.cleanedId || state.cleanedDirty;
  elements.revisionSuggestionsButton.disabled = !state.cleanedId || !state.hasRevisionFlags || state.cleanedDirty;
  elements.saveCleanedButton.disabled = !state.cleanedId || !state.cleanedDirty;
  elements.cleanedOutput.readOnly = !state.cleanedId;
}

async function postJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "API request failed");
  }
  return data;
}

async function patchJson(url, body) {
  const response = await fetch(url, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "API request failed");
  }
  return data;
}

async function getJson(url) {
  const response = await fetch(url);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "API request failed");
  }
  return data;
}

function appendIfPresent(formData, key, value) {
  if (value !== null && value !== undefined && String(value).trim() !== "") {
    formData.append(key, value);
  }
}

function hasRevisionFlags(text) {
  return /要確認|不明|聞き取れない|確認が必要/.test(text);
}

function setCleanedText(text, { dirty = false } = {}) {
  elements.cleanedOutput.value = text;
  state.cleanedDirty = dirty;
  state.hasRevisionFlags = hasRevisionFlags(text);
  updateCleanedAssistNote();
  setButtons();
}

function updateCleanedAssistNote() {
  if (!state.cleanedId) {
    elements.cleanedEditNote.hidden = true;
    elements.cleanedEditNote.textContent = "";
    return;
  }

  if (state.cleanedDirty) {
    elements.cleanedEditNote.textContent = "未保存の修正があります。保存すると議事録生成に反映されます。";
    elements.cleanedEditNote.hidden = false;
    return;
  }

  if (state.hasRevisionFlags) {
    elements.cleanedEditNote.textContent = "要確認箇所があります。修正案を確認し、必要に応じて手動で直してください。";
    elements.cleanedEditNote.hidden = false;
    return;
  }

  elements.cleanedEditNote.hidden = true;
  elements.cleanedEditNote.textContent = "";
}

elements.recordStart.addEventListener("click", async () => {
  setError("");
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    state.chunks = [];
    state.mediaRecorder = new MediaRecorder(stream);
    state.mediaRecorder.addEventListener("dataavailable", (event) => {
      if (event.data.size > 0) state.chunks.push(event.data);
    });
    state.mediaRecorder.addEventListener("stop", () => {
      state.recordedBlob = new Blob(state.chunks, { type: state.mediaRecorder.mimeType || "audio/webm" });
      elements.preview.src = URL.createObjectURL(state.recordedBlob);
      elements.preview.hidden = false;
      stream.getTracks().forEach((track) => track.stop());
    });
    state.mediaRecorder.start();
    elements.recordStart.disabled = true;
    elements.recordStop.disabled = false;
    addJobLine("録音中です。");
  } catch (error) {
    setError(`録音を開始できません: ${error.message}`);
  }
});

elements.recordStop.addEventListener("click", () => {
  if (state.mediaRecorder && state.mediaRecorder.state !== "inactive") {
    state.mediaRecorder.stop();
    addJobLine("録音を停止しました。");
  }
  elements.recordStart.disabled = false;
  elements.recordStop.disabled = true;
});

elements.audioFile.addEventListener("change", () => {
  if (elements.audioFile.files.length > 0) {
    state.recordedBlob = null;
    elements.preview.hidden = true;
  }
});

elements.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  setError("");
  const selectedFile = elements.audioFile.files[0];
  const uploadFile =
    state.recordedBlob ||
    selectedFile;

  if (!uploadFile) {
    setError("音声を録音するか、音声ファイルを選択してください。");
    return;
  }

  const formData = new FormData();
  if (state.recordedBlob) {
    formData.append("file", state.recordedBlob, `recording-${Date.now()}.webm`);
  } else {
    formData.append("file", selectedFile);
  }
  formData.append("meeting_name", elements.meetingName.value);
  appendIfPresent(formData, "meeting_date", elements.meetingDate.value);
  appendIfPresent(formData, "meeting_type", elements.meetingType.value);
  appendIfPresent(formData, "participants", elements.participants.value);
  appendIfPresent(formData, "notes", elements.notes.value);

  try {
    const response = await fetch("/api/files/audio", { method: "POST", body: formData });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "音声登録に失敗しました。");
    state.audioFileId = data.audio_file.id;
    state.transcriptId = null;
    state.cleanedId = null;
    state.minutesId = null;
    state.cleanedDirty = false;
    state.hasRevisionFlags = false;
    elements.rawOutput.value = "";
    setCleanedText("");
    elements.revisionPanel.hidden = true;
    elements.revisionSuggestions.textContent = "";
    elements.minutesOutput.value = "";
    setButtons();
    addJobLine(`音声登録完了: audio_file_id=${state.audioFileId}`);
  } catch (error) {
    setError(error.message);
  }
});

async function createAndPollJob(endpoint, payload, label, onComplete) {
  setError("");
  try {
    const job = await postJson(endpoint, payload);
    addJobLine(`${label}: job_id=${job.id} queued`);
    const timer = window.setInterval(async () => {
      try {
        const current = await getJson(`/api/jobs/${job.id}`);
        addJobLine(`${label}: ${current.status}`);
        if (current.status === "completed") {
          window.clearInterval(timer);
          await onComplete(current);
          setButtons();
        }
        if (current.status === "failed") {
          window.clearInterval(timer);
          setError(`${label} failed: ${current.error_message || "unknown error"}`);
        }
      } catch (error) {
        window.clearInterval(timer);
        setError(error.message);
      }
    }, 1000);
  } catch (error) {
    setError(error.message);
  }
}

elements.transcribeButton.addEventListener("click", () => {
  if (!state.audioFileId) {
    setError("音声がまだ登録されていません。");
    return;
  }
  createAndPollJob(
    "/api/jobs/transcription",
    { audio_file_id: state.audioFileId },
    "文字起こし",
    async (job) => {
      state.transcriptId = job.result_id;
      const transcript = await getJson(`/api/transcripts/${state.transcriptId}`);
      elements.rawOutput.value = transcript.text;
    },
  );
});

elements.cleanupButton.addEventListener("click", () => {
  if (!state.transcriptId) {
    setError("文字起こしがまだ完了していません。");
    return;
  }
  createAndPollJob(
    "/api/jobs/cleanup",
    { transcript_id: state.transcriptId },
    "整形",
    async (job) => {
      state.cleanedId = job.result_id;
      const cleaned = await getJson(`/api/cleaned/${state.cleanedId}`);
      setCleanedText(cleaned.text);
      elements.revisionPanel.hidden = true;
      elements.revisionSuggestions.textContent = "";
      if (state.hasRevisionFlags) {
        await loadRevisionSuggestions();
      }
    },
  );
});

elements.cleanedOutput.addEventListener("input", () => {
  if (!state.cleanedId) return;
  state.cleanedDirty = true;
  state.hasRevisionFlags = hasRevisionFlags(elements.cleanedOutput.value);
  updateCleanedAssistNote();
  setButtons();
});

async function saveCleanedText() {
  if (!state.cleanedId) {
    setError("整形済みテキストがまだありません。");
    return;
  }

  setError("");
  try {
    const cleaned = await patchJson(`/api/cleaned/${state.cleanedId}`, {
      text: elements.cleanedOutput.value,
    });
    setCleanedText(cleaned.text);
    addJobLine("整形済みテキストを保存しました。");
  } catch (error) {
    setError(error.message);
  }
}

async function loadRevisionSuggestions() {
  if (!state.cleanedId) {
    setError("整形済みテキストがまだありません。");
    return;
  }

  setError("");
  try {
    const response = await postJson(`/api/cleaned/${state.cleanedId}/revision-suggestions`, {});
    elements.revisionSuggestions.textContent = response.suggestions;
    elements.revisionPanel.hidden = false;
    state.hasRevisionFlags = response.has_review_flags;
    updateCleanedAssistNote();
    setButtons();
  } catch (error) {
    setError(error.message);
  }
}

elements.saveCleanedButton.addEventListener("click", saveCleanedText);
elements.revisionSuggestionsButton.addEventListener("click", loadRevisionSuggestions);

elements.minutesButton.addEventListener("click", () => {
  if (!state.cleanedId) {
    setError("整形済みテキストがまだありません。");
    return;
  }
  if (state.cleanedDirty) {
    setError("未保存の修正があります。先に「修正を保存」を押してください。");
    return;
  }
  createAndPollJob(
    "/api/jobs/minutes",
    { cleaned_transcript_id: state.cleanedId },
    "議事録生成",
    async (job) => {
      state.minutesId = job.result_id;
      const minutes = await getJson(`/api/minutes/${state.minutesId}`);
      elements.minutesOutput.value = minutes.content;
    },
  );
});

setButtons();
