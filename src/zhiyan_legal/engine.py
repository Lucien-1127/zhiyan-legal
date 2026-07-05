"""
Zhiyan AI Legal System — 統一 LLM 引擎 (v3.0)

Canonical engine for all LLM calls. Replaces runner.py (deprecated) and
backward-compatible with the original backend/engine.py ZhiyanEngine.

Key features:
  - Async-first with sync fallback (via asyncio.run)
  - httpx.AsyncClient connection pooling
  - Tenacity exponential backoff retry (3 attempts)
  - Multi-key rotation on 429 (from runner.py)
  - Gemini SDK support (optional)
  - Structured exception hierarchy
  - Post-LLM output validation
  - Lifespan-aware resource management
  - Health check / telemetry
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import httpx
from dotenv import load_dotenv
from openai import OpenAI, AsyncOpenAI, RateLimitError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

load_dotenv()

# ── GEMINI SDK (optional) ───────────────────────────
try:
    import google.genai as genai
    HAS_GEMINI_SDK = True
except ImportError:
    HAS_GEMINI_SDK = False

# ── Paths ────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # src/zhiyan_legal/ → project root
DOCS_DIR = PROJECT_ROOT / "docs"
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from zhiyan_legal.loader import compose, count_tokens  # noqa: E402
from zhiyan_legal.manifest import get_load_order  # noqa: E402

logger = logging.getLogger("zhiyan_legal.engine")

# ── Defaults ─────────────────────────────────────────
DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_API_BASE = "https://api.deepseek.com/v1"
_ENGINE_TIMEOUT = 60.0
_CONN_POOL_LIMITS = httpx.Limits(
    max_keepalive_connections=5,
    max_connections=10,
    keepalive_expiry=30.0,
)

# ── Exception hierarchy ──────────────────────────────


class EngineError(Exception):
    """Engine base exception."""


class LLMConnectionError(EngineError):
    """LLM API connection failure."""


class LLMTimeoutError(EngineError):
    """LLM API timeout."""


class LLMRateLimitError(EngineError):
    """LLM API rate limit (429)."""


class LLMResponseError(EngineError):
    """LLM API returned abnormal response."""


# ── Legal mode keywords ──────────────────────────────

LEGAL_KEYWORDS = [
    "法", "條", "判決", "判例", "訴訟", "律師", "法院",
    "起訴", "上訴", "刑法", "民法", "憲法", "行政法",
    "勞動法", "合約", "契約", "侵權", "損害賠償",
    "公然侮辱", "誹謗", "詐欺", "侵占", "竊盜",
    "商標", "專利", "著作權", "股東", "公司",
    "離婚", "監護", "遺產", "繼承", "車禍",
    "存證信函", "支付命令", "假扣押", "假處分",
]

# ── Output validation patterns (from runner.py) ──────

_TASK_VALIDATION = {
    "QC": {
        "patterns": ["條款", "條文", "第.", "違反", "缺失", "風險"],
        "hint": "QC 輸出應指出具體條款與風險點",
    },
    "LITIGATION": {
        "patterns": ["原告", "被告", "主張", "抗辯", "攻防", "策略"],
        "hint": "訴訟分析應涵蓋雙方立場與攻防策略",
    },
    "REPORT": {
        "patterns": ["摘要", "結論", "建議", "分析"],
        "hint": "報告應包含摘要、分析、結論三層結構",
    },
    "RESEARCH": {
        "patterns": ["依據", "見解", "實務", "判決"],
        "hint": "研究應附法規或判決依據",
    },
    "CONSULTANT": {
        "patterns": ["方案", "選項", "比較", "利弊", "風險"],
        "hint": "顧問分析應比較不同選項的優劣",
    },
    "SAFETY": {
        "patterns": ["協助", "資源", "專線", "求助", "諮詢"],
        "hint": "安全相關回應應提供求助資源",
    },
    "SIMULATION": {
        "patterns": ["假設", "模擬", "推演", "⚠"],
        "hint": "模擬模式應標示免責聲明",
    },
}


# ── Data classes ─────────────────────────────────────


@dataclass
class QueryResult:
    """LLM query result."""
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
    """Engine configuration (injectable)."""
    api_base: str = field(default_factory=lambda: os.getenv(
        "ZHIYAN_API_BASE_URL", DEFAULT_API_BASE))
    api_key: str = ""
    default_model: str = field(default_factory=lambda: os.getenv(
        "ZHIYAN_MODEL", DEFAULT_MODEL))
    timeout: float = _ENGINE_TIMEOUT
    max_retries: int = 3
    max_conversation_turns: int = 10


# ── API key discovery ────────────────────────────────


def discover_api_key() -> str:
    """Multi-layer API key discovery (env vars → Hermes profile).
    
    Priority: DEEPSEEK > OPENROUTER > OPENAI > GEMINI > ZHIYAN
    (ZHIYAN_API_KEY is lowest priority to avoid stale keys overriding the active one.)
    """
    # Check well-known keys first (most likely to be active)
    hermes_keys = (
        "DEEPSEEK_API_KEY", "OPENROUTER_API_KEY",
        "OPENAI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY",
    )
    for var in hermes_keys:
        val = os.getenv(var)
        if val:
            return val
    # ZHIYAN_API_KEY last (often stale/misconfigured)
    zhiyan_val = os.getenv("ZHIYAN_API_KEY")
    if zhiyan_val:
        return zhiyan_val
    # Fallback: load Hermes profile .env
    hermes_env = Path.home() / ".hermes" / "profiles" / "lenien-gcp" / ".env"
    if hermes_env.exists():
        load_dotenv(hermes_env)
        for var in hermes_keys:
            val = os.getenv(var)
            if val:
                return val
    return ""


def _get_gemini_key() -> str:
    """Get Gemini API key from env or Hermes config."""
    key = os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")
    if key:
        return key
    cfg_path = os.path.expanduser("~/.hermes/profiles/lenien-gcp/config.yaml")
    try:
        with open(cfg_path, encoding="utf-8") as _f:
            _in_gemini = False
            for _line in _f:
                if "gemini:" in _line:
                    _in_gemini = True
                elif _in_gemini and "api_key:" in _line:
                    return _line.split("api_key:", 1)[1].strip()
                elif _in_gemini and _line.strip() and not _line.startswith(" ") and ":" in _line:
                    _in_gemini = False

        import subprocess
        out = subprocess.run(
            ["grep", "-A1", "gemini:", cfg_path],
            capture_output=True, text=True, timeout=5,
        ).stdout
        for line in out.split("\n"):
            if "api_key" in line:
                return line.split("api_key:")[1].strip()
    except Exception:
        pass
    return ""


# ── Retry decorator factory ──────────────────────────


def _build_retry_decorator():
    """Build tenacity retry decorator for LLM API calls."""
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


# ── Output validation ────────────────────────────────


def validate_output(result: str, task: str = "QC") -> str:
    """Post-LLM output validation.

    Checks output for task-essential keywords. If core patterns are missing,
    appends a structured advisory rather than modifying original content.
    """
    if not result:
        return result

    checks = _TASK_VALIDATION.get(task)
    if not checks:
        return result

    matched = sum(1 for p in checks["patterns"] if re.search(p, result))

    matched = sum(1 for p in checks["patterns"] if p in result)
    threshold = max(1, len(checks["patterns"]) // 3)

    if matched < threshold:
        advisory = (
            f"\n\n---\n"
            f"⚠️ 【輸出校驗警示】此 {task} 輸出未偵測到關鍵要素\n"
            f"建議補充：{checks['hint']}\n"
            f"請確認上述分析是否完整，必要時補充論述。"
        )
        logger.warning(
            "Output validation: task=%s, matched=%d/%d patterns, threshold=%d",
            task, matched, len(checks["patterns"]), threshold,
        )
        return result + advisory

    logger.info(
        "Output validation passed: task=%s, matched=%d/%d patterns",
        task, matched, len(checks["patterns"]),
    )
    return result


# ═══════════════════════════════════════════════════════
# ZhiyanEngine — 統一 LLM 引擎
# ═══════════════════════════════════════════════════════

class ZhiyanEngine:
    """統一的非同步 LLM 引擎 — 連接池 + retry + key 輪換 + 輸出驗證。

    Usage:
        engine = ZhiyanEngine()
        await engine.startup()
        result = await engine.query_async("民法第184條是什麼?")
        await engine.shutdown()
    """

    def __init__(self, config: Optional[EngineConfig] = None):
        self._config = config or EngineConfig()
        if not self._config.api_key:
            self._config.api_key = discover_api_key()

        # Document cache
        self._system_prompt: Optional[str] = None
        self._docs_loaded = False
        self._doc_cache: dict[str, str] = {}  # task → composed prompt

        # Resources
        self._http_client: Optional[httpx.AsyncClient] = None
        self._async_openai: Optional[AsyncOpenAI] = None
        self._sync_openai: Optional[OpenAI] = None
        self._initialized = False

    # ── Lifecycle ────────────────────────────────────

    async def startup(self):
        """Initialize resources (called by FastAPI lifespan or manually)."""
        if self._initialized:
            return

        self._http_client = httpx.AsyncClient(
            base_url=self._config.api_base,
            timeout=httpx.Timeout(self._config.timeout),
            limits=_CONN_POOL_LIMITS,
        )
        self._async_openai = AsyncOpenAI(
            base_url=self._config.api_base,
            api_key=self._config.api_key,
            http_client=self._http_client,
        )
        self._sync_openai = OpenAI(
            base_url=self._config.api_base,
            api_key=self._config.api_key,
        )

        self.load_docs()

        self._initialized = True
        logger.info(
            "ZhiyanEngine 初始化完成 | api_base=%s | model=%s | pool=%s",
            self._config.api_base, self._config.default_model,
            _CONN_POOL_LIMITS,
        )

    async def shutdown(self):
        """Release resources."""
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

    # ── Document management ──────────────────────────

    def load_docs(self, task: str = "QC") -> str:
        """Load task-specific docs via manifest.get_load_order() with per-task caching."""
        if task in self._doc_cache:
            return self._doc_cache[task]

        try:
            file_paths = get_load_order(task)
        except Exception as e:
            logger.warning("get_load_order(%s) failed: %s — falling back to glob", task, e)
            file_paths = [
                str(f)
                for cat in ["10_核心控制層", "20_模式與引用層", "40_模組與人格層"]
                for f in sorted((DOCS_DIR / cat).glob("*.md"))
                if (DOCS_DIR / cat).exists()
            ]

        composed = compose(file_paths)
        self._doc_cache[task] = composed

        if not self._system_prompt:
            self._system_prompt = composed
            self._docs_loaded = True

        logger.info("已載入 task=%s: %d 字元", task, len(composed))
        return composed

    def reload(self):
        """Force reload documents (clears all task caches)."""
        self._system_prompt = None
        self._docs_loaded = False
        self._doc_cache.clear()

    def load_docs(self) -> str:
        """Load docs/ spec documents into a composed system prompt."""
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
        logger.info("已載入 %d 份規格文件，共 %d 字元",
                    len(parts), len(self._system_prompt))
        return self._system_prompt

    def reload(self):
        """Force reload documents."""
        self._system_prompt = None
        self._docs_loaded = False
        return self.load_docs()

    # ── Core async query ─────────────────────────────

    async def query_async(
        self,
        user_message: str,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        conversation_history: Optional[list[dict]] = None,
        request_id: Optional[str] = None,
        task: str = "QC",
    ) -> QueryResult:
        """Async LLM query with multi-key rotation on 429."""
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

        # Multi-key rotation (from runner.py)
        max_key_attempts = 3
        last_error = None

        for attempt in range(1, max_key_attempts + 1):
            try:
                client = self._get_client(attempt)
                result = await self._call_llm(
                    client=client, model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    rid=rid,
                )
                # Validate
                result.content = validate_output(result.content, task)
                result.mode = "legal" if is_legal else "general"
                result.mode_label = "⚖️ 法律分析模式" if is_legal else "💬 一般對話模式"
                result.request_id = rid
                return result

            except (RateLimitError, LLMRateLimitError) as e:
                last_error = e
                next_key = attempt + 1
                if attempt < max_key_attempts and os.getenv(f"ZHIYAN_API_KEY_{next_key}"):
                    wait = 1.0
                    logger.warning(
                        "Rate limited on key=%d (429). Waiting %.1fs then trying key=%d ...",
                        attempt, wait, next_key,
                    )
                    await asyncio.sleep(wait)
                    continue
                else:
                    logger.error("Rate limited on all available keys: %s", e)
                    # Fallback to sync client
                    try:
                        result = await self._call_llm_sync_fallback(
                            model=model, messages=messages,
                            temperature=temperature, max_tokens=max_tokens, rid=rid,
                        )
                        result.mode = "legal" if is_legal else "general"
                        result.mode_label = "⚖️ 法律分析模式" if is_legal else "💬 一般對話模式"
                        result.request_id = rid
                        return result
                    except Exception as sync_e:
                        last_error = sync_e
                    break

            except Exception as e:
                logger.error("API call failed (key=%d): %s", attempt, e, exc_info=True)
                last_error = e
                if attempt == max_key_attempts:
                    break

        # All keys exhausted
        logger.error("All API keys exhausted. Last error: %s", last_error)
        return QueryResult(
            content="", model=model,
            mode="legal" if is_legal else "general",
            tokens_in=0, tokens_out=0,
            request_id=rid,
            error=str(last_error) if last_error else "All API keys exhausted",
        )

    # ── Sync query (backward compat) ────────────────

    def query(
        self,
        user_message: str,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        conversation_history: Optional[list[dict]] = None,
        task: str = "QC",
    ) -> dict:
        """Synchronous query wrapper (backward-compatible with runner.py interface).

        Returns dict with keys: content, model, tokens_in, tokens_out, mode.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # asyncio.run() cannot be called from a running event loop — use sync client
            if not self._sync_openai:
                self._sync_openai = OpenAI(
                    base_url=self._config.api_base,
                    api_key=self._config.api_key,
                )
            model_name = model or self._config.default_model
            msgs = list(conversation_history or [])
            msgs.append({"role": "user", "content": user_message})
            resp = self._sync_openai.chat.completions.create(
                model=model_name, messages=msgs,
                temperature=temperature, max_tokens=max_tokens,
            )
            content = resp.choices[0].message.content or ""
            usage = resp.usage
            return {
                "content": content,
                "model": model_name,
                "tokens_in": usage.prompt_tokens if usage else 0,
                "tokens_out": usage.completion_tokens if usage else 0,
                "mode": "legal",
            }

        result = asyncio.run(self.query_async(

        coro = self.query_async(
            user_message=user_message,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            conversation_history=conversation_history,
            task=task,
        ))

        )

        if loop and loop.is_running():
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

    # ── Internal: API client per key ────────────────

    def _get_client(self, key_num: int = 1) -> AsyncOpenAI:
        """Get an AsyncOpenAI client using key_num (for key rotation)."""
        if key_num == 1:
            api_key = self._config.api_key
        else:
            api_key = os.getenv(f"ZHIYAN_API_KEY_{key_num}", "")

        if not api_key and key_num == 1:
            for fallback in ("OPENAI_API_KEY", "OPENROUTER_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
                val = os.getenv(fallback)
                if val:
                    api_key = val
                    break

        if not api_key and key_num == 1:
            raise RuntimeError("API key not found")

        return AsyncOpenAI(
            base_url=self._config.api_base,
            api_key=api_key,
            http_client=self._http_client,
        )

    # ── Internal: LLM call ──────────────────────────

    @_build_retry_decorator()
    async def _call_llm(
        self,
        client: AsyncOpenAI,
        model: str,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        rid: str,
    ) -> QueryResult:
        """Async LLM call with retry + timeout."""
        try:
            async with asyncio.timeout(self._config.timeout):
                response = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
        except asyncio.TimeoutError:
            raise LLMTimeoutError(f"LLM API 逾時 ({self._config.timeout}s)") from None
        except httpx.TimeoutException as e:
            raise LLMTimeoutError(f"HTTP 連線逾時: {e}") from e
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise LLMRateLimitError(f"Rate limit (429): {e}") from e
            raise LLMResponseError(f"HTTP {e.response.status_code}: {e}") from e
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
            content=content, model=model,
            mode="legal",   # overwritten by caller
            tokens_in=tokens_in, tokens_out=tokens_out,
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
        """Sync OpenAI client fallback (when async rate-limited)."""
        loop = asyncio.get_running_loop()

        def _sync_call():
            return self._sync_openai.chat.completions.create(
                model=model, messages=messages,
                temperature=temperature, max_tokens=max_tokens,
            )

        try:
            response = await asyncio.wait_for(
                loop.run_in_executor(None, _sync_call),
                timeout=self._config.timeout,
            )
        except asyncio.TimeoutError:
            raise LLMTimeoutError(f"Sync fallback 逾時 ({self._config.timeout}s)") from None
        except Exception as e:
            raise LLMConnectionError(f"Sync fallback 失敗: {e}") from e

        choice = response.choices[0]
        content = choice.message.content or ""
        usage = response.usage

        return QueryResult(
            content=content, model=model, mode="legal",
            tokens_in=usage.prompt_tokens if usage else 0,
            tokens_out=usage.completion_tokens if usage else 0,
            request_id=rid,
        )

    # ── Gemini path (from runner.py) ────────────────

    async def query_gemini(
        self,
        system_prompt: str,
        user_message: str,
        model: str = "gemini-2.5-flash",
        temperature: float = 0.3,
        max_tokens: int = 4096,
        task: str = "QC",
    ) -> str:
        """Run via Google GenAI SDK."""
        if not HAS_GEMINI_SDK:
            raise RuntimeError("google.genai SDK not installed. Run: pip install google-genai")

        api_key = _get_gemini_key()
        if not api_key:
            raise RuntimeError("Gemini API key not found.")

        gemini_model = model.removeprefix("models/")
        logger.info("Calling Gemini %s (temp=%.1f, max=%d)", gemini_model, temperature, max_tokens)

        try:
            response = genai.Client(api_key=api_key).models.generate_content(
                model=gemini_model,
                contents=user_message,
                config={
                    "system_instruction": system_prompt,
                    "max_output_tokens": max_tokens,
                    "temperature": temperature,
                },
            )
            content = response.text or ""
            return validate_output(content, task)
        except Exception as e:
            logger.error("Gemini API call failed: %s", e, exc_info=True)
            return ""

    # ── Mode detection ──────────────────────────────

    def _detect_legal_mode(self, text: str) -> bool:
        """Detect if the input is law-related."""
        return sum(1 for kw in LEGAL_KEYWORDS if kw in text) >= 1

    # ── Health check ────────────────────────────────

    async def health_check(self) -> dict[str, Any]:
        """Engine health status."""
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

    # ── Internal: one-shot call (refactored from run()) ──

    async def _run_one_shot(
        self,
        model_name: str,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        task: str,
    ) -> str:
        """One-shot LLM call with multi-key rotation."""
        max_key_attempts = 3
        last_error = None

        for attempt in range(1, max_key_attempts + 1):
            try:
                client = self._get_client(attempt)
                response = await client.chat.completions.create(
                    model=model_name, messages=messages,
                    temperature=temperature, max_tokens=max_tokens,
                )
                content = response.choices[0].message.content or ""
                logger.info("_run_one_shot succeeded (key=%d, %d chars)", attempt, len(content))
                return validate_output(content, task)
            except (RateLimitError, LLMRateLimitError) as e:
                last_error = e
                if attempt < max_key_attempts and os.getenv(f"ZHIYAN_API_KEY_{attempt + 1}"):
                    await asyncio.sleep(1)
                    continue
                logger.error("Rate limited on all keys: %s", e)
                break
            except Exception as e:
                logger.error("_run_one_shot failed (key=%d): %s", attempt, e)
                last_error = e
                raise

        logger.error("_run_one_shot all keys exhausted: %s", last_error)
        return ""

    # ── Convenience: one-shot sync call (compat with runner.run_llm) ──

    def run(
        self,
        system_prompt: str,
        user_message: str,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        dry_run: bool = False,
        task: str = "QC",
    ) -> str:
        """One-shot synchronous call — drop-in replacement for runner.run_llm().

        This bypasses the doc-loading path and uses the provided system_prompt directly.
        """
        if dry_run:
            print("=" * 60)
            print("🔍 DRY RUN — No API call will be made")
            print("=" * 60)
            print(f"\n📋 Model:      {model or self._config.default_model}")
            print(f"📋 Provider:   {self._config.api_base}")
            print(f"📋 System PMT: {len(system_prompt):,} chars ({count_tokens(system_prompt):,} tokens)")
            print(f"📋 User MSG:   {len(user_message):,} chars")
            print("=" * 60)
            print(system_prompt[:5000] + ("\n… (truncated)" if len(system_prompt) > 5000 else ""))
            print("\n✅ Dry-run complete — 0 tokens consumed.")
            return ""

        provider = os.getenv("ZHIYAN_PROVIDER", "openai").lower()
        if provider == "gemini":
            # Use Gemini SDK
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(
                    self.query_gemini(system_prompt, user_message, model or "gemini-2.5-flash",
                                      temperature, max_tokens, task)
                )
            finally:
                loop.close()

        # OpenAI-compatible path via async (reuse connection pool)
        model_name = model or self._config.default_model
        messages = [{"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}]

        try:
            existing_loop = asyncio.get_running_loop()
        except RuntimeError:
            existing_loop = None

        if existing_loop:
            # run_until_complete() cannot be called on a running event loop — use sync client
            if not self._sync_openai:
                self._sync_openai = OpenAI(
                    base_url=self._config.api_base,
                    api_key=self._config.api_key,
                )
            resp = self._sync_openai.chat.completions.create(
                model=model_name, messages=messages,
                temperature=temperature, max_tokens=max_tokens,
            )
            content = resp.choices[0].message.content or ""
            return validate_output(content, task)

            # Already in an event loop — run directly
            return existing_loop.run_until_complete(
                self._run_one_shot(model_name, messages, temperature, max_tokens, task)
            )

        # No running loop — create one
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(
                self._run_one_shot(model_name, messages, temperature, max_tokens, task)
            )
        finally:
            loop.close()
