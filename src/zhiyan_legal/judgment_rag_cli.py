"""CLI for the official Judicial Yuan judgment vector index."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path

from .judgment_rag import JudgmentRagError, client_from_env, index_from_env


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="司法院判決書同步、索引與本地向量查詢",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "環境變數：JUDICIAL_API_USER、JUDICIAL_API_PASSWORD、"
            "JUDGMENT_MANIFEST_PATH、JUDGMENT_QDRANT_PATH、JUDGMENT_EMBED_MODEL\n"
            "注意：司法院 JList 僅提供官方規格所述的近期異動；歷史 bootstrap 請先整理成 JDoc JSONL。"
        ),
    )
    parser.add_argument("--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="顯示本地 manifest 與 Qdrant 狀態")
    sub.add_parser("sync-changes", help="取得官方異動清單並同步判決全文")

    sync = sub.add_parser("sync-jids", help="依 JID 檔案同步判決全文")
    sync.add_argument("jids_file", type=Path, help="一行一個 JID 的文字檔")

    import_jsonl = sub.add_parser("import-jsonl", help="匯入 JDoc JSONL，適合歷史批次 bootstrap")
    import_jsonl.add_argument("jsonl_file", type=Path)

    search = sub.add_parser("search", help="查詢本地判決向量庫")
    search.add_argument("query")
    search.add_argument("--top-k", type=int, default=8)
    search.add_argument("--jid", default="")
    search.add_argument("--year", default="")
    return parser


def main() -> None:
    args = _parser().parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s | %(name)s | %(message)s",
    )
    try:
        index = index_from_env()
        try:
            if args.command == "status":
                print(json.dumps(index.status(), ensure_ascii=False, indent=2))
                return
            if args.command == "search":
                results = index.search(args.query, top_k=args.top_k, jid=args.jid, year=args.year)
                print(json.dumps(results, ensure_ascii=False, indent=2))
                return
            if args.command == "import-jsonl":
                print(json.dumps(index.import_jsonl(str(args.jsonl_file)), ensure_ascii=False, indent=2))
                return

            client = client_from_env()
            if args.command == "sync-changes":
                result = asyncio.run(index.sync_changes(client))
            else:
                jids = [line.strip() for line in args.jids_file.read_text(encoding="utf-8").splitlines()]
                result = asyncio.run(index.sync_jids(client, jids))
            print(json.dumps(result, ensure_ascii=False, indent=2))
        finally:
            index.close()
    except (JudgmentRagError, FileNotFoundError, ValueError) as exc:
        raise SystemExit(f"錯誤：{exc}") from exc


if __name__ == "__main__":
    main()
