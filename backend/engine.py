"""
智研 SaaS 版 — 法律引擎封裝層

將原本 CLI 版的 zhiyan-legal 引擎封裝成可被 FastAPI 呼叫的服務。
支援同步與非同步兩種模式。
"""

from __future__ import annotations

import os
import sys
import logging
from pathlib import Path
from typing import Optional

from openai import OpenAI

logger = logging.getLogger(__name__)

# ─── 路徑設定 ────────────────────────────────────────────
# 專案根目錄（backend/ 的上層）
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"
SRC_DIR = PROJECT_ROOT / "src"

# 確保 src 在 import path 中
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# ─── 預設值 ──────────────────────────────────────────────
DEFAULT_MODEL = "deepseek-chat"
DEFAULT_API_BASE = "https://api.deepseek.com/v1"

# 法律 domain 關鍵字 — 用於自動偵測是否觸發法律模式
LEGAL_KEYWORDS = [
    "法", "條", "判決", "判例", "訴訟", "律師", "法院",
    "起訴", "上訴", "刑法", "民法", "憲法", "行政法",
    "勞動法", "合約", "契約", "侵權", "損害賠償",
    "公然侮辱", "誹謗", "詐欺", "侵占", "竊盜",
    "商標", "專利", "著作權", "股東", "公司",
    "離婚", "監護", "遺產", "繼承", "車禍",
    "存證信函", "支付命令", "假扣押", "假處分",
]


class ZhiyanEngine:
    """封裝智研法律引擎，處理提示詞組合與 LLM 呼叫。"""

    def __init__(self):
        self._system_prompt: Optional[str] = None
        self._docs_loaded = False

    # ─── 提示詞組合 ────────────────────────────────────

    def load_docs(self) -> str:
        """載入 docs/ 中的所有規格文件，組合成 system prompt。"""
        if self._system_prompt and self._docs_loaded:
            return self._system_prompt

        parts = []

        # 載入順序：核心控制層 → 模式與引用層 → 模組與人格層
        load_order = [
            "10_核心控制層",
            "20_模式與引用層",
            "40_模組與人格層",
        ]

        for category in load_order:
            cat_dir = DOCS_DIR / category
            if not cat_dir.exists():
                logger.warning(f"目錄不存在: {cat_dir}")
                continue

            files = sorted(cat_dir.glob("*.md"))
            for f in files:
                try:
                    content = f.read_text(encoding="utf-8")
                    parts.append(f"<!-- {f.name} -->\n{content}")
                except Exception as e:
                    logger.error(f"讀取失敗 {f.name}: {e}")

        self._system_prompt = "\n\n---\n\n".join(parts)
        self._docs_loaded = True

        file_count = len(parts)
        logger.info(f"已載入 {file_count} 份規格文件，共 {len(self._system_prompt):,} 字元")
        return self._system_prompt

    def reload(self):
        """強制重新載入文件（更新後呼叫）。"""
        self._system_prompt = None
        self._docs_loaded = False
        return self.load_docs()

    # ─── API 客戶端 ────────────────────────────────────

    def _get_client(self) -> OpenAI:
        """取得 OpenAI 相容客戶端。"""
        base_url = os.getenv("ZHIYAN_API_BASE_URL", DEFAULT_API_BASE)
        api_key = os.getenv("ZHIYAN_API_KEY", "")

        if not api_key:
            for fallback in ("OPENAI_API_KEY", "OPENROUTER_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
                val = os.getenv(fallback)
                if val:
                    api_key = val
                    break

        return OpenAI(base_url=base_url, api_key=api_key)

    # ─── LLM 查詢 ──────────────────────────────────────

    def query(
        self,
        user_message: str,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        conversation_history: Optional[list[dict]] = None,
    ) -> dict:
        """
        執行法律查詢。

        Parameters
        ----------
        user_message : str
            使用者的問題。
        model : str, optional
            LLM 模型名稱。
        temperature : float
            生成溫度（法律用途建議 0.3 以下）。
        max_tokens : int
            最大輸出 token 數。
        conversation_history : list[dict], optional
            對話歷史，格式為 [{"role": "user"/"assistant", "content": "..."}]

        Returns
        -------
        dict with keys:
            - content: LLM 回應
            - model: 使用的模型
            - tokens_in: 輸入 token 數
            - tokens_out: 輸出 token 數
            - mode: 偵測到的模式 (legal / general)
        """
        system_prompt = self.load_docs()
        model = model or os.getenv("ZHIYAN_MODEL") or DEFAULT_MODEL

        # 偵測是否為法律問題
        is_legal = self._detect_legal_mode(user_message)

        messages = [{"role": "system", "content": system_prompt}]

        if conversation_history:
            # 只保留最近的對話 history（避免超過 context window）
            recent = conversation_history[-6:] if len(conversation_history) > 6 else conversation_history
            messages.extend(recent)

        messages.append({"role": "user", "content": user_message})

        client = self._get_client()

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        result = {
            "content": response.choices[0].message.content or "",
            "model": model,
            "tokens_in": response.usage.prompt_tokens if response.usage else 0,
            "tokens_out": response.usage.completion_tokens if response.usage else 0,
            "mode": "legal" if is_legal else "general",
        }

        return result

    # ─── 模式偵測 ──────────────────────────────────────

    def _detect_legal_mode(self, text: str) -> bool:
        """判斷是否為法律相關問題。"""
        text_lower = text.lower()
        match_count = sum(1 for kw in LEGAL_KEYWORDS if kw in text)
        return match_count >= 1

    # ─── 任務分類（參考現有 router.py） ──────────────────

    def classify_task(self, user_message: str) -> str:
        """簡易任務分類：report / research / qc / general。"""
        text = user_message.lower()

        if any(w in text for w in ["查核", "驗證", "正確嗎", "對不對", "核對", "檢查"]):
            return "qc"
        elif any(w in text for w in ["研究", "分析", "比較", "趨勢", "實務", "學說"]):
            return "research"
        elif any(w in text for w in ["法條", "條文", "第", "條", "項", "款"]):
            return "report"
        else:
            return "general"
