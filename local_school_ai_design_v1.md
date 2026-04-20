# 校内機密データ向けローカルAI支援基盤 設計書 v1

## 1. 文書の目的
本書は、`local_school_ai_requirements_v3.md` をもとに、校内機密データ向けローカルAI支援基盤の設計を具体化したものである。

本書では以下を定義する。

- 採用技術と選定理由
- 全体アーキテクチャ
- コンポーネント分割
- データ保存方針
- 文書処理パイプライン
- チャットおよび専用ツールの整合
- 議事録ツールの位置づけ
- 開発環境と本番環境の差分
- 今後の拡張点

---

## 2. 設計方針

### 2.1 中心はチャット基盤とする
本システムの利用体験の中心は、汎用的なチャットUIとする。

ただし、チャットUIは重い処理を直接担当せず、以下に責務を限定する。

- 会話履歴管理
- セッション管理
- ツール呼び出し
- 応答表示
- 添付文書との関連付け

### 2.2 重い処理は専用ツール・専用ランタイムへ分離する
以下の処理はチャット本体とは分離する。

- 議事録作成
- 文書正規化
- 文書チャンク化
- 複数文書比較
- ASR
- LLM推論

### 2.3 原本保存と内部表現統一を分ける
入力ファイルは形式が多様であるため、原本をそのまま保存しつつ、サーバ側で共通内部表現へ正規化する。

### 2.4 モデル・推論サーバは差し替え可能にする
アプリケーション本体は特定モデルや特定ランタイムに密結合しない。
すべて OpenAI 互換APIまたは抽象アダプタ経由で呼び出す。

### 2.5 CLI入口とGUI入口は共通パイプラインを使う
資料投入はCLIとGUIの両方を用意するが、内部では同一の取り込み処理を使う。

---

## 3. 採用技術選定

## 3.1 採用一覧
| レイヤ | 採用技術 | 役割 |
| --- | --- | --- |
| フロントエンド | Web UI（チャットUI + 専用ツールUI） | 操作入口 |
| API Gateway | FastAPI | 認証、セッション、ジョブ管理、ツール起動 |
| 開発用LLM実行環境 | Ollama | Mac上でのローカル推論 |
| 本番候補LLM実行環境 | SGLang | PGX上での同時利用に強い推論サーバ |
| ベースLLM | Gemma 4 31B | 主力モデル |
| 軽量モック用LLM | Gemma 4 E4B | Macやモック時の軽量構成 |
| ASR | faster-whisper | 音声文字起こし |
| 文書正規化 | Docling | 多形式文書の統一処理 |
| 全文検索 / 管理DB | SQLite + FTS5 | メタデータ管理、全文検索、ジョブ管理 |
| 意味検索 | Qdrant local | ベクトル検索 |
| 永続保存 | ローカルファイルストレージ | 原本・正規化文書・チャンク保存 |

---

## 3.2 採用理由

### FastAPI
- Python資産と相性がよい
- API設計が容易
- 将来のチャット基盤と専用ツールの両方を同一Gatewayに統合しやすい
- 非同期処理やジョブ管理の実装がしやすい

### Ollama
- Mac上でローカルモデルをすぐ動かせる
- 開発初期に扱いやすい
- OpenAI互換APIが使えるため、アプリ側の差し替えコストが低い

### SGLang
- 本番寄りの推論基盤候補として、同時利用への耐性を持たせやすい
- OpenAI互換APIに寄せられる
- Gemma系を含めたローカルLLM運用に向く

### Gemma 4 31B
- 本基盤の主対象である長文読解、資料参照、添削、比較支援に対応しやすい
- ローカル推論可能な範囲で高性能
- 要件上の信頼性・説明性に配慮しやすいベースモデル

### Gemma 4 E4B
- Mac上のモックや軽量デモで使いやすい
- 本実装では31Bへの置換を前提としつつ、初期実装の開発速度を確保できる

### faster-whisper
- Whisper系ASRの中で導入しやすく、速度とメモリ効率のバランスが良い
- モデルサイズ切り替えが容易
- モックから本実装まで同じ抽象インターフェースで扱いやすい

### Docling
- PDF, DOCX, PPTX, XLSX, HTML, Markdown, 画像等を広く扱える
- 内部の共通表現へ変換しやすい
- JSON / Markdown への書き出しがしやすく、RAGと比較支援の両方に向く

### SQLite + FTS5
- ローカル完結しやすい
- 設定が軽い
- ジョブ管理、メタデータ管理、全文検索の土台に向く

### Qdrant local
- ローカルで意味検索を実現しやすい
- ベクトル検索を後付けしやすい
- SQLiteベースの管理基盤を壊さず追加できる

---

## 3.3 代替候補と非採用理由

### vLLM
- 有力候補ではある
- ただし現時点では PGX 本番候補としては SGLang を第一候補とする
- 将来的な比較対象として残す

### TensorRT-LLM
- 高性能である可能性が高い
- ただし導入・運用難度が上がりやすいため、本設計の第一候補にはしない

### whisper.cpp
- ローカル性は非常に高い
- ただし現時点では faster-whisper の方が導入・速度面で扱いやすいため、標準採用はしない
- ASRアダプタで差し替え可能にしておく

### Apache Tika
- 多形式テキスト抽出の保険として有用
- ただし文書正規化の主軸は Docling とし、Tika は補助候補に留める

---

## 4. 全体アーキテクチャ

```text
[ Web UI / Chat UI / Minutes UI / Upload UI ]
                    |
                    v
             [ FastAPI API Gateway ]
                    |
      +-------------+-------------+----------------+
      |             |             |                |
      v             v             v                v
[ Chat Service ] [ Tool Router ] [ Job Manager ] [ Auth/Audit (future) ]
      |             |             |
      |             |             +----------------------+
      |             |                                    |
      v             v                                    v
[ LLM Adapter ] [ Document Services ]              [ Minutes Services ]
      |             |                                    |
      v             v                                    v
[ Ollama / SGLang ] [ Docling / Chunker / Index ] [ ASR / Cleanup / Minutes ]
                    |                                    |
                    +----------------+-------------------+
                                     |
                                     v
                    [ File Store / SQLite / FTS5 / Qdrant ]
```

---

## 5. コンポーネント設計

## 5.1 Frontend
### 役割
- チャットUI
- 資料アップロードUI
- 一時文書アップロードUI
- 比較ツール起動UI
- 議事録専用UI

### ポイント
- 中心はチャットUI
- 議事録は専用画面または専用モーダルで起動
- 添付文書はチャットセッションに紐づける

---

## 5.2 API Gateway
### 役割
- 認証（将来）
- セッション管理
- ジョブ管理
- ファイル受付
- ツール呼び出し振り分け
- レスポンス統一

### 方針
- 重い処理は直接実行しない
- 長い処理はジョブ化する
- LLM / ASR / 文書処理は下位サービスへ委譲する

---

## 5.3 Chat Service
### 役割
- 会話履歴の保持
- 利用可能ツールの判断
- 文書参照、文書読解、文書比較、議事録呼び出しの入口

### 注意
- Chat Service 自体は文書変換や比較を行わない
- すべて Tool Router 経由で下位サービスへ依頼する

---

## 5.4 Tool Router
### 役割
- チャットからの要求を適切なツールへルーティングする

### 主要ツール
- Document Search Tool
- Document Read Tool
- Document Compare Tool
- Minutes Tool

### 設計方針
- 「検索」「読解」「比較」を別ツールとして分離する
- 曖昧な万能ツールは作らない

---

## 5.5 LLM Runtime
### 開発構成
- Ollama
- モデル: Gemma 4 E4B

### 本番候補
- SGLang
- モデル: Gemma 4 31B

### アダプタ設計
以下を環境変数ベースで差し替え可能とする。

- `LLM_PROVIDER`
- `LLM_BASE_URL`
- `LLM_API_KEY`
- `LLM_MODEL`

---

## 5.6 ASR Runtime
### 標準採用
- faster-whisper

### 役割
- 音声ファイルから raw transcript を生成する

### アダプタ設計
以下を差し替え可能とする。

- `ASR_PROVIDER`
- `ASR_MODEL_SIZE`
- `ASR_LANGUAGE`
- `ASR_DEVICE`

---

## 5.7 Document Pipeline
### 役割
- 原本保存
- 正規化
- Markdown / JSON 生成
- チャンク化
- 索引化

### 処理段階
1. ingest
2. normalize
3. chunk
4. index

### 共通化方針
CLI投入とGUI投入は入口のみ異なり、内部では同一パイプラインを使用する。

---

## 5.8 Data Store
### 保存対象
- 原本ファイル
- 正規化済み JSON
- 正規化済み Markdown
- チャンク JSONL
- セッション情報
- ジョブ状態
- チャット履歴
- 議事録生成物

### 採用方針
- 原本はローカルファイルとして保持
- メタデータとジョブ状態は SQLite に格納
- 全文検索は FTS5
- 意味検索は Qdrant local

---

## 6. データ保存構造

```text
data/
  originals/
    persistent/{collection_id}/{doc_id}/source.ext
    temporary/{session_id}/{doc_id}/source.ext
    audio/{session_id}/{audio_id}/source.ext
  normalized/
    persistent/{collection_id}/{doc_id}/document.json
    persistent/{collection_id}/{doc_id}/document.md
    temporary/{session_id}/{doc_id}/document.json
    temporary/{session_id}/{doc_id}/document.md
  chunks/
    persistent/{collection_id}/{doc_id}.jsonl
    temporary/{session_id}/{doc_id}.jsonl
  generated/
    minutes/{session_id}/{minutes_id}.md
    cleaned/{session_id}/{cleaned_id}.txt
    transcripts/{session_id}/{transcript_id}.txt
  db/
    app.db
  vector/
    qdrant/
```

### ポイント
- 永続資料と一時資料を明確に分離する
- 音声データは専用領域に置く
- 議事録関連の中間生成物も保存する
- 将来的な削除ポリシー実装を前提とする

---

## 7. 文書取り込み設計

## 7.1 CLI投入
### 想定用途
- 学内資料の一括登録
- 年度更新資料の差し替え
- 管理者による保守運用

### 例
```bash
school-ai ingest /srv/school-ai/dropbox/handbooks --collection handbooks
school-ai ingest /srv/school-ai/dropbox/rules --collection rules
```

### 処理
- ディレクトリ走査
- Docling 変換
- Markdown / JSON 保存
- チャンク化
- FTS5 / Qdrant 登録

---

## 7.2 GUI投入
### 想定用途
- 教員による日常追加
- 論文・レポート・提出物のその場アップロード
- 比較対象ファイル投入

### UI要件
- 単一ファイル / 複数ファイルアップロード
- 永続資料として登録するか、一時資料として扱うか選択可能
- 処理状況表示
- 失敗ファイル表示

---

## 8. チャットと文書の整合設計

## 8.1 永続文書
### 用途
- 学内資料参照
- 規程確認
- FAQ回答下書き

### チャットからの扱い
- Document Search Tool で候補検索
- Document Read Tool で該当部分精読
- 参照箇所を引用しながら回答生成

---

## 8.2 一時文書
### 用途
- 論文読解
- レポート添削
- 提出物確認
- その場限りの文書解析

### チャットからの扱い
- セッション添付文書として一覧化
- Document Read Tool で内容参照
- 必要に応じて比較ツールへ引き渡し

---

## 8.3 複数文書参照
### 必要性
- レポートA/B比較
- 版差確認
- 流用疑い箇所確認
- 複数資料の横断参照

### 方針
- セッションに複数文書を紐付け可能とする
- 比較対象は2件以上選択可能とする
- 検索・読解・比較は別ツールに分離する

---

## 9. 議事録ツール設計

## 9.1 位置づけ
議事録ツールは専用ワークフローを持つ独立ツールとする。
ただし、チャットUIのツールメニューから起動できるようにする。

### 理由
- 音声入力を起点とする
- ASR → cleanup → minutes の多段処理が必要
- 通常チャットとはUI要件が異なる
- 長時間ジョブ化しやすい

---

## 9.2 処理フロー
1. 面談情報入力
2. 録音または音声アップロード
3. ASR による raw transcript 生成
4. Cleanup LLM による整形
5. Minutes LLM による議事録生成
6. raw / cleaned / minutes の比較表示
7. 必要ならチャットへ結果を渡す

---

## 9.3 出力形式
- 面談名
- 実施日
- 参加者
- 主な相談内容
- 決定事項
- 今後の対応
- 注意事項
- 自由記述

---

## 10. 文書比較ツール設計

## 10.1 目的
- 丸写し・流用確認
- 版差確認
- 類似段落抽出
- 共通箇所の可視化

## 10.2 入力
- 2件以上の文書
- 比較粒度（全文 / 節 / 段落 / チャンク）

## 10.3 出力
- 差分サマリ
- 類似箇所一覧
- 類似率の参考指標
- 並列比較表示用の構造化結果

## 10.4 実装方針
- 初期はチャンク単位の類似比較から始める
- 将来的により高度な類似判定へ拡張可能にする

---

## 11. API / ツール境界

## 11.1 外部向け主要API
### チャット関連
- `POST /api/chat/sessions`
- `POST /api/chat/messages`
- `GET /api/chat/sessions/{session_id}`

### 文書関連
- `POST /api/documents/upload`
- `POST /api/documents/ingest`
- `GET /api/documents/{doc_id}`
- `POST /api/documents/search`

### 比較関連
- `POST /api/compare/jobs`
- `GET /api/compare/jobs/{job_id}`

### 議事録関連
- `POST /api/files/audio`
- `POST /api/jobs/transcription`
- `POST /api/jobs/cleanup`
- `POST /api/jobs/minutes`
- `GET /api/jobs/{job_id}`
- `GET /api/minutes/{minutes_id}`

---

## 11.2 内部ツール境界
- `document_search_tool`
- `document_read_tool`
- `document_compare_tool`
- `minutes_tool`

### 分離理由
- 検索と読解は責務が異なる
- 比較は単体文書処理と別ロジックが必要
- 議事録は音声起点の専用処理である

---

## 12. 非機能設計

## 12.1 セキュリティ
- 入力データを外部クラウドへ送信しない
- ローカルまたは閉域環境で運用する
- 永続資料と一時資料で削除ポリシーを分ける
- 将来的に認証・権限管理・監査ログを導入する

## 12.2 同時利用
- API Gateway と推論基盤を分離する
- 重い処理はジョブ化する
- チャット応答とバッチ処理を分離する
- PGX 本番環境では SGLang 等の専用推論基盤を使う

## 12.3 拡張性
- LLM差し替えを環境変数・アダプタで吸収する
- ASR差し替えをアダプタで吸収する
- 文書変換器の差し替え余地を残す
- 議事録ツールは独立性を保ちつつチャットから呼べるようにする

## 12.4 保守性
- CLI/GUI の内部パイプラインを共通化する
- ツール責務を分離する
- 原本と中間生成物を明確に分けて保存する

---

## 13. 開発環境と本番環境

## 13.1 開発環境（ローカルMac）
### 目的
- 画面・API・パイプラインの動作確認
- モック作成
- 軽量な文書処理確認

### 構成
- FastAPI
- Ollama
- Gemma 4 E4B
- faster-whisper
- SQLite
- ローカルファイル保存

---

## 13.2 本番候補環境（Lenovo ThinkStation PGX）
### 目的
- Gemma 4 31B の実運用
- 複数同時利用
- 長文読解、比較、資料参照の強化

### 構成
- FastAPI API Gateway
- SGLang
- Gemma 4 31B
- faster-whisper
- Docling
- SQLite + FTS5 + Qdrant local
- ローカルストレージ

---

## 14. 段階的実装方針

### Phase 1
- 議事録専用モック
- 音声アップロード / ASR / cleanup / minutes
- 独立ツールとして成立させる

### Phase 2
- 共通チャットUI
- 永続資料投入CLI
- 永続資料検索・読解

### Phase 3
- 一時文書アップロード
- 添削支援
- 複数文書参照

### Phase 4
- 文書比較ツール
- 類似箇所抽出
- 版差比較

### Phase 5
- 認証
- 監査ログ
- データ削除ポリシー
- 同時利用最適化

---

## 15. まとめ
本設計では、校内機密データを安全に扱うため、チャット基盤を中心にしつつ、文書基盤と専用ツール群を分離して設計する。

議事録機能は専用ツールとして独立させるが、チャットから起動可能にすることで全体UXの統一を図る。
資料参照、論文・レポート読解、複数文書比較は、共通文書基盤とツール群によって実現する。

また、開発環境では Mac + Ollama + Gemma 4 E4B を用い、本番候補では PGX + SGLang + Gemma 4 31B を前提とすることで、短期の試作と中長期の運用を両立する。
