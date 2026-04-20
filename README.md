# Local School AI Minutes Mock

校内機密データ向けローカルAI支援基盤のうち、**議事録作成支援機能のみ**を切り出した最小実装です。

`local_school_ai_requirements_v2.md` の Phase 1 に合わせ、音声アップロードまたはブラウザ録音から、raw transcript、整形済みテキスト、議事録案をジョブ処理で生成します。機微データを外部クラウドへ送る前提にはしていません。

## 今回の構成

- Backend: FastAPI
- Frontend: FastAPI配信の薄いHTML/CSS/JavaScript
- DB: SQLite
- Job: SQLite上の `queued / running / completed / failed`
- LLM: OpenAI-compatible adapter
- ASR: Whisper系 adapter
- デモ用: `mock` LLM / `mock` ASR

主なディレクトリ:

```text
backend/
  api/            FastAPI routers
  services/       transcription / cleanup / minutes services
  adapters/
    llm/          LLM adapter protocol and implementations
    asr/          ASR adapter protocol and implementations
  models/         SQLAlchemy DB models and Pydantic schemas
  repositories/   SQLite persistence and file storage
  workers/        simple job runner
  prompts/        cleanup and minutes prompts
frontend/         browser UI
tests/            smoke and adapter tests
```

## 起動手順

Python 3.11以上を想定しています。

```bash
cd ~/Documents/engineering_design_2026
uv sync --extra dev
cp .env.example .env
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
open http://127.0.0.1:8000
```

`uv` を使わない場合:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn backend.main:app --reload --port 8000
```

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
  local_school_ai.db       SQLite DB。文字起こし、整形済みテキスト、議事録案、ジョブ状態、メタ情報を保存
  uploads/audio/           アップロードまたは録音した音声ファイルを保存
```

音声ファイルは通常のファイルとして `data/uploads/audio/` に置かれます。raw transcript、整形済みテキスト、議事録案は個別の `.txt` ファイルではなく、`data/local_school_ai.db` の各テーブルに保存されます。

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
4. 面談名、実施日、参加者を入力
5. ブラウザ録音、または音声ファイルを選択
6. 「音声を登録」
7. 「文字起こし開始」
8. 「整形」
9. 要確認箇所が出た場合は「修正案を表示」で確認
10. 整形済みテキストを必要に応じて手動修正し、「修正を保存」
11. 「議事録生成」
12. raw transcript / 整形済みテキスト / 議事録案を確認

## API

最低要件のAPI:

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
