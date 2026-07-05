"""
全系統唯一設定入口 — ZhiyanSettings

所有子系統統一從此載入設定，無需各自讀環境變數。

使用方式：
    from zhiyan_legal.config import settings

    client = openai.OpenAI(
        api_key=settings.api_key,
        base_url=settings.api_base_url,
    )
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
    # 從專案根目錄的 .env 載入（最多往上找 3 層）
    _root = Path(__file__).resolve()
    for _ in range(5):
        _candidate = _root / ".env"
        if _candidate.exists():
            load_dotenv(_candidate, override=False)
            break
        _root = _root.parent
except ImportError:
    pass  # python-dotenv 未安裝時靜默跳過

logger = logging.getLogger("zhiyan_legal.config")


def _get(key: str, *fallbacks: str, default: str = "") -> str:
    """依序嘗試多個環境變數，回傳第一個有值的。"""
    for k in (key, *fallbacks):
        v = os.environ.get(k, "").strip()
        if v:
            return v
    return default


@dataclass
class ZhiyanSettings:
    """全系統設定物件（singleton）。"""

    # ── 主模型 API ──────────────────────────────────────────────────
    api_key: str = field(default_factory=lambda: _get(
        "ZHIYAN_API_KEY",
        "OPENAI_API_KEY", "OPENROUTER_API_KEY",
        "GEMINI_API_KEY", "GOOGLE_API_KEY",
    ))
    api_base_url: str = field(default_factory=lambda: _get(
        "ZHIYAN_API_BASE_URL",
        default="https://api.openai.com/v1",
    ))
    model: str = field(default_factory=lambda: _get(
        "ZHIYAN_MODEL", default="gpt-4o-mini",
    ))
    provider: str = field(default_factory=lambda: _get(
        "ZHIYAN_PROVIDER", default="openai",
    ))

    # ── 合議庭 Agnes Keys ────────────────────────────────────────────
    agnes_key_1: str = field(default_factory=lambda: _get(
        "AGNES_API_KEY_1", "AGNES_KEY1",
    ))
    agnes_key_2: str = field(default_factory=lambda: _get(
        "AGNES_API_KEY_2", "AGNES_KEY2",
    ))
    agnes_base_url: str = field(default_factory=lambda: _get(
        "AGNES_BASE_URL",
        default="https://apihub.agnes-ai.com/v1",
    ))
    agnes_model: str = field(default_factory=lambda: _get(
        "AGNES_MODEL", default="agnes-2.0-flash",
    ))

    # ── Gemini (合議庭第三席) ────────────────────────────────────────
    gemini_api_key: str = field(default_factory=lambda: _get(
        "GEMINI_API_KEY", "GOOGLE_API_KEY",
    ))
    gemini_model: str = field(default_factory=lambda: _get(
        "GEMINI_MODEL", default="gemini-2.5-flash",
    ))

    # ── 輸出調控 ────────────────────────────────────────────────────
    temperature: float = field(default_factory=lambda: float(
        _get("ZHIYAN_TEMPERATURE", default="0.3")
    ))
    max_tokens: int = field(default_factory=lambda: int(
        _get("ZHIYAN_MAX_TOKENS", default="4096")
    ))

    # ── 路徑 ────────────────────────────────────────────────────────
    docs_dir: str = field(default_factory=lambda: _get(
        "ZHIYAN_DOCS_DIR",
        default=str(Path(__file__).resolve().parents[2] / "docs"),
    ))
    skill_dir: str = field(default_factory=lambda: _get(
        "ZHIYAN_SKILL_DIR",
        default=str(Path(__file__).resolve().parents[2]
                    / ".hermes" / "skills" / "openclaw-imports" / "zhiyan-legal"),
    ))
    db_path: str = field(default_factory=lambda: _get(
        "ZHIYAN_DB_PATH",
        default=str(Path(__file__).resolve().parents[2] / "data" / "laws.db"),
    ))

    # ── 系統行為 ────────────────────────────────────────────────────
    log_level: str = field(default_factory=lambda: _get(
        "ZHIYAN_LOG_LEVEL", default="INFO",
    ))
    dry_run: bool = field(default_factory=lambda: (
        os.environ.get("ZHIYAN_DRY_RUN", "").lower() in ("1", "true", "yes")
    ))
    debug: bool = field(default_factory=lambda: (
        os.environ.get("ZHIYAN_DEBUG", "").lower() in ("1", "true", "yes")
    ))

    def validate(self) -> list[str]:
        """回傳所有設定警告（不 raise，讓呼叫端決定是否中止）。"""
        warnings: list[str] = []
        if not self.api_key:
            warnings.append(
                "ZHIYAN_API_KEY 未設定 — 主模型查詢將失敗。"
                " 請在 .env 設定或匯出環境變數。"
            )
        if not self.agnes_key_1 and not self.agnes_key_2:
            warnings.append(
                "AGNES_API_KEY_1/2 均未設定 — 合議庭 Agnes 席次將無法運作。"
            )
        if not self.gemini_api_key:
            warnings.append(
                "GEMINI_API_KEY 未設定 — 合議庭 Gemini 席次將跳過。"
            )
        return warnings

    def __post_init__(self) -> None:
        # 設定 log level
        logging.basicConfig(
            level=getattr(logging, self.log_level.upper(), logging.INFO),
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )
        for w in self.validate():
            logger.warning(w)


# ── Singleton ───────────────────────────────────────────────────────
settings = ZhiyanSettings()
