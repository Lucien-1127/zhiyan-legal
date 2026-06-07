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
    "審計": "QC", "核對": "QC", "比對": "QC",
    # RESEARCH
    "查資料": "RESEARCH", "研究": "RESEARCH", "比對": "RESEARCH",
    "整理多來源": "RESEARCH", "更新資訊": "RESEARCH",
    "查": "RESEARCH", "搜尋": "RESEARCH",
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
    # LITIGATION
    "訴訟": "LITIGATION", "攻防": "LITIGATION",
    "起訴": "LITIGATION", "告": "LITIGATION",
    # SAFETY
    "自殺": "SAFETY", "不想活": "SAFETY", "想死": "SAFETY",
    "殺": "SAFETY", "綁架": "SAFETY", "跟蹤": "SAFETY",
    "詐騙": "SAFETY", "威脅": "SAFETY",
}

ROUTE_ORDER = ["QC", "RESEARCH", "REPORT"]
PERSONA_ORDER = ["CONSULTANT", "TA", "TUTOR", "LEGAL_WRITER"]


def route(text: str) -> str:
    """
    Determine the task label for a given input text.

    Returns the highest-priority matching task label.
    Default: "QC" (fallback)
    """
    # Sort keywords by length (longest first) to avoid substring collisions
    sorted_kw = sorted(KEYWORD_MAP.items(), key=lambda x: -len(x[0]))

    # 1. Check SAFETY first (overrides everything)
    for kw, task in sorted_kw:
        if task == "SAFETY" and kw in text:
            return "SAFETY"

    # 2. Check LITIGATION
    for kw, task in sorted_kw:
        if task == "LITIGATION" and kw in text:
            return "LITIGATION"

    # 3. Check mode routing (QC > RESEARCH > REPORT)
    for route_name in ROUTE_ORDER:
        for kw, task in sorted_kw:
            if task == route_name and kw in text:
                return route_name

    # 4. Check personas
    for p in PERSONA_ORDER:
        for kw, task in sorted_kw:
            if task == p and kw in text:
                return p

    # 5. Default
    return "QC"


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
    }
    return descriptions.get(task, task)
