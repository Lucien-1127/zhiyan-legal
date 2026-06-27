"""
Task router — maps user input keywords to task labels.

Mirrors the MODE_ROUTER logic from the specification (docs/20_*).
"""

from __future__ import annotations

from typing import Dict, List, Optional

# ── Keyword → task mappings ────────────────────────────────────────
KEYWORD_MAP: Dict[str, str] = {
    # QC
    "檢查": "QC", "抓錯": "QC", "對齊": "QC",
    "找矛盾": "QC", "稽核": "QC", "審驗": "QC",
    "審計": "QC", "審查": "QC", "核對": "QC", "核對比對": "QC",
    # RESEARCH
    "查資料": "RESEARCH", "研究": "RESEARCH", "比對": "RESEARCH",
    "整理多來源": "RESEARCH", "更新資訊": "RESEARCH",
    "調查": "RESEARCH", "查": "RESEARCH", "搜尋": "RESEARCH", "查詢": "RESEARCH",
    # REPORT
    "產出報告": "REPORT", "報告": "REPORT", "摘要": "REPORT",
    "主管版本": "REPORT", "交付文件": "REPORT",
    "整理成": "REPORT", "寫成": "REPORT",
    # CONSULTANT
    "比較": "CONSULTANT", "方案A": "CONSULTANT", "方案B": "CONSULTANT",
    "利弊": "CONSULTANT", "風險對照": "CONSULTANT",
    # TUTOR
    "什麼是": "TUTOR", "解釋": "TUTOR", "是什麼": "TUTOR",
    "制度": "TUTOR", "概念": "TUTOR",
    # TA
    "批改": "TA", "給分": "TA", "評分": "TA",
    # LITIGATION (compound variants to avoid "告" false matches in "報告")
    "訴訟": "LITIGATION", "攻防": "LITIGATION",
    "起訴": "LITIGATION", "提告": "LITIGATION",
    "被告": "LITIGATION", "告訴": "LITIGATION",
    "控告": "LITIGATION", "告人": "LITIGATION", "告他": "LITIGATION",
    # LEGAL_WRITER
    "起草": "LEGAL_WRITER", "合約": "LEGAL_WRITER",
    "律師函": "LEGAL_WRITER", "訴狀": "LEGAL_WRITER",
    "法律文書": "LEGAL_WRITER", "契約": "LEGAL_WRITER",
    # SAFETY (compound variants first to reduce false positives)
    "自殺": "SAFETY", "不想活": "SAFETY", "想死": "SAFETY",
    "謀殺": "SAFETY", "殺人": "SAFETY", "殺害": "SAFETY",
    "綁架": "SAFETY", "跟蹤": "SAFETY",
    "詐騙": "SAFETY", "威脅": "SAFETY",
    "殺": "SAFETY",
    # SIMULATION (模擬模式豁免 — 覆蓋 QC/RESEARCH/REPORT)
    "假設": "SIMULATION", "模擬": "SIMULATION",
    "推演": "SIMULATION", "假定": "SIMULATION",
    "如果": "SIMULATION",
}

ROUTE_ORDER = ["QC", "RESEARCH", "REPORT"]
PERSONA_ORDER = ["CONSULTANT", "TA", "TUTOR", "LEGAL_WRITER"]

# ── Boundary protection for high-risk short keywords ────────────────
# "殺" inside "抹殺" → false positive for SAFETY
# We require: not BOTH preceded AND followed by CJK characters.

_HIGH_RISK_SINGLE_CHARS = {"殺"}


def _keyword_in_text(kw: str, text: str) -> bool:
    """Match keyword with boundary protection for high-risk single chars.

    Currently protects: '殺' (false match in '抹殺').
    For these, we check the character is not fully embedded between
    two CJK characters.
    """
    if len(kw) == 1 and kw in _HIGH_RISK_SINGLE_CHARS:
        idx = text.find(kw)
        while idx != -1:
            prev_cjk = idx > 0 and '\u4e00' <= text[idx - 1] <= '\u9fff'
            next_cjk = (idx + 1 < len(text)
                        and '\u4e00' <= text[idx + 1] <= '\u9fff')
            if not (prev_cjk and next_cjk):
                return True
            idx = text.find(kw, idx + 1)
        return False
    return kw in text


def route(text: str) -> str:
    """
    Determine the task label for a given input text.

    Returns the highest-priority matching task label.
    Default: "CONSULTANT"
    """
    # Sort keywords by length (longest first) to avoid substring collisions
    sorted_kw = sorted(KEYWORD_MAP.items(), key=lambda x: -len(x[0]))

    # 1. Check SAFETY first (overrides everything)
    for kw, task in sorted_kw:
        if task == "SAFETY" and _keyword_in_text(kw, text):
            return "SAFETY"

    # 2. Check SIMULATION (模擬模式 — 必須在 LITIGATION 之前，讓「模擬」覆蓋「訴訟」)
    for kw, task in sorted_kw:
        if task == "SIMULATION" and _keyword_in_text(kw, text):
            return "SIMULATION"

    # 3. Check LITIGATION
    for kw, task in sorted_kw:
        if task == "LITIGATION" and _keyword_in_text(kw, text):
            return "LITIGATION"

    # 4. Check mode routing (QC > RESEARCH > REPORT)
    for route_name in ROUTE_ORDER:
        for kw, task in sorted_kw:
            if task == route_name and _keyword_in_text(kw, text):
                return route_name

    # 5. Check personas
    for p in PERSONA_ORDER:
        for kw, task in sorted_kw:
            if task == p and _keyword_in_text(kw, text):
                return p

    # 6. Default
    return "CONSULTANT"


def describe_route(task: str) -> str:
    """Return a human-readable description of the routed task."""
    descriptions = {
        "QC": "品質檢查 (Quality Check)",
        "RESEARCH": "法律研究檢索 (Legal Research)",
        "REPORT": "正式報告產出 (Report Generation)",
        "CONSULTANT": "顧問分析 (Consultant Advisory)",
        "TA": "助教批改 (TA Review)",
        "TUTOR": "教學解釋 (Tutorial)",
        "LEGAL_WRITER": "合約起草 (Legal Writing)",
        "LITIGATION": "訴訟模擬 (Litigation Simulation)",
        "SAFETY": "⚠️ 安全優先路由 (Safety Protocol)",
        "SIMULATION": "🧪 模擬模式 (Simulation Mode)",
    }
    return descriptions.get(task, task)
