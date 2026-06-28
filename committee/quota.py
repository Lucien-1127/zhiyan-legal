"""API 配額追蹤與警告 — 避免靜默失敗。"""

from __future__ import annotations

import json
import os
import time
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

QUOTA_FILE = Path.home() / "zhiyan-legal" / "tests" / "ablation_results" / ".quota_cache.json"

# 已知配額限制
QUOTA_LIMITS: Dict[str, Dict] = {
    "gemini-2.5-flash": {"daily": 20, "rpm": 20},
    "gemini-2.0-flash": {"daily": 1500, "rpm": 30},
    "agnes-2.0-flash": {"daily": None, "rpm": 20},     # 無明確每日限制
    "deepseek-v4-flash": {"daily": None, "rpm": None},  # 付費
}


def load_counts() -> dict:
    """讀取累計配額使用量。"""
    if QUOTA_FILE.exists():
        try:
            with open(QUOTA_FILE) as f:
                data = json.load(f)
                # 只保留今日資料
                today = str(date.today())
                if data.get("date") != today:
                    data = {"date": today, "models": {}}
                return data
        except (json.JSONDecodeError, KeyError):
            pass
    return {"date": str(date.today()), "models": {}}


def save_counts(data: dict) -> None:
    """寫回配額使用量。"""
    QUOTA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(QUOTA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def record_call(model_id: str, count: int = 1) -> None:
    """記錄一次 API 呼叫。"""
    data = load_counts()
    data.setdefault("models", {}).setdefault(model_id, 0)
    data["models"][model_id] += count
    save_counts(data)


def get_remaining(model_id: str) -> Optional[int]:
    """查詢指定模型的剩餘呼叫次數。

    Returns None 表示無限制。
    """
    limits = QUOTA_LIMITS.get(model_id, {})
    daily_limit = limits.get("daily")
    if daily_limit is None:
        return None  # 無限制

    data = load_counts()
    used = data.get("models", {}).get(model_id, 0)
    return max(0, daily_limit - used)


def warn_if_low(model_id: str, threshold: int = 5) -> bool:
    """如果配額低於 threshold 回傳 True 並印出警告。"""
    remaining = get_remaining(model_id)
    if remaining is None:
        return False  # 無限制

    if remaining == 0:
        print(f"\n⚠️  [QUOTA] {model_id} 今日配額已用盡！")
        print(f"  限制：{QUOTA_LIMITS[model_id]['daily']}/天")
        print(f"  建議：換模型或等配額重置（當地時間午夜）")
        return True
    elif remaining <= threshold:
        print(f"\n⚠️  [QUOTA] {model_id} 僅剩 {remaining} 次呼叫")
        print(f"  限制：{QUOTA_LIMITS[model_id]['daily']}/天")
        return True
    return False


def print_quota_status(models: List[str]) -> None:
    """印出所有模型的配額狀態。"""
    print(f"\n📊 配額狀態 ({date.today()})")
    print(f"{'模型':<25} {'使用/限制':<15} {'剩餘':<8}")
    print("-" * 50)
    for mid in models:
        limits = QUOTA_LIMITS.get(mid, {})
        daily = limits.get("daily", "N/A")
        data = load_counts()
        used = data.get("models", {}).get(mid, 0)
        remaining = get_remaining(mid)

        if remaining is None:
            print(f"{mid:<25} {used:>4}/{'∞':<5} {'∞':<8}")
        else:
            pct = round(used / daily * 100) if daily else 0
            warn = "⚠️" if remaining <= 5 else " "
            print(f"{mid:<25} {used:>4}/{daily:<5} {warn}{remaining:<7}")
