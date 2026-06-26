"""
regulation_api — FastAPI REST 後端

用法：
    uvicorn src.zhiyan_legal.regulation_api:app --host 127.0.0.1 --port 7850 --reload

    # 或直接執行（等同上述）
    python -m src.zhiyan_legal.regulation_api
"""

import json
import logging
import os
import sys
import re
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

# ── 專案路徑 ──────────────────────────────────
_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SRC_DIR = os.path.join(_PROJECT_DIR, "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from zhiyan_legal.regulation_tracker import RegulationTracker
from zhiyan_legal.regulation_diff import build_diff_report, export_word

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("regulation_api")

app = FastAPI(
    title="法規異動監控 API",
    description="全國法規資料庫異動偵測與新舊條文對照後端",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 全域 tracker 實例 ────────────────────────
_tracker: Optional[RegulationTracker] = None


def get_tracker() -> RegulationTracker:
    global _tracker
    if _tracker is None:
        _tracker = RegulationTracker()
    return _tracker


# ═════════════════════════════════════════════
# API 端點
# ═════════════════════════════════════════════

@app.get("/api/status")
def api_status():
    """系統整體狀態"""
    tracker = get_tracker()
    s = tracker.status_summary()
    return {
        "ok": True,
        "index_size": s["index_size"],
        "tracked_count": s["total_tracked"],
        "changed_recent_7d": s["changed_recent_7d"],
        "last_sync": s.get("last_sync"),
        "tracked": s["tracked_list"],
    }


@app.post("/api/sync")
def api_sync(force: bool = Query(False)):
    """手動同步法規索引"""
    tracker = get_tracker()
    try:
        ok = tracker.sync_index(force=force)
        return {"ok": True, "downloaded": ok, "message": "同步完成" if ok else "索引已是今日最新"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/check")
def api_check(official: bool = Query(True)):
    """執行查核所有追蹤法規"""
    tracker = get_tracker()
    tracker.sync_index(force=False)
    results = tracker.check_all(official=official)
    changed = [r for r in results if r.get("changed")]
    new = [r for r in results if r.get("status") == "newly_tracked"]
    errors = [r for r in results if r.get("status") == "error"]
    return {
        "ok": True,
        "checked": len(results),
        "changed": len(changed),
        "newly_tracked": len(new),
        "errors": len(errors),
        "results": [
            {
                "pcode": r["pcode"],
                "name": r["name"],
                "status": r["status"],
                "old_version": r.get("old_version"),
                "new_version": r.get("new_version"),
                "changed": r.get("changed", False),
            }
            for r in results
        ],
    }


@app.get("/api/tracked")
def api_tracked():
    """列出所有追蹤法規"""
    tracker = get_tracker()
    rows = tracker.get_all_tracked()
    out = []
    for r in rows:
        meta = tracker.law_meta(r["pcode"])
        out.append({
            "pcode": r["pcode"],
            "name": r["name"],
            "level": r.get("level", meta.get("level", "") if meta else ""),
            "baseline_version": r.get("baseline_version", ""),
            "baseline_date": r.get("baseline_date", ""),
            "frequency_days": r.get("frequency_days", 7),
            "last_checked_at": r.get("last_checked_at", ""),
            "abolished": meta.get("abolished", False) if meta else False,
            "current_version": meta.get("modifiedDate", "") if meta else "",
        })
    return {"ok": True, "tracked": out}


@app.post("/api/tracked/add")
def api_tracked_add(pcode: str = Query(...), name: str = Query(""), frequency: int = Query(7)):
    """加入追蹤法規"""
    tracker = get_tracker()
    if not name:
        meta = tracker.law_meta(pcode)
        if meta:
            name = meta["name"]
    ok = tracker.add_tracking(pcode, name=name or None, frequency_days=frequency)
    if not ok:
        raise HTTPException(status_code=400, detail=f"無法加入追蹤：pcode={pcode}")
    return {"ok": True, "message": f"已加入 {name or pcode}"}


@app.delete("/api/tracked/{pcode}")
def api_tracked_remove(pcode: str):
    """移除法規追蹤"""
    tracker = get_tracker()
    ok = tracker.remove_tracking(pcode)
    if not ok:
        raise HTTPException(status_code=404, detail=f"未追蹤此 pcode: {pcode}")
    return {"ok": True, "message": f"已移除 {pcode}"}


@app.get("/api/history")
def api_history(days: int = Query(7), pcode: Optional[str] = Query(None)):
    """查核歷史"""
    tracker = get_tracker()
    if pcode:
        rows = tracker.get_history(pcode, limit=50)
    else:
        rows = tracker.get_recent_changes(days=days)
    return {"ok": True, "history": rows}


@app.get("/api/search")
def api_search(keyword: str = Query(...)):
    """搜尋法規"""
    tracker = get_tracker()
    results = tracker.search_law(keyword)
    return {"ok": True, "results": results[:30]}


@app.get("/api/diff/{pcode}")
def api_diff(pcode: str, format: str = Query("json")):
    """新舊條文對照"""
    tracker = get_tracker()
    report = build_diff_report(pcode, tracker)
    if not report:
        raise HTTPException(status_code=404, detail=f"無法建立 {pcode} 的異動報告")

    if format == "json":
        # 清理 char_diff 中的大段文字（只留摘要）
        for m in report.get("modified", []):
            if "char_diff" in m:
                m["char_diff_summary"] = _summarize_char_diff(m["char_diff"])
                del m["char_diff"]
            m["old"] = m.get("old", "")[:300]
            m["new"] = m.get("new", "")[:300]
        return {"ok": True, "report": report}

    # format == "docx"
    export_dir = os.path.join(_PROJECT_DIR, "data", "exports")
    os.makedirs(export_dir, exist_ok=True)
    name_safe = re.sub(r'[\\/:*?"<>|]', "_", report["name"])
    out_path = os.path.join(
        export_dir,
        f"{name_safe}_新舊條文對照_{report['new_date']}.docx",
    )
    export_word(report, out_path)
    return FileResponse(
        out_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=os.path.basename(out_path),
    )


@app.get("/api/diff/all")
def api_diff_all():
    """批次產出所有有異動法規的 Word 對照表"""
    tracker = get_tracker()
    tracked = tracker.get_all_tracked()
    export_dir = os.path.join(_PROJECT_DIR, "data", "exports")
    os.makedirs(export_dir, exist_ok=True)

    generated = []
    for t in tracked:
        pcode = t["pcode"]
        try:
            report = build_diff_report(pcode, tracker)
            if report and report.get("changed_count", 0) > 0:
                name_safe = re.sub(r'[\\/:*?"<>|]', "_", report["name"])
                out_path = os.path.join(
                    export_dir,
                    f"{name_safe}_新舊條文對照_{report['new_date']}.docx",
                )
                export_word(report, out_path)
                generated.append({"pcode": pcode, "name": report["name"], "path": out_path})
        except Exception as e:
            logger.warning(f"diff-all 跳過 {pcode}: {e}")

    return {"ok": True, "generated": len(generated), "files": generated}


def _summarize_char_diff(ops):
    """從 char_diff ops 中取前後各一段作為摘要"""
    added_chars = "".join(o["s"] for o in ops if o["t"] == "+")
    removed_chars = "".join(o["s"] for o in ops if o["t"] == "-")
    summary = []
    if added_chars:
        summary.append(f"+{added_chars[:80]}")
    if removed_chars:
        summary.append(f"-{removed_chars[:80]}")
    return " | ".join(summary) if summary else ""


# ═════════════════════════════════════════════
# 直接執行
# ═════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.zhiyan_legal.regulation_api:app", host="127.0.0.1", port=7850, reload=True)
