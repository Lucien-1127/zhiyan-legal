#!/usr/bin/env python3
"""資料庫健康檢查 — 一鍵掃描 zhiyan-legal 所有資料庫層的健康狀態"""

import os
import sys
import sqlite3
import json
import tempfile
from pathlib import Path
from datetime import datetime

REPORTS_DIR = Path(__file__).resolve().parent.parent / "results"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

def check_sqlite(db_path: str, label: str) -> dict:
    """Run full integrity check on a SQLite database."""
    result = {
        "db": label,
        "path": db_path,
        "exists": False,
        "size_bytes": 0,
        "size_mb": 0,
        "integrity": "N/A",
        "quick_check": "N/A",
        "table_count": 0,
        "tables": [],
        "row_counts": {},
        "errors": [],
    }
    path = Path(db_path)
    if not path.exists():
        result["errors"].append(f"檔案不存在: {db_path}")
        return result

    result["exists"] = True
    result["size_bytes"] = path.stat().st_size
    result["size_mb"] = round(path.stat().st_size / (1024 * 1024), 2)

    try:
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode=WAL;")

        # Integrity check
        cur = conn.execute("PRAGMA integrity_check;")
        integrity_rows = cur.fetchall()
        result["integrity"] = "ok" if integrity_rows == [("ok",)] else [r[0] for r in integrity_rows]

        # Quick check
        cur = conn.execute("PRAGMA quick_check;")
        quick = cur.fetchone()
        result["quick_check"] = quick[0] if quick else "N/A"

        # Foreign key check
        cur = conn.execute("PRAGMA foreign_key_check;")
        fk_issues = cur.fetchall()
        result["foreign_key_issues"] = len(fk_issues)

        # Tables & row counts
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
        )
        tables = [r[0] for r in cur.fetchall()]
        result["tables"] = tables
        result["table_count"] = len(tables)

        for tbl in tables:
            try:
                cur = conn.execute(f"SELECT COUNT(*) FROM \"{tbl}\";")
                result["row_counts"][tbl] = cur.fetchone()[0]
            except Exception as e:
                result["row_counts"][tbl] = f"ERROR: {e}"

        # Schema version / pragma info
        cur = conn.execute("PRAGMA schema_version;")
        result["schema_version"] = cur.fetchone()[0]
        cur = conn.execute("PRAGMA page_count;")
        result["page_count"] = cur.fetchone()[0]
        cur = conn.execute("PRAGMA page_size;")
        result["page_size"] = cur.fetchone()[0]

        conn.close()
    except Exception as e:
        result["errors"].append(str(e))

    return result


def check_mcp_database() -> dict:
    """Check mcp-taiwan-legal-db CacheDB availability."""
    result = {
        "db": "mcp-taiwan-legal-db (CacheDB)",
        "package_installed": False,
        "version": None,
        "cache_db_exists": False,
        "cache_db_path": None,
        "cache_db_health": None,
        "errors": [],
    }
    try:
        import mcp_server
        result["package_installed"] = True
        result["version"] = getattr(mcp_server, "__version__", "unknown")
    except ImportError:
        result["errors"].append("mcp-server 套件未安裝 (pip install mcp-taiwan-legal-db)")
        return result

    cache_path = Path(tempfile.gettempdir()) / "zhiyan_legal_cache.db"
    result["cache_db_path"] = str(cache_path)

    if cache_path.exists():
        result["cache_db_exists"] = True
        check = check_sqlite(str(cache_path), "mcp-cache-cache")
        result["cache_db_health"] = check
    else:
        result["errors"].append("CacheDB 尚未建立（需首次呼叫 judicial_api 才會建立）")

    return result


def check_fulltext_search(db_path: str) -> dict:
    """Check if FTS5 tables exist and are populated."""
    result = {"fts5_tables": [], "fts5_errors": []}
    if not Path(db_path).exists():
        return result

    try:
        conn = sqlite3.connect(db_path)
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND sql LIKE '%fts%' ORDER BY name;"
        )
        for r in cur.fetchall():
            result["fts5_tables"].append(r[0])

        for tbl in result["fts5_tables"]:
            try:
                cur = conn.execute(f"SELECT COUNT(*) FROM \"{tbl}\";")
                result[f"{tbl}_rows"] = cur.fetchone()[0]
            except Exception as e:
                result["fts5_errors"].append(f"{tbl}: {e}")

        conn.close()
    except Exception as e:
        result["fts5_errors"].append(str(e))

    return result


def main():
    print("=" * 60)
    print("  🔍 zhiyan-legal 資料庫健康檢查")
    print(f"  時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # ── 1. regulation_tracker.db ──
    regulation_db = Path.cwd() / "regulation_tracker.db"
    if not regulation_db.exists():
        # 也可能在專案根目錄之外
        regulation_db = Path.home() / ".zhiyan" / "regulation_tracker.db"
    if not regulation_db.exists():
        regulation_db = Path(tempfile.gettempdir()) / "regulation_tracker.db"

    r1 = check_sqlite(str(regulation_db), "regulation_tracker.db")
    print(f"\n📁 [{r1['db']}] {'✅' if r1['exists'] else '⬜'}  "
          f"大小={r1['size_mb']}MB  "
          f"完整性={r1['integrity']}  "
          f"表格={r1['table_count']}")

    if r1["exists"]:
        fts1 = check_fulltext_search(str(regulation_db))
        if fts1["fts5_tables"]:
            print(f"   📝 FTS5 全文檢索引擎: {', '.join(fts1['fts5_tables'])}")
        for tbl, cnt in r1["row_counts"].items():
            print(f"     - {tbl}: {cnt} 行")
        if r1["foreign_key_issues"]:
            print(f"   ⚠️  外部鍵異常: {r1['foreign_key_issues']} 筆")
        if r1["errors"]:
            print(f"   ❌ 錯誤: {r1['errors']}")

    # ── 2. mcp-taiwan-legal-db CacheDB ──
    r2 = check_mcp_database()
    print(f"\n📁 [{r2['db']}] {'✅' if r2['package_installed'] else '⬜'}  "
          f"已安裝={'是' if r2['package_installed'] else '否'}")
    if r2["package_installed"]:
        print(f"   📦 版本: {r2['version']}")
        if r2["cache_db_exists"]:
            c = r2["cache_db_health"]
            print(f"   🗄️  快取 DB: {r2['cache_db_path']}")
            print(f"      大小={c['size_mb']}MB  完整性={c['integrity']}  表格={c['table_count']}")
            for tbl, cnt in c["row_counts"].items():
                print(f"      - {tbl}: {cnt} 行")
        else:
            print(f"   💡 快取 DB 尚未建立（等待首次 judicial_api 呼叫）")

    # ── 3. 所有測試中的資料庫相關測試 ──
    print(f"\n🧪 資料庫相關測試狀態")
    test_files = []
    for root, dirs, files in os.walk(Path.cwd() / "tests"):
        for f in files:
            if f.endswith(".py"):
                test_files.append(Path(root) / f)

    db_test_files = {
        "test_judicial_api.py": "司法 API（含 CacheDB）",
        "test_runner.py": "Runner（含 validate）",
    }
    for fname, desc in db_test_files.items():
        fpath = Path.cwd() / "tests" / fname
        exists = fpath.exists()
        print(f"   {'✅' if exists else '⬜'} {desc} ({fname})")

    # ── 4. Summary ──
    print(f"\n{'=' * 60}")
    r1_ok = not r1.get("errors") or not r1["exists"]
    r2_ok = not r2.get("errors") or not r2["package_installed"]
    status = "🟢 全部正常" if (r1_ok and r2_ok) else "🟡 有注意事項"
    print(f"  {status}")
    print(f"{'=' * 60}")

    # Save report
    report = {
        "timestamp": datetime.now().isoformat(),
        "regulation_db": r1,
        "mcp_cache_db": r2,
        "fulltext_search": fts1 if r1["exists"] else {},
        "overall_status": status,
    }
    report_path = REPORTS_DIR / "db_health_check.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n📄 報告已儲存: {report_path}")

    # Exit code
    if r1.get("errors") and r1["exists"]:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
