"""
司法院資料開放平臺 — 裁判書 API 整合模組。

端點：https://data.judicial.gov.tw/jdg/api/
規格文件：司法院裁判書開放 API (114.08.22)

限制：
- 服務時間 00:00–06:00（每日）
- Token 有效期 6 小時
- 回傳 7 日前異動資料（非即時）
- 裁判書可能被移除，下載後須配合刪除機制

JID 格式：COURT, YEAR, CASE_TYPE, CASE_NO, DATE, CHECK
  範例：CHDM,100,訴,1552,20130517,2
"""

import json
import os
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger("judicial_api")

API_BASE = "https://data.judicial.gov.tw/jdg/api"
AUTH_ENDPOINT = f"{API_BASE}/Auth"
JLIST_ENDPOINT = f"{API_BASE}/JList"
JDOC_ENDPOINT = f"{API_BASE}/JDoc"

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


class JudicialAPIClient:
    """司法院裁判書開放 API 客戶端。"""

    def __init__(self, username: str = "", password: str = ""):
        self.username = username or os.getenv("JUDICIAL_API_USER", "")
        self.password = password or os.getenv("JUDICIAL_API_PASS", "")
        self.token: Optional[str] = None
        self.token_expiry: Optional[datetime] = None

    def auth(self) -> str:
        """驗證帳密，取得 Token（有效期 6 小時）。"""
        if self.token and self.token_expiry and datetime.now() < self.token_expiry:
            return self.token

        import urllib.request

        payload = json.dumps({"user": self.username, "password": self.password}).encode()
        req = urllib.request.Request(
            AUTH_ENDPOINT,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())

        if "error" in data:
            raise PermissionError(f"驗證失敗：{data['error']}")

        self.token = data["Token"]
        self.token_expiry = datetime.now() + timedelta(hours=6)
        logger.info("API 驗證成功，Token 有效期至 %s", self.token_expiry)
        return self.token

    def get_jlist(self) -> list:
        """取得 7 日前裁判書異動清單。"""
        import urllib.request

        token = self.auth()
        payload = json.dumps({"token": token}).encode()
        req = urllib.request.Request(
            JLIST_ENDPOINT,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=30)
        data = json.loads(resp.read())

        if "error" in data:
            raise RuntimeError(f"JList 失敗：{data['error']}")

        date = data.get("date", "?")
        jlist = data.get("list", [])
        logger.info("取得 %s 的異動清單，共 %d 筆", date, len(jlist))
        return jlist

    def get_jdoc(self, jid: str) -> dict:
        """依 JID 取得單筆裁判書全文。"""
        import urllib.request

        token = self.auth()
        payload = json.dumps({"token": token, "j": jid}).encode()
        req = urllib.request.Request(
            JDOC_ENDPOINT,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=30)
        data = json.loads(resp.read())

        if "error" in data:
            raise RuntimeError(f"JDoc 失敗：{data['error']}")

        return data

    @staticmethod
    def build_jid(court: str, year: str, case_type: str, case_no: str,
                  date: str = "", check: str = "1") -> str:
        """從案件資訊組裝 JID。"""
        court_code = COURT_CODES.get(court, court)
        type_code = CASE_TYPE_CODES.get(case_type, case_type)
        return f"{court_code},{year},{type_code},{case_no},{date},{check}"

    @staticmethod
    def parse_case_number(case_str: str) -> Optional[dict]:
        """解析中文案號字串為 JID 元件。

        範例輸入：
          「臺灣彰化地方法院 100 年度訴字第 1552 號」
          「最高法院112年度台上字第XXX號」
        """
        import re
        # 法院名稱
        court = ""
        for name in sorted(COURT_CODES, key=len, reverse=True):
            if name in case_str:
                court = name
                break

        # 移除法院名稱前綴，避免後續 regex 吞掉法院名
        rest = case_str[len(court):] if court else case_str

        # 年度
        m = re.search(r'(\d{2,3})\s*年度', rest)
        year = m.group(1) if m else ""

        # 從剩餘字串移除已解析的年度部分，避免干擾字別提取
        if m:
            rest = rest[:m.start()] + rest[m.end():]

        # 字別 + 號次（在剩餘字串中搜尋，避免法院名或年度干擾）
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


def search_judgment(case_number: str, username: str = "", password: str = "") -> Optional[dict]:
    """對外主要接口：依案號查詢裁判書全文。

    範例：
        result = search_judgment("臺灣彰化地方法院 100 年度訴字第 1552 號")
        if result:
            print(result["JFULLX"]["JFULLCONTENT"][:500])
    """
    client = JudicialAPIClient(username, password)
    parsed = client.parse_case_number(case_number)
    if not parsed:
        logger.warning("無法解析案號：%s", case_number)
        return None

    jid = client.build_jid(
        parsed["court_code"], parsed["year"],
        parsed["case_type"], parsed["case_no"]
    )
    logger.info("查詢 JID：%s", jid)

    try:
        return client.get_jdoc(jid)
    except Exception as e:
        logger.error("查詢失敗：%s", e)
        return None
