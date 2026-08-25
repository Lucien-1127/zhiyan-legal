"""FastAPI transport for the regulation monitoring application.

HTTP concerns live here so the regulation tracker and the domain/application
layers do not need to import a web framework. ``regulation_api`` remains a
compatibility module that re-exports this application.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from ..regulation_diff import build_diff_report, export_word
from ..regulation_tracker import RegulationTracker

logger = logging.getLogger("regulation_api")
_PROJECT_DIR = Path(__file__).resolve().parents[3]

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

_tracker: Optional[RegulationTracker] = None


def get_tracker() -> RegulationTracker:
    global _tracker
    if _tracker is None:
        _tracker = RegulationTracker()
    return _tracker


@app.get("/api/status")
def api_status():
    tracker = get_tracker()
    summary = tracker.status_summary()
    return {
        "ok": True,
        "index_size": summary["index_size"],
        "tracked_count": summary["total_tracked"],
        "changed_recent_7d": summary["changed_recent_7d"],
        "last_sync": summary.get("last_sync"),
        "tracked": summary["tracked_list"],
    }


@app.post("/api/sync")
def api_sync(force: bool = Query(False)):
    tracker = get_tracker()
    try:
        downloaded = tracker.sync_index(force=force)
        return {"ok": True, "downloaded": downloaded, "message": "同步完成" if downloaded else "索引已是今日最新"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/check")
def api_check(official: bool = Query(True)):
    tracker = get_tracker()
    tracker.sync_index(force=False)
    results = tracker.check_all(official=official)
    changed = [row for row in results if row.get("changed")]
    newly_tracked = [row for row in results if row.get("status") == "newly_tracked"]
    errors = [row for row in results if row.get("status") == "error"]
    return {
        "ok": True,
        "checked": len(results),
        "changed": len(changed),
        "newly_tracked": len(newly_tracked),
        "errors": len(errors),
        "results": [
            {"pcode": row["pcode"], "name": row["name"], "status": row["status"],
             "old_version": row.get("old_version"), "new_version": row.get("new_version"),
             "changed": row.get("changed", False)}
            for row in results
        ],
    }


@app.get("/api/tracked")
def api_tracked():
    tracker = get_tracker()
    output = []
    for row in tracker.get_all_tracked():
        meta = tracker.law_meta(row["pcode"])
        output.append({
            "pcode": row["pcode"], "name": row["name"],
            "level": row.get("level", meta.get("level", "") if meta else ""),
            "baseline_version": row.get("baseline_version", ""),
            "baseline_date": row.get("baseline_date", ""),
            "frequency_days": row.get("frequency_days", 7),
            "last_checked_at": row.get("last_checked_at", ""),
            "abolished": meta.get("abolished", False) if meta else False,
            "current_version": meta.get("modifiedDate", "") if meta else "",
        })
    return {"ok": True, "tracked": output}


@app.post("/api/tracked/add")
def api_tracked_add(pcode: str = Query(...), name: str = Query(""), frequency: int = Query(7)):
    tracker = get_tracker()
    if not name:
        meta = tracker.law_meta(pcode)
        if meta:
            name = meta["name"]
    if not tracker.add_tracking(pcode, name=name or None, frequency_days=frequency):
        raise HTTPException(status_code=400, detail=f"無法加入追蹤：pcode={pcode}")
    return {"ok": True, "message": f"已加入 {name or pcode}"}


@app.delete("/api/tracked/{pcode}")
def api_tracked_remove(pcode: str):
    if not get_tracker().remove_tracking(pcode):
        raise HTTPException(status_code=404, detail=f"未追蹤此 pcode: {pcode}")
    return {"ok": True, "message": f"已移除 {pcode}"}


@app.get("/api/history")
def api_history(days: int = Query(7), pcode: Optional[str] = Query(None)):
    tracker = get_tracker()
    rows = tracker.get_history(pcode, limit=50) if pcode else tracker.get_recent_changes(days=days)
    return {"ok": True, "history": rows}


@app.get("/api/search")
def api_search(keyword: str = Query(...)):
    return {"ok": True, "results": get_tracker().search_law(keyword)[:30]}


@app.get("/api/diff/{pcode}")
def api_diff(pcode: str, format: str = Query("json")):
    report = build_diff_report(pcode, get_tracker())
    if not report:
        raise HTTPException(status_code=404, detail=f"無法建立 {pcode} 的異動報告")
    if format == "json":
        for item in report.get("modified", []):
            if "char_diff" in item:
                item["char_diff_summary"] = _summarize_char_diff(item["char_diff"])
                del item["char_diff"]
            item["old"] = item.get("old", "")[:300]
            item["new"] = item.get("new", "")[:300]
        return {"ok": True, "report": report}

    export_dir = _PROJECT_DIR / "data" / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    name_safe = re.sub(r'[\\/:*?"<>|]', "_", report["name"])
    output_path = export_dir / f"{name_safe}_新舊條文對照_{report['new_date']}.docx"
    export_word(report, str(output_path))
    return FileResponse(str(output_path), media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", filename=output_path.name)


@app.get("/api/diff/all")
def api_diff_all():
    tracker = get_tracker()
    export_dir = _PROJECT_DIR / "data" / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    generated = []
    for tracked in tracker.get_all_tracked():
        pcode = tracked["pcode"]
        try:
            report = build_diff_report(pcode, tracker)
            if report and report.get("changed_count", 0) > 0:
                name_safe = re.sub(r'[\\/:*?"<>|]', "_", report["name"])
                output_path = export_dir / f"{name_safe}_新舊條文對照_{report['new_date']}.docx"
                export_word(report, str(output_path))
                generated.append({"pcode": pcode, "name": report["name"], "path": str(output_path)})
        except Exception as exc:
            logger.warning("diff-all 跳過 %s: %s", pcode, exc)
    return {"ok": True, "generated": len(generated), "files": generated}


def _summarize_char_diff(ops):
    added = "".join(item["s"] for item in ops if item["t"] == "+")
    removed = "".join(item["s"] for item in ops if item["t"] == "-")
    summary = []
    if added:
        summary.append(f"+{added[:80]}")
    if removed:
        summary.append(f"-{removed[:80]}")
    return " | ".join(summary) if summary else ""


__all__ = ["app", "get_tracker", "api_status", "api_sync", "api_check", "api_tracked", "api_tracked_add", "api_tracked_remove", "api_history", "api_search", "api_diff", "api_diff_all"]
