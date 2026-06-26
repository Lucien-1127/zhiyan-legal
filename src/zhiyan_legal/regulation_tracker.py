"""
regulation_tracker — 法規異動自動偵測引擎

從 law-tracker (Node.js) 移植核心邏輯，改寫為 Python 模組，
整合進智研 AI 法律工作站。

參考來源：https://github.com/ksliao0314/law-tracker (MIT License)

功能：
- 每日下載全國法規資料庫索引 (Law + Order JSON ZIP)
- 比對追蹤法規的 baseline 版本 vs 現行版本
- 產出異動報告（新增、修正、刪除條文）
- 更新法規現狀參考表

用法：
    from zhiyan_legal.regulation_tracker import RegulationTracker
    tracker = RegulationTracker()
    tracker.sync_index()           # 下載最新法規索引
    tracker.add_tracking(...)      # 加入追蹤法規
    results = tracker.check_all()  # 執行比對
"""

import json
import logging
import os
import re
import sqlite3
import time
import zipfile
from datetime import datetime, timezone, timedelta
from typing import Optional
from urllib.request import urlopen, Request

logger = logging.getLogger("regulation_tracker")

# ── 資料源 ────────────────────────────────────────
LAW_API = "https://law.moj.gov.tw/api/Ch/Law/JSON"
ORDER_API = "https://law.moj.gov.tw/api/Ch/Order/JSON"
LAWOLDVER = "https://law.moj.gov.tw/LawClass/LawOldVer.aspx?pcode="
LAWHISTORY = "https://law.moj.gov.tw/LawClass/LawHistory.aspx?pcode="
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15) ZhiyanTracker/1.0"

# ── 內建資料目錄 ─────────────────────────────────
DEFAULT_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
)
DB_NAME = "regulation_tracker.db"


# ═══════════════════════════════════════════════════
# 國字數字 → 阿拉伯數字（解析沿革用）
# ═══════════════════════════════════════════════════

_CN_DIGITS = {
    "〇": 0, "零": 0, "一": 1, "二": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "兩": 2,
}


def _cn_to_num(s: str) -> int:
    section = 0
    num = 0
    for ch in s:
        if ch in _CN_DIGITS:
            num = _CN_DIGITS[ch]
        elif ch == "十":
            section += (num or 1) * 10
            num = 0
        elif ch == "百":
            section += (num or 1) * 100
            num = 0
        elif ch == "千":
            section += (num or 1) * 1000
            num = 0
    return section + num


def _parse_roc_date(s: str) -> str:
    """中華民國一百零六年六月十四日 → '20170614'"""
    m = re.search(
        r"([〇零一二三四五六七八九十百千兩]+)\s*年\s*"
        r"([〇零一二三四五六七八九十百千兩]+)\s*月\s*"
        r"([〇零一二三四五六七八九十百千兩]+)\s*日",
        s or "",
    )
    if not m:
        return ""
    y = _cn_to_num(m.group(1)) + 1911
    mo = _cn_to_num(m.group(2))
    da = _cn_to_num(m.group(3))
    if not y or not mo or not da:
        return ""
    return f"{y}{mo:02d}{da:02d}"


def _parse_amendment_dates(text: str) -> list[str]:
    """從沿革文字擷取所有修正日期（西元 YYYYMMDD，升冪）"""
    if not text:
        return []
    dates = set()
    for m in re.finditer(
        r"中華民國\s*"
        r"([〇零一二三四五六七八九十百千兩]+\s*年[〇零一二三四五六七八九十百千兩]+\s*月[〇零一二三四五六七八九十百千兩]+\s*日)",
        text,
    ):
        d = _parse_roc_date(m.group(1))
        if d:
            dates.add(d)
    return sorted(dates)


# ═══════════════════════════════════════════════════
# 日期工具
# ═══════════════════════════════════════════════════

def _ymd_norm(s: str) -> str:
    """YYYY-MM-DD 或 YYYYMMDD → YYYYMMDD（校驗合法日期）"""
    d = re.sub(r"\D", "", str(s))
    if len(d) != 8:
        return ""
    try:
        dt = datetime(int(d[:4]), int(d[4:6]), int(d[6:8]))
        if dt.strftime("%Y%m%d") == d:
            return d
    except ValueError:
        pass
    return ""


def _today_ymd() -> str:
    return datetime.now().strftime("%Y%m%d")


def _add_days(ymd: str, days: int) -> str:
    d = _ymd_norm(ymd)
    if not d or len(d) != 8:
        return d
    dt = datetime(int(d[:4]), int(d[4:6]), int(d[6:8])) + timedelta(days=days)
    return dt.strftime("%Y%m%d")


# ═══════════════════════════════════════════════════
# 索引下載與解析
# ═══════════════════════════════════════════════════

def _fetch_zip(url: str, timeout: int = 60) -> bytes:
    """下載 ZIP 檔案"""
    req = Request(url, headers={"User-Agent": UA, "Accept": "application/zip,application/octet-stream,*/*"})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _parse_moj_zip(buf: bytes) -> list[dict]:
    """從 moj.gov.tw 的 ZIP 提取 JSON"""
    import io
    with zipfile.ZipFile(io.BytesIO(buf)) as zf:
        names = zf.namelist()
        json_name = next((n for n in names if n.endswith(".json")), None)
        if not json_name:
            raise ValueError("ZIP 內找不到 JSON 檔案")
        data = json.loads(zf.read(json_name).decode("utf-8-sig"))
    return data if isinstance(data, list) else data.get("Laws", [])


class RegulationTracker:
    """法規異動偵測引擎"""

    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir or DEFAULT_DATA_DIR
        os.makedirs(self.data_dir, exist_ok=True)
        self.db_path = os.path.join(self.data_dir, DB_NAME)
        self._init_db()

        # 記憶體快取
        self._index: dict[str, dict] = {}   # pcode → {name, level, modifiedDate, abolished, ...}
        self._histories: dict[str, str] = {} # pcode → 沿革文字
        self._fetched_at: Optional[str] = None

    # ── 資料庫初始化 ──────────────────────────────

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tracked_regulations (
                    pcode TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    level TEXT DEFAULT '',
                    baseline_version TEXT,       -- 上次確認的版本日期 (YYYYMMDD)
                    baseline_date TEXT,           -- 設定 baseline 的日期
                    frequency_days INTEGER DEFAULT 7,
                    last_checked_at TEXT,
                    created_at TEXT DEFAULT (datetime('now','localtime'))
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS check_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pcode TEXT NOT NULL,
                    checked_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                    old_version TEXT,
                    new_version TEXT,
                    status TEXT NOT NULL,
                    summary_json TEXT,
                    FOREIGN KEY (pcode) REFERENCES tracked_regulations(pcode)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS moj_cache (
                    key TEXT PRIMARY KEY,
                    data_json TEXT NOT NULL,
                    fetched_at TEXT NOT NULL
                )
            """)
            conn.commit()

    # ── 索引同步 ──────────────────────────────────

    def sync_index(self, force: bool = False) -> bool:
        """
        下載全國法規資料庫最新索引。
        同一天不重複下載（除非 force=True）。
        回傳 True=有下載, False=沿用快取
        """
        today = _today_ymd()
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT fetched_at FROM moj_cache WHERE key='index_fresh_date'"
            ).fetchone()
            if row and row[0] == today and not force:
                logger.info("索引已是今日最新，跳過下載")
                self._load_index_from_cache()
                return False

        logger.info("下載全國法規資料庫索引中…")
        try:
            # 法律
            buf_law = _fetch_zip(LAW_API)
            laws_law = _parse_moj_zip(buf_law)
            # 命令
            buf_order = _fetch_zip(ORDER_API)
            laws_order = _parse_moj_zip(buf_order)
        except Exception as e:
            logger.error(f"下載法規索引失敗: {e}")
            # 有舊快取就沿用
            if self._load_index_from_cache():
                return False
            raise

        index = {}
        histories = {}
        articles_cache = []  # (pcode, articles_json) for tracked pcode

        # 哪些 pcode 需要條文快照
        tracked_pcodes = {t["pcode"] for t in self.get_all_tracked()}

        for item in laws_law + laws_order:
            pcode = self._pcode_from_url(item.get("LawURL", ""))
            if not pcode:
                continue
            index[pcode] = {
                "name": item.get("LawName", ""),
                "level": item.get("LawLevel", ""),
                "category": item.get("LawCategory", ""),
                "modifiedDate": str(item.get("LawModifiedDate", "") or ""),
                "effectiveDate": str(item.get("LawEffectiveDate", "") or ""),
                "abolished": (item.get("LawAbandonNote", "") or "").strip() == "廢",
            }
            hist = (item.get("LawHistories") or "").strip()
            if hist:
                histories[pcode] = hist
            # 快取條文（僅追蹤中的法規）
            if pcode in tracked_pcodes and item.get("LawArticles"):
                arts = self._extract_articles(item)
                if arts:
                    mod_date = str(item.get("LawModifiedDate", "") or "")
                    articles_cache.append((pcode, mod_date, json.dumps(arts, ensure_ascii=False)))

        self._index = index
        self._histories = histories
        self._fetched_at = datetime.now(timezone.utc).isoformat()

        # 寫入快取
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO moj_cache (key, data_json, fetched_at) VALUES (?, ?, ?)",
                ("index", json.dumps(index, ensure_ascii=False), self._fetched_at),
            )
            conn.execute(
                "INSERT OR REPLACE INTO moj_cache (key, data_json, fetched_at) VALUES (?, ?, ?)",
                ("histories", json.dumps(histories, ensure_ascii=False), self._fetched_at),
            )
            conn.execute(
                "INSERT OR REPLACE INTO moj_cache (key, data_json, fetched_at) VALUES (?, ?, ?)",
                ("index_fresh_date", today, self._fetched_at),
            )
            conn.commit()

        # 寫入條文快照（追蹤中的法規）
        articles_dir = os.path.join(self.data_dir, "articles")
        os.makedirs(articles_dir, exist_ok=True)
        for pcode, mod_date, arts_json in articles_cache:
            fpath = os.path.join(articles_dir, f"{pcode}.json")
            try:
                existing = {}
                if os.path.exists(fpath):
                    with open(fpath, "r", encoding="utf-8") as f:
                        existing = json.load(f)
                existing[mod_date] = json.loads(arts_json)
                # 保留最近的 8 個版本
                keys = sorted(existing.keys())
                for k in keys[:-8]:
                    del existing[k]
                with open(fpath, "w", encoding="utf-8") as f:
                    json.dump(existing, f, ensure_ascii=False, indent=1)
            except Exception as e:
                logger.warning(f"寫入條文快照 {pcode} 失敗: {e}")

        law_count = len(laws_law)
        order_count = len(laws_order)
        logger.info(f"已同步索引：法律 {law_count} 部、命令 {order_count} 部，共 {len(index)} 筆")
        return True

    def _load_index_from_cache(self) -> bool:
        """從 SQLite 快取載入索引"""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT data_json, fetched_at FROM moj_cache WHERE key='index'"
            ).fetchone()
            if not row:
                return False
            self._index = json.loads(row[0])
            self._fetched_at = row[1]
            row2 = conn.execute(
                "SELECT data_json FROM moj_cache WHERE key='histories'"
            ).fetchone()
            if row2:
                self._histories = json.loads(row2[0])
        return True

    @staticmethod
    def _pcode_from_url(url: str) -> str:
        m = re.search(r"[?&]pcode=([^&]+)", url or "")
        return m.group(1) if m else ""

    @staticmethod
    def _extract_articles(item: dict) -> dict:
        """從 ZIP item 的 LawArticles 提取條文 {第1條: 內容, ...}"""
        arts = {}
        raw_no = "ArticleNo"
        raw_content = "ArticleContent"
        for a in item.get("LawArticles") or []:
            no_str = a.get(raw_no, "")
            m = re.search(r"第\s*([0-9A-Za-z]+(?:-[0-9A-Za-z]+)?)\s*條", str(no_str))
            if m:
                no = m.group(1)
                content = (a.get(raw_content) or "").strip()
                # 清理 HTML 標籤和空白
                content = re.sub(r"<[^>]+>", "", content)
                content = content.replace("&nbsp;", " ").replace("&amp;", "&")
                content = re.sub(r"\s+", " ", content).strip()
                if content:
                    arts[no] = content
        return arts

    def get_articles(self, pcode: str) -> dict:
        """讀取本機條文快照 {version_date: {artNo: content, ...}}"""
        fpath = os.path.join(self.data_dir, "articles", f"{pcode}.json")
        if os.path.exists(fpath):
            with open(fpath, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _ensure_index_loaded(self):
        """確保索引已從快取載入（lazy loading）"""
        if not self._index:
            self._load_index_from_cache()

    # ── 索引查詢 ──────────────────────────────────

    def law_meta(self, pcode: str) -> dict | None:
        self._ensure_index_loaded()
        return self._index.get(pcode)

    def search_law(self, keyword: str) -> list[dict]:
        """依關鍵字搜尋法規（精確名稱優先，子字串次之）"""
        self._ensure_index_loaded()
        exact = []
        prefix = []
        fuzzy = []
        for pc, meta in self._index.items():
            name = meta.get("name", "")
            if name == keyword:
                exact.append({
                    "pcode": pc,
                    "name": name,
                    "level": meta.get("level", ""),
                    "modifiedDate": meta.get("modifiedDate", ""),
                    "abolished": meta.get("abolished", False),
                })
            elif name.startswith(keyword):
                prefix.append({
                    "pcode": pc,
                    "name": name,
                    "level": meta.get("level", ""),
                    "modifiedDate": meta.get("modifiedDate", ""),
                    "abolished": meta.get("abolished", False),
                })
            elif keyword in name:
                fuzzy.append({
                    "pcode": pc,
                    "name": name,
                    "level": meta.get("level", ""),
                    "modifiedDate": meta.get("modifiedDate", ""),
                    "abolished": meta.get("abolished", False),
                })
        # 排序：法律優先於命令
        def sort_key(x):
            level_order = 0 if x["level"] == "法律" else 1
            return (level_order, x["name"])
        exact.sort(key=sort_key)
        prefix.sort(key=sort_key)
        fuzzy.sort(key=sort_key)
        return exact + prefix + fuzzy

    def get_all_tracked(self) -> list[dict]:
        """回傳所有追蹤中的法規"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM tracked_regulations ORDER BY name"
            ).fetchall()
            return [dict(r) for r in rows]

    # ── 追蹤管理 ──────────────────────────────────

    def add_tracking(
        self,
        pcode: str,
        name: str = None,
        level: str = None,
        frequency_days: int = 7,
    ) -> bool:
        """加入法規追蹤（從索引補齊中繼資料）"""
        meta = self.law_meta(pcode)
        if not meta and not name:
            logger.warning(f"pcode {pcode} 不在索引中，也未提供名稱")
            return False
        name = name or meta["name"]
        level = level or meta.get("level", "")
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR IGNORE INTO tracked_regulations
                   (pcode, name, level, frequency_days)
                   VALUES (?, ?, ?, ?)""",
                (pcode, name, level, frequency_days),
            )
            conn.commit()
        logger.info(f"已加入追蹤：{name} ({pcode})")
        return True

    def remove_tracking(self, pcode: str) -> bool:
        """移除法規追蹤"""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("DELETE FROM tracked_regulations WHERE pcode=?", (pcode,))
            conn.commit()
        return cur.rowcount > 0

    def update_frequency(self, pcode: str, frequency_days: int) -> bool:
        """更新查核頻率"""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "UPDATE tracked_regulations SET frequency_days=? WHERE pcode=?",
                (frequency_days, pcode),
            )
            conn.commit()
        return cur.rowcount > 0

    # ── as-of 版本查詢 ─────────────────────────────

    def _as_of_date(self, pcode: str, ymd: str) -> str:
        """
        截至某日期（含）為止，最新一版的修正日期。
        從沿革解析版本日期，取 ≤ ymd 的最大值。
        """
        if not ymd:
            return ""
        dates = _parse_amendment_dates(self._histories.get(pcode, ""))
        best = ""
        for d in dates:
            if d <= ymd:
                best = d
            else:
                break
        # 沿革解析不到時退回到索引現值
        if not best:
            meta = self.law_meta(pcode)
            if meta and meta.get("modifiedDate", "") <= ymd:
                best = meta["modifiedDate"]
        return best

    # ── 核心：執行查核 ────────────────────────────

    def check_one(self, pcode: str, official: bool = True) -> dict:
        """
        查核單一法規。

        Parameters
        ----------
        pcode : str
            法規 pcode
        official : bool
            True=正式查核（更新 baseline），False=試算（不更新）

        Returns
        -------
        dict with keys: pcode, name, old_version, new_version, status, changed
            status: 'unchanged' | 'changed' | 'newly_tracked' | 'missing' | 'abolished'
        """
        meta = self.law_meta(pcode)
        now = _today_ymd()

        if not meta:
            return {
                "pcode": pcode,
                "name": pcode,
                "old_version": None,
                "new_version": None,
                "status": "missing",
                "changed": False,
                "abolished": False,
            }

        name = meta["name"]
        abolished = meta.get("abolished", False)
        current_version = meta.get("modifiedDate", "")

        if abolished:
            return {
                "pcode": pcode,
                "name": name,
                "old_version": current_version,
                "new_version": current_version,
                "status": "abolished",
                "changed": False,
                "abolished": True,
            }

        # 讀取 baseline
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT baseline_version, baseline_date FROM tracked_regulations WHERE pcode=?",
                (pcode,),
            ).fetchone()

        if not row or row[0] is None:
            # 首次追蹤：記為「首次納入」
            if official:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute(
                        "UPDATE tracked_regulations SET baseline_version=?, baseline_date=?, last_checked_at=? WHERE pcode=?",
                        (current_version, now, now, pcode),
                    )
                    conn.commit()
            return {
                "pcode": pcode,
                "name": name,
                "old_version": None,
                "new_version": current_version,
                "status": "newly_tracked",
                "changed": False,
            }

        old_version = row[0]

        if current_version > old_version:
            status = "changed"
            changed = True
        else:
            status = "unchanged"
            changed = False

        # 正式查核：更新 baseline
        if official and changed:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "UPDATE tracked_regulations SET baseline_version=?, baseline_date=?, last_checked_at=? WHERE pcode=?",
                    (current_version, now, now, pcode),
                )
                conn.commit()

        # 記錄 history
        summary = json.dumps({
            "old_version": old_version,
            "new_version": current_version,
            "abolished": abolished,
        }, ensure_ascii=False)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO check_history (pcode, old_version, new_version, status, summary_json)
                   VALUES (?, ?, ?, ?, ?)""",
                (pcode, old_version, current_version, status, summary),
            )
            conn.commit()

        return {
            "pcode": pcode,
            "name": name,
            "old_version": old_version,
            "new_version": current_version,
            "status": status,
            "changed": changed,
            "abolished": abolished,
        }

    def check_all(self, official: bool = True) -> list[dict]:
        """查核所有追蹤中的法規"""
        results = []
        tracked = self.get_all_tracked()
        for t in tracked:
            try:
                r = self.check_one(t["pcode"], official=official)
                results.append(r)
                msg = f"  {'✓' if not r['changed'] else '⚠'} {r['name']}"
                if r["status"] == "changed":
                    msg += f" (v{r['old_version']} → v{r['new_version']})"
                elif r["status"] == "newly_tracked":
                    msg += f" (首次納入 v{r['new_version']})"
                elif r["status"] == "abolished":
                    msg += " (已廢止)"
                elif r["status"] == "missing":
                    msg += " (查無此法規)"
                logger.info(msg)
            except Exception as e:
                logger.error(f"查核 {t.get('name', t['pcode'])} 失敗: {e}")
                results.append({
                    "pcode": t["pcode"],
                    "name": t.get("name", t["pcode"]),
                    "status": "error",
                    "error": str(e),
                    "changed": False,
                })
        return results

    # ── 報告 ──────────────────────────────────────

    def get_recent_changes(self, days: int = 7) -> list[dict]:
        """回傳近期異動紀錄"""
        cutoff = _add_days(_today_ymd(), -days)
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT h.*, t.name, t.level
                   FROM check_history h
                   JOIN tracked_regulations t ON h.pcode = t.pcode
                   WHERE h.status='changed' AND h.checked_at >= ?
                   ORDER BY h.checked_at DESC
                   LIMIT 50""",
                (cutoff,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_history(self, pcode: str, limit: int = 20) -> list[dict]:
        """回傳單一法規的查核歷史"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT * FROM check_history
                   WHERE pcode=?
                   ORDER BY checked_at DESC
                   LIMIT ?""",
                (pcode, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def status_summary(self) -> dict:
        """回傳整體狀態摘要"""
        self._ensure_index_loaded()
        tracked = self.get_all_tracked()
        with sqlite3.connect(self.db_path) as conn:
            changed_count = conn.execute(
                "SELECT COUNT(DISTINCT pcode) FROM check_history WHERE status='changed' AND checked_at >= date('now', '-7 days')"
            ).fetchone()[0]
        return {
            "total_tracked": len(tracked),
            "changed_recent_7d": changed_count,
            "last_sync": self._fetched_at,
            "index_size": len(self._index),
            "tracked_list": [
                {"pcode": t["pcode"], "name": t["name"], "level": t.get("level", ""),
                 "baseline_version": t.get("baseline_version", ""),
                 "frequency_days": t.get("frequency_days", 7)}
                for t in tracked
            ],
        }


# ═══════════════════════════════════════════════════
# 命令列介面（直接執行用）
# ═══════════════════════════════════════════════════

def main():
    import argparse
    import sys
    # 確保專案 src 在路徑中
    _project_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    _src_dir = os.path.join(_project_dir, "src")
    if _src_dir not in sys.path:
        sys.path.insert(0, _src_dir)

    parser = argparse.ArgumentParser(description="法規異動偵測引擎")
    parser.add_argument("action", nargs="?", default="check",
                        choices=["sync", "check", "list", "add", "remove", "report", "status",
                                 "track-drug", "track-all-default",
                                 "diff", "diff-all"])
    parser.add_argument("--pcode", help="法規 pcode")
    parser.add_argument("--name", help="法規名稱")
    parser.add_argument("--frequency", type=int, default=7, help="查核頻率（天）")
    parser.add_argument("--force", action="store_true", help="強制重新下載索引")
    parser.add_argument("--days", type=int, default=7, help="報告天數")
    parser.add_argument("--output", help="Word 匯出路徑")
    parser.add_argument("--verbose", "-v", action="store_true", help="詳細輸出")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    tracker = RegulationTracker()

    if args.action == "sync":
        tracker.sync_index(force=args.force)
        print("✓ 索引已同步")

    elif args.action == "check":
        tracker.sync_index(force=args.force)
        results = tracker.check_all()
        changed = [r for r in results if r.get("changed")]
        new = [r for r in results if r.get("status") == "newly_tracked"]
        abolished = [r for r in results if r.get("status") == "abolished"]
        errors = [r for r in results if r.get("status") == "error"]
        print(f"\n查核完成：{len(results)} 部")
        if changed:
            print(f"\n⚠ 有異動 ({len(changed)} 部)：")
            for r in changed:
                print(f"  {r['name']}  v{r['old_version']} → v{r['new_version']}")
        if new:
            print(f"\n🆕 首次納入 ({len(new)} 部)：")
            for r in new:
                print(f"  {r['name']} (v{r['new_version']})")
        if abolished:
            print(f"\n🚫 已廢止 ({len(abolished)} 部)：")
            for r in abolished:
                print(f"  {r['name']}")
        if errors:
            print(f"\n❌ 錯誤 ({len(errors)} 部)：")
            for r in errors:
                print(f"  {r['name']}: {r.get('error')}")
        if not changed and not new and not abolished and not errors:
            print("  全部無異動 ✓")

    elif args.action == "list":
        tracked = tracker.get_all_tracked()
        if not tracked:
            print("目前沒有追蹤中的法規")
        else:
            print(f"追蹤中的法規 ({len(tracked)} 部)：")
            for t in tracked:
                print(f"  {t['name']} ({t['pcode']}) "
                      f"[baseline: {t.get('baseline_version', '-')}] "
                      f"每 {t.get('frequency_days', 7)} 天")

    elif args.action == "add":
        if not args.pcode:
            print("請指定 --pcode")
            return
        tracker.sync_index(force=False)
        ok = tracker.add_tracking(args.pcode, name=args.name, frequency_days=args.frequency)
        if ok:
            meta = tracker.law_meta(args.pcode)
            name = meta["name"] if meta else args.name
            print(f"✓ 已加入追蹤：{name}")
        else:
            print(f"✗ 加入失敗：查無 pcode={args.pcode}")

    elif args.action == "remove":
        if not args.pcode:
            print("請指定 --pcode")
            return
        ok = tracker.remove_tracking(args.pcode)
        print(f"{'✓ 已移除' if ok else '✗ 找不到該法規'}")

    elif args.action == "report":
        changes = tracker.get_recent_changes(days=args.days)
        if not changes:
            print(f"近 {args.days} 天無異動紀錄")
        else:
            print(f"近 {args.days} 天異動紀錄 ({len(changes)} 筆)：")
            for c in changes:
                print(f"  {c['name']} ({c['level']}) "
                      f"v{c['old_version']} → v{c['new_version']} "
                      f"於 {c['checked_at'][:10]}")

    elif args.action == "status":
        s = tracker.status_summary()
        print(f"索引規模：{s['index_size']} 部法規")
        print(f"追蹤中：{s['total_tracked']} 部")
        print(f"近 7 天異動：{s['changed_recent_7d']} 部")
        print(f"最後同步：{s.get('last_sync', '從未')}")
        if s["tracked_list"]:
            print("\n追蹤清單：")
            for t in s["tracked_list"]:
                print(f"  {t['name']} ({t.get('level','')}) "
                      f"baseline={t.get('baseline_version','-')} "
                      f"每 {t.get('frequency_days',7)} 天")

    elif args.action == "track-drug":
        """一鍵追蹤毒品相關法規"""
        tracker.sync_index(force=False)
        drug_pcodes = {
            "C0000008": ("毒品危害防制條例", 7),
        }
        for pcode, (name, freq) in drug_pcodes.items():
            tracker.add_tracking(pcode, name=name, frequency_days=freq)
        print("✓ 已加入毒品相關法規追蹤")

    elif args.action == "track-all-default":
        """追蹤法規現狀參考表中的所有法規"""
        tracker.sync_index(force=False)
        # 精確 pcode 對照（避免子字串誤配）
        defaults = [
            ("毒品危害防制條例", "C0000008", 7),
            ("毒品危害防制條例施行細則", "I0030019", 7),
            ("勞動基準法", "N0030001", 30),
            ("勞工退休金條例", "N0030020", 30),
            ("勞工保險條例", "N0050001", 30),
            ("就業保險法", "N0050021", 30),
            ("性別平等工作法", "N0030014", 30),
            ("職業安全衛生法", "N0060001", 30),
            ("公司法", "J0080001", 30),
            ("商業會計法", "J0080009", 30),
            ("會計法", "T0030001", 30),
            ("證券交易法", "G0400001", 30),
            ("企業併購法", "J0080041", 30),
            ("審計法", "U0010001", 30),
            ("所得稅法", "G0340003", 30),
            ("加值型及非加值型營業稅法", "G0340080", 30),
            ("中華民國刑法", "C0000001", 90),
            ("刑事訴訟法", "C0010001", 90),
            ("民法", "B0000001", 90),
            ("民事訴訟法", "B0010001", 90),
            ("行政程序法", "A0030055", 90),
            ("行政訴訟法", "A0030154", 90),
            ("憲法訴訟法", "A0030159", 90),
        ]
        added = 0
        for name, pcode, freq in defaults:
            tracker.add_tracking(pcode, name=name, frequency_days=freq)
            added += 1
        print(f"✓ 已加入 {added} 部法規追蹤")

    elif args.action == "diff":
        """顯示新舊條文對照"""
        if not args.pcode:
            print("請指定 --pcode")
            return
        from zhiyan_legal.regulation_diff import diff_cmd
        diff_cmd(args.pcode, output=args.output, verbose=args.verbose)

    elif args.action == "diff-all":
        """為所有有異動的法規產生 Word 對照表"""
        from zhiyan_legal.regulation_diff import diff_all_cmd
        diff_all_cmd(verbose=args.verbose)


if __name__ == "__main__":
    main()
