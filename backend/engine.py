"""
智研 SaaS 版 — 法律引擎封裝層 (v2.0)

Async-first LLM client with connection pooling, retry, timeout.
Supports both async (recommended) and sync (backward compat) modes.

Key improvements over v1:
  - httpx.AsyncClient connection pool (reuse, not per-call create)
  - Tenacity exponential backoff retry (3 attempts)
  - asyncio.timeout() protection
  - Proper exception hierarchy
  - Lifespan-aware resource management
  - Request ID tracing
  - Structured error logging
"""

from __future__ import annotations

import os
import sys
import uuid
import logging
import asyncio
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass, field

from dotenv import load_dotenv
load_dotenv()  # 載入 .env（獨立使用時）

import httpx
from openai import OpenAI, AsyncOpenAI
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

logger = logging.getLogger(__name__)

# ─── 路徑設定 ────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# ─── 預設值 ──────────────────────────────────────────────
DEFAULT_MODEL = "deepseek-chat"
DEFAULT_API_BASE = "https://api.deepseek.com/v1"
_DEFAULT_TIMEOUT = 60.0        # LLM API 呼叫 timeout
_CONN_POOL_LIMITS = httpx.Limits(
    max_keepalive_connections=5,
    max_connections=10,
    keepalive_expiry=30.0,
)

# ─── 自訂例外 ─────────────────────────────────────────────


class EngineError(Exception):
    """引擎基礎例外"""


class LLMConnectionError(EngineError):
    """LLM API 連線失敗"""


class LLMTimeoutError(EngineError):
    """LLM API 逾時"""


class LLMRateLimitError(EngineError):
    """LLM API rate limit 觸發 (429)"""


class LLMResponseError(EngineError):
    """LLM API 回傳異常"""


# ─── 法律模式關鍵字 ────────────────────────────────────

LEGAL_KEYWORDS = [
    "法", "條", "判決", "判例", "訴訟", "律師", "法院",
    "起訴", "上訴", "刑法", "民法", "憲法", "行政法",
    "勞動法", "合約", "契約", "侵權", "損害賠償",
    "公然侮辱", "誹謗", "詐欺", "侵占", "竊盜",
    "商標", "專利", "著作權", "股東", "公司",
    "離婚", "監護", "遺產", "繼承", "車禍",
    "存證信函", "支付命令", "假扣押", "假處分",
]


# ─── 資料類別 ───────────────────────────────────────────

@dataclass
class QueryResult:
    """LLM 查詢結果"""
    content: str
    model: str
    mode: str          # "legal" | "general"
    tokens_in: int
    tokens_out: int
    mode_label: str = "💬 一般對話模式"
    request_id: str = ""
    error: Optional[str] = None


@dataclass
class EngineConfig:
    """引擎設定（可 inject）"""
    api_base: str = field(default_factory=lambda: os.getenv(
        "ZHIYAN_API_BASE_URL", DEFAULT_API_BASE))
    api_key: str = ""
    default_model: str = field(default_factory=lambda: os.getenv(
        "ZHIYAN_MODEL", DEFAULT_MODEL))
    timeout: float = _DEFAULT_TIMEOUT
    max_retries: int = 3
    max_conversation_turns: int = 10  # 保留最近的對話輪數


# ═══════════════════════════════════════════════════════
# ZhiyanEngine — 非同步 LLM 引擎
# ═══════════════════════════════════════════════════════

def _discover_api_key() -> str:
    """多層次 API key 發現（彈性降級）"""
    for var in ("ZHIYAN_API_KEY", "DEEPSEEK_API_KEY",
                "OPENAI_API_KEY", "OPENROUTER_API_KEY",
                "GEMINI_API_KEY", "GOOGLE_API_KEY"):
        val = os.getenv(var)
        if val:
            return val
    return ""


def _build_retry_decorator():
    """建立 tenacity retry 裝飾器（LLM API 專用）"""
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((
            httpx.TimeoutException,
            httpx.ConnectError,
            httpx.RemoteProtocolError,
            httpx.HTTPStatusError,
        )),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )


class ZhiyanEngine:
    """非同步 LLM 引擎 — 連接池 + retry + timeout"""

    def __init__(self, config: Optional[EngineConfig] = None):
        self._config = config or EngineConfig()
        if not self._config.api_key:
            self._config.api_key = _discover_api_key()

        # ── 文件快取 ──
        self._system_prompt: Optional[str] = None
        self._docs_loaded = False

        # ── 資源：生命週期管理 ──
        self._http_client: Optional[httpx.AsyncClient] = None
        self._async_openai: Optional[AsyncOpenAI] = None
        self._sync_openai: Optional[OpenAI] = None
        self._initialized = False

    # ─── 生命週期 ────────────────────────────────────────

    async def startup(self):
        """初始化資源（FastAPI lifespan 呼叫）"""
        if self._initialized:
            return

        # HTTPX 連接池
        self._http_client = httpx.AsyncClient(
            base_url=self._config.api_base,
            timeout=httpx.Timeout(self._config.timeout),
            limits=_CONN_POOL_LIMITS,
        )

        # Async OpenAI client（共用 httpx client）
        self._async_openai = AsyncOpenAI(
            base_url=self._config.api_base,
            api_key=self._config.api_key,
            http_client=self._http_client,
        )

        # Sync OpenAI client（fallback）
        self._sync_openai = OpenAI(
            base_url=self._config.api_base,
            api_key=self._config.api_key,
        )

        # 預載文件
        self.load_docs()

        self._initialized = True
        logger.info(
            "ZhiyanEngine 初始化完成 | api_base=%s | model=%s | pool=%s",
            self._config.api_base, self._config.default_model,
            _CONN_POOL_LIMITS,
        )

    async def shutdown(self):
        """釋放資源（FastAPI lifespan 呼叫）"""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        self._async_openai = None
        self._sync_openai = None
        self._initialized = False
        logger.info("ZhiyanEngine 資源已釋放")

    @property
    def is_ready(self) -> bool:
        return self._initialized

    # ─── 文件管理 ────────────────────────────────────────

    def load_docs(self) -> str:
        """載入 docs/ 規格文件，組合成 system prompt"""
        if self._system_prompt and self._docs_loaded:
            return self._system_prompt

        parts: list[str] = []
        load_order = [
            "10_核心控制層",
            "20_模式與引用層",
            "40_模組與人格層",
        ]

        for category in load_order:
            cat_dir = DOCS_DIR / category
            if not cat_dir.exists():
                logger.warning("目錄不存在: %s", cat_dir)
                continue
            files = sorted(cat_dir.glob("*.md"))
            for f in files:
                try:
                    content = f.read_text(encoding="utf-8")
                    parts.append(f"<!-- {f.name} -->\n{content}")
                except Exception as e:
                    logger.error("讀取失敗 %s: %s", f.name, e)

        self._system_prompt = "\n\n---\n\n".join(parts)
        self._docs_loaded = True
        logger.info(
            "已載入 %d 份規格文件，共 %d 字元",
            len(parts), len(self._system_prompt),
        )
        return self._system_prompt

    def reload(self):
        """強制重新載入文件"""
        self._system_prompt = None
        self._docs_loaded = False
        return self.load_docs()

    # ─── 核心查詢（async） ────────────────────────────────

    async def query_async(
        self,
        user_message: str,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        conversation_history: Optional[list[dict]] = None,
        request_id: Optional[str] = None,
    ) -> QueryResult:
        """非同步 LLM 查詢（主要路徑）

        Parameters
        ----------
        user_message : str
            使用者問題
        model : str, optional
            模型名稱
        temperature : float
            生成溫度
        max_tokens : int
            最大輸出 tokens
        conversation_history : list[dict], optional
            對話歷史
        request_id : str, optional
            請求追蹤 ID（自動產生）

        Returns
        -------
        QueryResult
        """
        if not self._initialized:
            await self.startup()

        rid = request_id or uuid.uuid4().hex[:12]
        model = model or self._config.default_model

        system_prompt = self.load_docs()
        is_legal = self._detect_legal_mode(user_message)

        messages = [{"role": "system", "content": system_prompt}]
        if conversation_history:
            recent = (
                conversation_history[-self._config.max_conversation_turns * 2:]
                if len(conversation_history) > self._config.max_conversation_turns * 2
                else conversation_history
            )
            messages.extend(recent)
        messages.append({"role": "user", "content": user_message})

        try:
            result = await self._call_llm(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                rid=rid,
            )
        except LLMRateLimitError:
            logger.warning("[%s] Rate limit 觸發，回退 sync client", rid)
            result = await self._call_llm_sync_fallback(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                rid=rid,
            )

        result.mode = "legal" if is_legal else "general"
        result.mode_label = "⚖️ 法律分析模式" if is_legal else "💬 一般對話模式"
        result.request_id = rid
        return result

    # ─── 同步查詢（backward compat） ──────────────────────

    def query(
        self,
        user_message: str,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        conversation_history: Optional[list[dict]] = None,
    ) -> dict:
        """同步查詢（相容舊版，內部跑 async event loop）"""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        coro = self.query_async(
            user_message=user_message,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            conversation_history=conversation_history,
        )

        if loop and loop.is_running():
            # 已在 event loop 中 → 建立新 loop 執行
            result = asyncio.run(coro)
        else:
            result = asyncio.run(coro)

        return {
            "content": result.content,
            "model": result.model,
            "tokens_in": result.tokens_in,
            "tokens_out": result.tokens_out,
            "mode": result.mode,
        }

    # ─── LLM 呼叫實作 ────────────────────────────────────

    @_build_retry_decorator()
    async def _call_llm(
        self,
        model: str,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        rid: str,
    ) -> QueryResult:
        """非同步 LLM 呼叫（附 retry + timeout）"""
        client = self._async_openai
        if not client:
            raise LLMConnectionError("AsyncOpenAI client 未初始化")

        try:
            async with asyncio.timeout(self._config.timeout):
                response = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
        except asyncio.TimeoutError:
            raise LLMTimeoutError(
                f"LLM API 逾時 ({self._config.timeout}s)"
            ) from None
        except httpx.TimeoutException as e:
            raise LLMTimeoutError(f"HTTP 連線逾時: {e}") from e
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise LLMRateLimitError(f"Rate limit (429): {e}") from e
            raise LLMResponseError(
                f"HTTP {e.response.status_code}: {e}"
            ) from e
        except httpx.TransportError as e:
            raise LLMConnectionError(f"傳輸錯誤: {e}") from e

        try:
            choice = response.choices[0]
            content = choice.message.content or ""
            usage = response.usage
            tokens_in = usage.prompt_tokens if usage else 0
            tokens_out = usage.completion_tokens if usage else 0
        except (IndexError, AttributeError) as e:
            raise LLMResponseError(f"回傳格式異常: {e}") from e

        return QueryResult(
            content=content,
            model=model,
            mode="legal",   # 由呼叫方覆寫
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            request_id=rid,
        )

    async def _call_llm_sync_fallback(
        self,
        model: str,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        rid: str,
    ) -> QueryResult:
        """sync OpenAI client fallback（async rate limit 時）"""
        client = self._sync_openai
        if not client:
            raise LLMConnectionError("SyncOpenAI client 未初始化")

        loop = asyncio.get_running_loop()

        def _sync_call():
            return client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

        try:
            response = await asyncio.wait_for(
                loop.run_in_executor(None, _sync_call),
                timeout=self._config.timeout,
            )
        except asyncio.TimeoutError:
            raise LLMTimeoutError(
                f"Sync fallback 逾時 ({self._config.timeout}s)"
            ) from None
        except Exception as e:
            raise LLMConnectionError(f"Sync fallback 失敗: {e}") from e

        choice = response.choices[0]
        content = choice.message.content or ""
        usage = response.usage

        return QueryResult(
            content=content,
            model=model,
            mode="legal",
            tokens_in=usage.prompt_tokens if usage else 0,
            tokens_out=usage.completion_tokens if usage else 0,
            request_id=rid,
        )

    # ─── 模式偵測 ────────────────────────────────────────

    def _detect_legal_mode(self, text: str) -> bool:
        """判斷是否為法律相關問題"""
        match_count = sum(1 for kw in LEGAL_KEYWORDS if kw in text)
        return match_count >= 1

    # ─── 健康檢查 ────────────────────────────────────────

    async def health_check(self) -> dict[str, Any]:
        """引擎健康狀態"""
        return {
            "ready": self._initialized,
            "docs_loaded": self._docs_loaded,
            "docs_count": len(list(DOCS_DIR.rglob("*.md"))) if DOCS_DIR.exists() else 0,
            "model": self._config.default_model,
            "api_base": self._config.api_base,
            "pool_limits": {
                "max_connections": _CONN_POOL_LIMITS.max_connections,
                "max_keepalive": _CONN_POOL_LIMITS.max_keepalive_connections,
            },
        }
