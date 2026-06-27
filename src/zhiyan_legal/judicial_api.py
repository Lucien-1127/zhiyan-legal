"""
司法院裁判書查詢模組 — MCP Taiwan Legal DB 實作

使用 mcp-taiwan-legal-db 套件，即時查詢 judgment.judicial.gov.tw，
免帳密、無時間限制。

8 個工具：
  search_judgments     — 全文搜尋判決
  get_judgment         — 依 JID/URL 取得判決全文
  query_regulation     — 查法條（全國法規資料庫）
  get_pcode            — 法規名稱轉代碼
  search_regulations   — 搜尋法規
  get_interpretation   — 查釋憲（含 868 筆離線資料）
  search_interpretations — 搜尋釋憲
  get_citations        — 引用關係圖

安裝：
  pip install mcp-taiwan-legal-db

使用範例：
  from zhiyan_legal.judicial_api import search_judgments, get_judgment
  results = await search_judgments("詐欺", case_type="刑事")
  doc = await get_judgment(jid="TPSM,114,台上,3753,20251112,1")
"""

import json
import os
import logging
import tempfile
from typing import Optional

logger = logging.getLogger("judicial_api")

# MCP Taiwan Legal DB 套件
from mcp_server.server import JudicialSearchClient, JudgmentDocClient, CacheDB, JudicialWAFBypass
from mcp_server.server import RegulationClient

# ── 全域資源（lazy init） ───────────────────────────
_cache: Optional[CacheDB] = None
_waf: Optional[JudicialWAFBypass] = None
_jud_search: Optional[JudicialSearchClient] = None
_jud_doc: Optional[JudgmentDocClient] = None
_reg_client: Optional[RegulationClient] = None


async def _ensure_init():
    global _cache, _waf, _jud_search, _jud_doc, _reg_client
    if _cache is not None:
        return
    db_path = os.path.join(tempfile.gettempdir(), "zhiyan_legal_cache.db")
    _cache = CacheDB(db_path=db_path)
    await _cache.initialize()
    _waf = JudicialWAFBypass()
    _jud_search = JudicialSearchClient(_cache, _waf)
    _jud_doc = JudgmentDocClient(_cache, _waf)
    _reg_client = RegulationClient(_cache, _waf)
    logger.info("MCP Taiwan Legal DB 初始化完成")


async def search_judgments(
    keyword: str = "",
    court: str = "",
    case_type: str = "",
    year_from: int = 0,
    year_to: int = 0,
    case_word: str = "",
    case_number: str = "",
    main_text: str = "",
) -> dict:
    """全文搜尋判決（即時，免帳密）

    回傳格式：
        {"success": bool, "total_count": int, "results": list, "cached": bool}
    """
    await _ensure_init()
    return await _jud_search.search(
        keyword=keyword, court=court, case_type=case_type,
        year_from=year_from, year_to=year_to,
        case_word=case_word, case_number=case_number,
        main_text=main_text,
    )


async def get_judgment(jid: str = "", url: str = "") -> dict:
    """依 JID 或 URL 取得判決全文"""
    await _ensure_init()
    return await _jud_doc.get(jid=jid, url=url)


async def query_regulation(law_name: str = "", article_no: str = "", pcode: str = "") -> dict:
    """查詢法條（全國法規資料庫 law.moj.gov.tw）"""
    await _ensure_init()
    return await _reg_client.query(law_name=law_name, article_no=article_no, pcode=pcode)


async def search_regulations(keyword: str) -> list:
    """搜尋法規"""
    await _ensure_init()
    return await _reg_client.search(keyword=keyword)

# ── 法院代碼對照表 ────────────────────────────

COURT_CODES = {
    "最高法院": "TPS",
    "最高行政法院": "TPA",
    "臺北高等行政法院": "TPB",
    "臺中高等行政法院": "TCB",
    "高雄高等行政法院": "KSB",
    "智慧財產及商業法院": "IPC",
    "懲戒法院": "ADC",
    "臺灣高等法院": "TPH",
    "臺灣高等法院臺中分院": "TCH",
    "臺灣高等法院臺南分院": "TNH",
    "臺灣高等法院高雄分院": "KSH",
    "臺灣高等法院花蓮分院": "HLH",
    "臺北高等行政法院地方訴訟庭": "TPD",
    "臺中高等行政法院地方訴訟庭": "TCD",
    "高雄高等行政法院地方訴訟庭": "KSD",
    "臺北地方法院": "TPD",
    "士林地方法院": "SLD",
    "新北地方法院": "PCD",
    "桃園地方法院": "TYD",
    "新竹地方法院": "SCD",
    "苗栗地方法院": "MLD",
    "臺中地方法院": "TCD",
    "彰化地方法院": "CHD",
    "南投地方法院": "NTD",
    "雲林地方法院": "ULD",
    "嘉義地方法院": "CYD",
    "臺南地方法院": "TND",
    "高雄地方法院": "KSD",
    "橋頭地方法院": "CTD",
    "屏東地方法院": "PTD",
    "臺東地方法院": "TTT",
    "花蓮地方法院": "HLD",
    "宜蘭地方法院": "ILD",
    "基隆地方法院": "KLD",
    "澎湖地方法院": "PHD",
    "金門地方法院": "KMD",
    "連江地方法院": "LCD",
}

# ── 案件類別代碼 ──────────────────────────────

CASE_TYPE_CODES = {
    "民事": "V",
    "刑事": "M",
    "行政": "A",
    "懲戒": "P",
    "憲法": "C",
}


# ── JID 工具函式（保留，供測試與其他模組使用） ─────

def build_jid(court: str, year: str, case_type: str, case_no: str,
              date: str = "", check: str = "1") -> str:
    """從案件資訊組裝 JID。"""
    court_code = COURT_CODES.get(court, court)
    type_code = CASE_TYPE_CODES.get(case_type, case_type)
    return f"{court_code},{year},{type_code},{case_no},{date},{check}"


def parse_case_number(case_str: str) -> Optional[dict]:
    """解析中文案號字串為 JID 元件。

    範例輸入：
      「臺灣彰化地方法院 100 年度訴字第 1552 號」
      「最高法院112年度台上字第XXX號」
    """
    import re
    court = ""
    for name in sorted(COURT_CODES, key=len, reverse=True):
        if name in case_str:
            court = name
            break

    rest = case_str[len(court):] if court else case_str

    m = re.search(r'(\d{2,3})\s*年度', rest)
    year = m.group(1) if m else ""
    if m:
        rest = rest[:m.start()] + rest[m.end():]

    m = re.search(r'(\w+)\s*字\s*第\s*(\d+)', rest)
    if m:
        case_word = m.group(1)
        case_no = m.group(2)
    else:
        m = re.search(r'(\w+)字第(\d+)', rest)
        if m:
            case_word = m.group(1)
            case_no = m.group(2)
        else:
            return None

    return {
        "court": court,
        "year": year,
        "case_type": case_word,
        "case_no": case_no,
        "court_code": COURT_CODES.get(court, ""),
    }
