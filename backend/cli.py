from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from backend.repositories.database import init_db, session_scope
from backend.services.document_service import DocumentService


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="school-ai")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest", help="永続資料を取り込み、正規化・チャンク化・索引化します。")
    ingest_parser.add_argument("path", help="取り込み対象のファイルまたはディレクトリ")
    ingest_parser.add_argument("--collection", required=True, help="登録先コレクション名")
    ingest_parser.add_argument("--no-process", action="store_true", help="原本保存のみ行い、処理は後で実行します。")
    ingest_parser.add_argument("--json", action="store_true", help="結果をJSONで出力します。")

    args = parser.parse_args(argv)
    if args.command == "ingest":
        return _run_ingest(args)
    parser.error(f"unknown command: {args.command}")
    return 2


def _run_ingest(args: argparse.Namespace) -> int:
    init_db()
    db = session_scope()
    try:
        result = DocumentService(db).ingest_path(
            Path(args.path),
            collection_name=args.collection,
            process=not args.no_process,
        )
        payload = {
            "collection": {
                "id": result.collection.id,
                "name": result.collection.name,
            },
            "documents": [
                {
                    "id": document.id,
                    "filename": document.original_filename,
                    "status": document.status,
                    "normalized_markdown_path": document.normalized_markdown_path,
                    "chunks_path": document.chunks_path,
                    "error_message": document.error_message,
                }
                for document in result.documents
            ],
            "failures": [
                {
                    "filename": failure.filename,
                    "document_id": failure.document_id,
                    "error_message": failure.error_message,
                }
                for failure in result.failures
            ],
        }
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            _print_ingest_summary(payload)
        return 1 if result.failures else 0
    finally:
        db.close()


def _print_ingest_summary(payload: dict) -> None:
    collection = payload["collection"]
    documents = payload["documents"]
    failures = payload["failures"]
    print(f"collection: {collection['name']} (id={collection['id']})")
    print(f"documents: {len(documents)}")
    for document in documents:
        line = f"- #{document['id']} {document['filename']}: {document['status']}"
        if document["error_message"]:
            line += f" ({document['error_message']})"
        print(line)
    if failures:
        print("failures:")
        for failure in failures:
            print(f"- {failure['filename']}: {failure['error_message']}")


if __name__ == "__main__":
    sys.exit(main())
