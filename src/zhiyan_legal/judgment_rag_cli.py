"""CLI for the official Judicial Yuan judgment vector index."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from pathlib import Path
import stat
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse

from dotenv import find_dotenv, load_dotenv

from .judgment_rag import (
    DEFAULT_MANIFEST_PATH,
    DEFAULT_QDRANT_PATH,
    OFFICIAL_API_BASE,
    JudgmentRagError,
    client_from_env,
    index_from_env,
)


def _load_project_env(start: Path | None = None) -> Path | None:
    """Load the nearest project .env without overriding deployment secrets."""

    if start is None:
        discovered = find_dotenv(filename=".env", usecwd=True)
        env_path = Path(discovered) if discovered else None
    else:
        current = start.resolve()
        if current.is_file():
            current = current.parent
        env_path = None
        for directory in (current, *current.parents):
            candidate = directory / ".env"
            if candidate.is_file():
                env_path = candidate
                break
    if env_path is None:
        return None
    load_dotenv(env_path, override=False)
    return env_path.resolve()


def _deployment_preflight(
    env: Mapping[str, str],
    *,
    env_path: Path | None,
    require_server: bool,
) -> dict[str, Any]:
    """Validate deployment inputs without opening Qdrant or printing secrets."""

    blockers: list[str] = []
    warnings: list[str] = []

    def value(name: str, default: str = "") -> str:
        return str(env.get(name, default) or "").strip()

    credentials = {
        "JUDICIAL_API_USER": bool(value("JUDICIAL_API_USER")),
        "JUDICIAL_API_PASSWORD": bool(value("JUDICIAL_API_PASSWORD")),
    }
    for name, present in credentials.items():
        if not present:
            blockers.append(f"{name} 尚未安全提供")

    base_url = value("JUDICIAL_API_BASE_URL", OFFICIAL_API_BASE).rstrip("/")
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        blockers.append("JUDICIAL_API_BASE_URL 不是有效的 HTTP(S) URL")
    elif parsed.scheme != "https":
        warnings.append("JUDICIAL_API_BASE_URL 未使用 HTTPS；只應用於受控內網 proxy")

    numeric_rules = {
        "JUDICIAL_API_TIMEOUT": (value("JUDICIAL_API_TIMEOUT", "60"), 1),
        "JUDGMENT_QDRANT_PORT": (value("JUDGMENT_QDRANT_PORT", "6333"), 1),
        "JUDGMENT_CHUNK_MAX_CHARS": (value("JUDGMENT_CHUNK_MAX_CHARS", "800"), 1),
        "JUDGMENT_CHUNK_OVERLAP": (value("JUDGMENT_CHUNK_OVERLAP", "80"), 0),
        "JUDGMENT_EMBED_BATCH_SIZE": (value("JUDGMENT_EMBED_BATCH_SIZE", "32"), 1),
    }
    parsed_numbers: dict[str, int | float] = {}
    for name, (raw, minimum) in numeric_rules.items():
        try:
            number: int | float = float(raw) if name == "JUDICIAL_API_TIMEOUT" else int(raw)
        except ValueError:
            blockers.append(f"{name} 必須是數字")
            continue
        if number < minimum:
            blockers.append(f"{name} 必須大於或等於 {minimum}")
        parsed_numbers[name] = number
    if (
        "JUDGMENT_CHUNK_MAX_CHARS" in parsed_numbers
        and "JUDGMENT_CHUNK_OVERLAP" in parsed_numbers
        and parsed_numbers["JUDGMENT_CHUNK_OVERLAP"]
        >= parsed_numbers["JUDGMENT_CHUNK_MAX_CHARS"]
    ):
        blockers.append("JUDGMENT_CHUNK_OVERLAP 必須小於 JUDGMENT_CHUNK_MAX_CHARS")

    manifest_path = Path(value("JUDGMENT_MANIFEST_PATH", DEFAULT_MANIFEST_PATH))
    manifest_parent = manifest_path.parent
    if manifest_parent.exists() and not os.access(manifest_parent, os.W_OK):
        blockers.append("JUDGMENT_MANIFEST_PATH 的上層目錄不可寫入")
    elif not manifest_parent.exists():
        warnings.append("manifest 上層目錄尚未建立；首次啟動時必須可建立")

    qdrant_path = value("JUDGMENT_QDRANT_PATH", DEFAULT_QDRANT_PATH)
    qdrant_host = value("JUDGMENT_QDRANT_HOST")
    mode = "server" if not qdrant_path else "local"
    revision_pinned = bool(value("JUDGMENT_EMBED_MODEL_REVISION"))
    if require_server:
        if mode != "server":
            blockers.append("Server 部署必須清空 JUDGMENT_QDRANT_PATH")
        if not qdrant_host:
            blockers.append("Server 部署必須設定 JUDGMENT_QDRANT_HOST")
        if not manifest_path.is_absolute():
            blockers.append("Server 部署的 JUDGMENT_MANIFEST_PATH 必須是絕對路徑")
        if not revision_pinned:
            blockers.append("正式部署必須固定 JUDGMENT_EMBED_MODEL_REVISION")
    elif not revision_pinned:
        warnings.append("尚未固定 JUDGMENT_EMBED_MODEL_REVISION；正式部署前必須補上")

    env_file: dict[str, Any] = {"found": env_path is not None}
    if env_path is not None:
        mode_bits = stat.S_IMODE(env_path.stat().st_mode)
        env_file.update({"path": str(env_path), "mode": oct(mode_bits)})
        if mode_bits & 0o077:
            blockers.append(".env 權限過寬；請執行 chmod 600 .env")

    return {
        "status": "ready" if not blockers else "blocked",
        "require_server": require_server,
        "credentials_present": credentials,
        "env_file": env_file,
        "qdrant_mode": mode,
        "qdrant_host_configured": bool(qdrant_host),
        "manifest_path": str(manifest_path),
        "embedding_revision_pinned": revision_pinned,
        "blockers": blockers,
        "warnings": warnings,
    }


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
    preflight = sub.add_parser("preflight", help="不連線、不顯示帳密，檢查部署設定")
    preflight.add_argument(
        "--require-server",
        action="store_true",
        help="要求 Qdrant Server、絕對 manifest 路徑與固定模型 revision",
    )
    sub.add_parser(
        "rebuild-index",
        help="設定變更後，把 manifest 中的 active 判決重建到新的空 collection",
    )
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
    env_path = _load_project_env()
    args = _parser().parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s | %(name)s | %(message)s",
    )
    if args.command == "preflight":
        report = _deployment_preflight(
            os.environ,
            env_path=env_path,
            require_server=args.require_server,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if report["status"] != "ready":
            raise SystemExit(2)
        return
    try:
        index = index_from_env(allow_rebuild=args.command == "rebuild-index")
        try:
            if args.command == "status":
                print(json.dumps(index.status(), ensure_ascii=False, indent=2))
                return
            if args.command == "rebuild-index":
                print(json.dumps(index.rebuild_index(), ensure_ascii=False, indent=2))
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
