# Local School AI Platform Mock

校内機密データ向けローカルAI支援基盤の初期実装です。

Open WebUI 採用構成では、通常チャットUI、会話セッション、モデル選択UIは Open WebUI に任せます。このリポジトリの FastAPI は、学校向けの業務データ処理バックエンドとして、文書基盤、比較、議事録、監査ログの責務を保持します。機微データを外部クラウドへ送る前提にはしていません。

## 今回の構成

- Backend: FastAPI
- Chat UI: Open WebUI
- Local tools UI: FastAPI配信の薄いHTML/CSS/JavaScript
- DB: SQLite
- Job: SQLite上の `queued / running / completed / failed`
- LLM: Open WebUI から Ollama / SGLang / OpenAI-compatible runtime に接続
- ASR: Whisper系 adapter
- デモ用: `mock` LLM / `mock` ASR
- Open WebUI bridge: Open WebUI から自前APIを呼ぶためのツール境界
- Documents: collection 管理、永続/一時の原本保存、Docling優先正規化、chunk JSONL、SQLite FTS5検索
- Compare: 処理済み文書の比較ジョブ、比較粒度、版差サマリ、類似箇所抽出
- Legacy Chat: 旧独自チャットAPIは互換・検証用として残し、主導線からは外しています

主なディレクトリ:

```text
backend/
  api/            FastAPI routers
  services/       transcription / cleanup / minutes / document services
  orchestrator/   legacy chat orchestration
  tooling/        tool registry metadata
  adapters/
    llm/          LLM adapter protocol and implementations
    asr/          ASR adapter protocol and implementations
  models/         SQLAlchemy DB models and Pydantic schemas
  repositories/   SQLite persistence and file storage
  workers/        simple job runner
  cli.py          school-ai CLI entrypoint
  prompts/        legacy chat, cleanup, minutes prompts
frontend/         local tool launcher UI
tests/            smoke and adapter tests
```

## 起動手順

Python 3.11以上を想定しています。

```bash
cd ~/Documents/engineering_design_2026
uv sync --extra dev
cp .env.example .env
```

Docling を使って PDF / DOCX / PPTX などを正規化する場合は documents extra も入れます。Docling が未導入でも、Markdown / text / CSV などのテキスト系ファイルはフォールバック正規化で処理できます。

```bash
uv sync --extra dev --extra documents
```

モデルなしでまず流れだけ確認する場合は、`.env` を以下に変更します。

```env
LLM_PROVIDER=mock
ASR_PROVIDER=mock
```

起動:

```bash
uv run uvicorn backend.main:app --reload --port 8000
```

ブラウザで開きます。

```bash
open http://127.0.0.1:8000/chat/
```

`/chat/` は独自チャットではなく Open WebUI 連携情報ページです。通常チャットは Open WebUI を起動し、必要に応じて `/api/openwebui/...` のツールAPIを呼びます。議事録、資料投入、文書比較の専用画面は、それぞれ `/`、`/documents/`、`/compare/` から直接確認できます。

`uv` を使わない場合:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn backend.main:app --reload --port 8000
```

## Open WebUI 連携

Open WebUI 側の設定では、通常チャットのモデル接続先を Ollama / SGLang / OpenAI-compatible local server に向けます。この FastAPI は LLM runtime ではなく、Open WebUI から呼ばれる学校向け業務APIとして扱います。

連携確認:

```bash
curl http://127.0.0.1:8000/api/openwebui/manifest
curl http://127.0.0.1:8000/api/openwebui/tools
```

一時文書は Open WebUI の会話IDなど任意の外部セッションIDで紐づけます。

```bash
curl -F "external_session_id=owui-chat-1" \
  -F "files=@./docs/report.md" \
  http://127.0.0.1:8000/api/openwebui/tools/session-documents/upload
```

## フロントエンド依存

旧独自チャットUIで使っていた `marked` と `DOMPurify` は `frontend/vendor/` に残しています。現在の主導線では Open WebUI を採用するため、FastAPI配信の画面は議事録、資料投入、文書比較、連携情報の軽量UIに限定しています。

依存を入れ直す場合:

```bash
npm install
npm run vendor:chat
```

同梱ファイル:

- `frontend/vendor/marked.esm.js`
- `frontend/vendor/purify.es.mjs`
- `frontend/vendor/marked.LICENSE.md`
- `frontend/vendor/dompurify.LICENSE`

## 必要な環境変数

`.env.example` を参照してください。主な設定は以下です。

| 変数 | 用途 |
| --- | --- |
| `LOCAL_SCHOOL_AI_DATA_DIR` | SQLite DB、アップロード音声の保存先 |
| `DATABASE_URL` | SQLite接続先 |
| `LLM_PROVIDER` | `openai_compatible` または `mock` |
| `LLM_BASE_URL` | OpenAI互換ローカル推論サーバURL |
| `LLM_API_KEY` | OpenAI互換サーバ用APIキー。ローカルならダミー可 |
| `LLM_MODEL` | 例: `gemma-4-e4b`、将来は `gemma-4-31b` |
| `ASR_PROVIDER` | `whisper_cpp`、`faster_whisper`、`mock` |
| `ASR_MODEL_SIZE` | `tiny`、`base`、`small`、`medium`、`large` |
| `ASR_LANGUAGE` | 例: `ja` |
| `ASR_DEVICE` | 例: `cpu`、`cuda`、`mps` |
| `ASR_WHISPER_CPP_BINARY` | whisper.cpp CLIのパス |
| `ASR_MODEL_PATH` | Whisperモデルファイルのパス |

## 保存場所

既定では `LOCAL_SCHOOL_AI_DATA_DIR=./data` なので、このリポジトリでは以下に保存されます。

```text
~/Documents/engineering_design_2026/data/
  local_school_ai.db       SQLite DB。チャット履歴、議事録、資料メタデータ、chunk、FTS5索引を保存
  uploads/audio/           アップロードまたは録音した音声ファイルを保存
  originals/persistent/    永続資料の原本を collection_id / document_id ごとに保存
  originals/temporary/     一時文書の原本を session_id / document_id ごとに保存
  normalized/persistent/   正規化済み document.json と document.md を保存
  normalized/temporary/    一時文書の正規化済み document.json と document.md を保存
  chunks/persistent/       chunk JSONL を文書単位で保存
  chunks/temporary/        一時文書の chunk JSONL を文書単位で保存
  indexes/                 将来の索引ファイルやベクトル索引用の領域
```

音声ファイルは通常のファイルとして `data/uploads/audio/` に置かれます。永続資料の原本は削除せず `data/originals/persistent/{collection_id}/{document_id}/source.ext` に保持します。一時文書は `data/originals/temporary/{session_id}/{document_id}/source.ext` に保持します。正規化済み JSON / Markdown と chunk JSONL は別管理です。チャットセッション、メッセージ、raw transcript、整形済みテキスト、議事録案、資料メタデータ、FTS5索引は `data/local_school_ai.db` の各テーブルに保存されます。

## モデル切り替え

### LLM: Gemma 4 E4B

Gemma 4 E4B を OpenAI互換APIとしてローカル起動し、`.env` を次のようにします。

```env
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=http://localhost:8001/v1
LLM_API_KEY=local-dev-key
LLM_MODEL=gemma-4-e4b
```

アプリ本体は Gemma 固有SDKを直接呼びません。SGLang、vLLM、OpenAI-compatible local server などへ置き換える場合も、基本的には `LLM_BASE_URL` と `LLM_MODEL` の変更で対応します。

### 将来: Gemma 4 31B

推論サーバ側で Gemma 4 31B を提供し、以下だけ差し替えます。

```env
LLM_MODEL=gemma-4-31b
```

同時利用や本番寄りの運用では、FastAPIとは別プロセスの SGLang / vLLM などに分離してください。

### ASR: Whisper系

whisper.cpp を使う場合:

```env
ASR_PROVIDER=whisper_cpp
ASR_MODEL_SIZE=base
ASR_LANGUAGE=ja
ASR_DEVICE=cpu
ASR_WHISPER_CPP_BINARY=/path/to/whisper-cli
ASR_MODEL_PATH=/path/to/ggml-base.bin
```

モデルサイズを変える場合:

```env
ASR_MODEL_SIZE=small
ASR_MODEL_PATH=/path/to/ggml-small.bin
```

`faster-whisper` を試す場合は optional extra を入れます。

```bash
uv sync --extra dev --extra asr-faster-whisper
```

```env
ASR_PROVIDER=faster_whisper
ASR_MODEL_SIZE=small
ASR_DEVICE=cpu
```

## デモ手順

1. `.env` で `LLM_PROVIDER=mock`、`ASR_PROVIDER=mock` にする
2. `uv run uvicorn backend.main:app --reload --port 8000` で起動
3. `http://127.0.0.1:8000` を開く
4. 共通チャットを試す場合は `http://127.0.0.1:8000/chat/` を開く
5. チャット入力欄左側の `+` から一時文書を添付する
6. 資料投入を試す場合は `http://127.0.0.1:8000/documents/` を開く
7. 文書比較を試す場合は `http://127.0.0.1:8000/compare/` を開く
8. 処理済み文書を2件以上選択し、比較粒度を選んで「比較ジョブを作成」
9. 新規チャットでメッセージを送信し、履歴保存とLLM応答を確認
10. 議事録ツールを試す場合は `http://127.0.0.1:8000/` を開く
11. 面談名、実施日、参加者を入力
12. ブラウザ録音、または音声ファイルを選択
13. 「音声を登録」
14. 「文字起こし開始」
15. 「整形」
16. 要確認箇所が出た場合は「修正案を表示」で確認
17. 整形済みテキストを必要に応じて手動修正し、「修正を保存」
18. 「議事録生成」
19. raw transcript / 整形済みテキスト / 議事録案を確認

## 永続資料の投入

CLI と GUI/API は `backend/services/document_service.py` の共通パイプラインを使います。どちらも以下の順で処理します。

```text
original保存 -> normalize(JSON/Markdown) -> chunk(JSONL) -> SQLite FTS5 index
```

CLI:

```bash
school-ai ingest ./docs/handbooks --collection handbooks
```

`uv` 環境から実行する場合:

```bash
uv run school-ai ingest ./docs/handbooks --collection handbooks
```

ブラウザ:

```bash
open http://127.0.0.1:8000/documents/
```

APIで投入する場合:

```bash
curl -F "collection=handbooks" \
  -F "scope=persistent" \
  -F "files=@./docs/handbook.md" \
  -F "files=@./docs/rules.txt" \
  http://127.0.0.1:8000/api/documents/upload
```

サーバ上のパスを投入する管理用API:

```bash
curl -X POST http://127.0.0.1:8000/api/documents/ingest \
  -H "Content-Type: application/json" \
  -d '{"path":"./docs/handbook.md","collection":"handbooks","scope":"persistent","process":true}'
```

検索:

```bash
curl -X POST http://127.0.0.1:8000/api/documents/search \
  -H "Content-Type: application/json" \
  -d '{"query":"handbook","collection":"handbooks","limit":5}'
```

比較:

```bash
curl -X POST http://127.0.0.1:8000/api/compare/jobs \
  -H "Content-Type: application/json" \
  -d '{"document_ids":[1,2],"min_similarity":0.35,"limit":20,"granularity":"chunk"}'

curl http://127.0.0.1:8000/api/compare/jobs/1
```

## API

最低要件のAPI:

チャット:

- `POST /api/chat/sessions`
- `POST /api/chat/messages`
- `GET /api/chat/sessions`
- `GET /api/chat/sessions/{session_id}`
- `DELETE /api/chat/sessions/{session_id}`
- `POST /api/chat/sessions/{session_id}/messages`
- `GET /api/chat/sessions/{session_id}/messages`
- `GET /api/chat/tools`

資料:

- `POST /api/document-collections`
- `GET /api/document-collections`
- `POST /api/documents/upload`
- `POST /api/documents/ingest`
- `GET /api/documents`
- `GET /api/documents/{document_id}`
- `POST /api/documents/{document_id}/process`
- `POST /api/documents/search`

比較:

- `POST /api/compare/jobs`
- `GET /api/compare/jobs/{job_id}`

議事録:

- `POST /api/files/audio`
- `POST /api/jobs/transcription`
- `POST /api/jobs/cleanup`
- `POST /api/jobs/minutes`
- `GET /api/jobs/{job_id}`
- `GET /api/minutes/{minutes_id}`

追加API:

- `GET /api/transcripts/{transcript_id}`
- `GET /api/cleaned/{cleaned_id}`
- `PATCH /api/cleaned/{cleaned_id}`
- `POST /api/cleaned/{cleaned_id}/revision-suggestions`

## チャット基盤とツール境界

チャット基盤は `backend/services/chat_service.py` と `backend/orchestrator/chat_orchestrator.py` に分けています。

- `chat_service`: セッション、メッセージ保存、LLM応答生成のアプリケーションサービス
- `chat_orchestrator`: 会話履歴、システムプロンプト、ツール候補をまとめてLLMへ渡す層
- `tooling/registry.py`: `document_search_tool`、`document_read_tool`、`document_compare_tool`、`minutes_tool` の登録場所

資料投入・検索APIと文書比較APIは実装済みです。チャットからは一時文書を添付でき、ツール一覧と関連ツール候補も表示します。自動ツール実行は今後の接続点です。議事録はチャット本体へ統合せず、`/` の専用UIで動く独立ツールとして扱っています。

## テスト

モデル実体がなくても `mock` adapter で動きます。

```bash
uv run pytest
```

## 本実装へ移行する時の差し替えポイント

- LLM runtime  
  `backend/adapters/llm/openai_compatible.py` を中心に、SGLang / vLLM / 専用推論サーバへ接続します。アプリ層は `LLMAdapter` のみを見るため、Gemma 4 E4B から Gemma 4 31B への移行は設定変更を基本にできます。

- ASR runtime  
  `backend/adapters/asr/` に whisper.cpp / faster-whisper を分けています。精度や速度に応じて `ASR_PROVIDER` と `ASR_MODEL_SIZE` を変更します。

- Job基盤  
  今回は FastAPI `BackgroundTasks` + SQLite です。本実装では worker プロセス、キュー、リトライ、キャンセル、進捗率を追加してください。

- 認証・監査ログ  
  要件定義では認証、アクセス制御、監査ログが必要です。今回の来週デモ用モックでは未実装なので、本実装時に最優先で追加してください。

- 削除・保持期間  
  音声、文字起こし、議事録は `LOCAL_SCHOOL_AI_DATA_DIR` 配下に保存されます。削除API、保持期間、閲覧権限は本実装で強化してください。

- プロンプト管理  
  `backend/prompts/cleanup_prompt.md` と `backend/prompts/minutes_prompt.md` に分離済みです。学校ごとの議事録テンプレート追加はこの層で行えます。
