"""Backward-compatible facade for the canonical application engine.

Historically this module contained its own OpenAI clients, key rotation,
document cache, and several competing query paths.  It now contains only
compatibility data types/helpers and delegates execution to
``ZhiyanApplicationEngine``.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from dotenv import load_dotenv

from .application import ZhiyanApplicationEngine
from .domain import ExecutionContext, TaskMode
from .providers import ProviderConfig, ProviderRegistry
from .loader import compose
from .manifest import get_load_order

load_dotenv()

logger = logging.getLogger("zhiyan_legal.engine")

DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_API_BASE = "https://api.deepseek.com/v1"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = PROJECT_ROOT / "docs"


class EngineError(Exception):
    """Compatibility base exception."""


class LLMConnectionError(EngineError):
    """Compatibility connection exception."""


class LLMTimeoutError(EngineError):
    """Compatibility timeout exception."""


class LLMRateLimitError(EngineError):
    """Compatibility rate-limit exception."""


class LLMResponseError(EngineError):
    """Compatibility malformed-response exception."""


@dataclass
class QueryResult:
    """Historical query result shape retained for callers of ``query_async``."""

    content: str
    model: str
    mode: str
    tokens_in: int
    tokens_out: int
    mode_label: str = "💬 一般對話模式"
    request_id: str = ""
    error: Optional[str] = None


@dataclass
class EngineConfig:
    """Compatibility configuration used to build one provider registry."""

    api_base: str = field(
        default_factory=lambda: os.getenv("ZHIYAN_API_BASE_URL", DEFAULT_API_BASE)
    )
    api_key: str = ""
    default_model: str = field(
        default_factory=lambda: os.getenv("ZHIYAN_MODEL", DEFAULT_MODEL)
    )
    timeout: float = 60.0
    max_retries: int = 3
    max_conversation_turns: int = 10


_TASK_VALIDATION = {
    "QC": (["條款", "條文", "第.", "違反", "缺失", "風險"], "QC 輸出應指出具體條款與風險點"),
    "LITIGATION": (["原告", "被告", "主張", "抗辯", "攻防", "策略"], "訴訟分析應涵蓋雙方立場與攻防策略"),
    "REPORT": (["摘要", "結論", "建議", "分析"], "報告應包含摘要、分析、結論三層結構"),
    "RESEARCH": (["依據", "見解", "實務", "判決"], "研究應附法規或判決依據"),
    "CONSULTANT": (["方案", "選項", "比較", "利弊", "風險"], "顧問分析應比較不同選項的優劣"),
    "SAFETY": (["協助", "資源", "專線", "求助", "諮詢"], "安全相關回應應提供求助資源"),
    "SIMULATION": (["假設", "模擬", "推演", "⚠"], "模擬模式應標示免責聲明"),
}


def validate_output(result: str, task: str = "QC") -> str:
    """Append a warning when a legacy task output lacks core markers."""

    if not result or task not in _TASK_VALIDATION:
        return result
    patterns, hint = _TASK_VALIDATION[task]
    matched = sum(1 for pattern in patterns if re.search(pattern, result))
    if matched >= max(1, len(patterns) // 3):
        return result
    return (
        f"{result}\n\n---\n⚠️ 【輸出校驗警示】此 {task} 輸出未偵測到關鍵要素\n"
        f"建議補充：{hint}\n請確認上述分析是否完整，必要時補充論述。"
    )


def discover_api_key() -> str:
    """Compatibility lookup for explicit standard environment variables only."""

    for name in (
        "DEEPSEEK_API_KEY",
        "OPENROUTER_API_KEY",
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "ZHIYAN_API_KEY",
    ):
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def run_llm(prompt: str = "", **kwargs: Any) -> str:
    """Historical convenience API routed through ``ZhiyanEngine``."""

    engine = ZhiyanEngine()
    result = engine.query(
        kwargs.get("user_message", prompt),
        model=kwargs.get("model"),
        temperature=kwargs.get("temperature", 0.3),
        max_tokens=kwargs.get("max_tokens", 4096),
        conversation_history=kwargs.get("conversation_history"),
        task=kwargs.get("task", "QC"),
    )
    return result.get("content", "")


class ZhiyanEngine:
    """Compatibility facade preserving ``query``/``query_async`` signatures."""

    def __init__(
        self,
        config: Optional[EngineConfig] = None,
        application_engine: ZhiyanApplicationEngine | None = None,
    ) -> None:
        self._config = config or EngineConfig()
        if not self._config.api_key:
            self._config.api_key = discover_api_key()
        self._application = application_engine or ZhiyanApplicationEngine(
            provider_registry=self._provider_registry()
        )
        self._doc_cache: dict[str, str] = {}
        self._system_prompt: str | None = None
        self._initialized = False

    def _provider_registry(self) -> ProviderRegistry:
        configured = ProviderRegistry.from_env()
        if len(configured) or not self._config.api_key:
            return configured
        provider_name = os.getenv("ZHIYAN_PROVIDER", "deepseek").lower()
        if provider_name not in {"openai", "deepseek", "gemini", "openrouter"}:
            provider_name = "openai"
        config = ProviderConfig(
            name=provider_name,
            base_url=self._config.api_base,
            api_key=self._config.api_key,
            default_model=self._config.default_model,
            priority=0,
            timeout_seconds=self._config.timeout,
        )
        return ProviderRegistry([config])

    async def startup(self) -> None:
        self._initialized = True

    async def shutdown(self) -> None:
        self._initialized = False

    @property
    def is_ready(self) -> bool:
        return self._initialized

    def load_docs(self, task: str = "QC") -> str:
        """Load and cache one task-specific prompt; this method is unique."""

        if task in self._doc_cache:
            return self._doc_cache[task]
        try:
            prompt = compose(get_load_order(task))
        except Exception as exc:
            logger.warning("unable to load task docs %s: %s", task, exc)
            prompt = ""
        self._doc_cache[task] = prompt
        if self._system_prompt is None:
            self._system_prompt = prompt
        return prompt

    def reload(self) -> str:
        """Clear document state and return the freshly loaded default prompt."""

        self._doc_cache.clear()
        self._system_prompt = None
        return self.load_docs()

    async def query_async(
        self,
        user_message: str,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        conversation_history: Optional[list[dict]] = None,
        request_id: Optional[str] = None,
        task: str = "QC",
        context: ExecutionContext | None = None,
    ) -> QueryResult:
        """Execute through the application engine after history validation."""

        execution_context = context or ExecutionContext(
            execution_id=request_id or uuid4().hex[:12],
            task_mode=self._task_mode(task),
            user_goal=user_message,
        )
        _, meta, content = await self._application.query_async(
            user_message,
            conversation_history=conversation_history,
            task=self._task_mode(task),
            context=execution_context,
        )
        is_legal = any(term in user_message for term in ("法", "契約", "判決", "訴訟", "條"))
        return QueryResult(
            content=content,
            model=model or self._config.default_model,
            mode="legal" if is_legal else "general",
            tokens_in=0,
            tokens_out=0,
            mode_label="⚖️ 法律分析模式" if is_legal else "💬 一般對話模式",
            request_id=execution_context.execution_id,
            error=None if meta.decision.value == "DELIVER" else meta.decision.value,
        )

    def query(
        self,
        user_message: str,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        conversation_history: Optional[list[dict]] = None,
        task: str = "QC",
    ) -> dict[str, Any]:
        """Synchronous compatibility wrapper around ``query_async``."""

        async def invoke() -> QueryResult:
            return await self.query_async(
                user_message,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                conversation_history=conversation_history,
                task=task,
            )

        result = _run_coroutine_sync(invoke())
        return {
            "content": result.content,
            "model": result.model,
            "tokens_in": result.tokens_in,
            "tokens_out": result.tokens_out,
            "mode": result.mode,
            "error": result.error,
        }

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
        """Legacy one-shot entry point; it also goes through the gate path."""

        if dry_run:
            return ""
        return self.query(
            user_message,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            task=task,
        )["content"]

    @staticmethod
    def _task_mode(task: str | TaskMode) -> TaskMode:
        if isinstance(task, TaskMode):
            return task
        aliases = {
            "LEGAL_WRITER": TaskMode.LEGAL_DRAFT,
            "CONTRACT": TaskMode.CONTRACT_REVIEW,
        }
        if str(task).upper() in aliases:
            return aliases[str(task).upper()]
        try:
            return TaskMode(str(task).upper())
        except ValueError:
            return TaskMode.QC


def _run_coroutine_sync(coroutine: Any) -> Any:
    """Run a coroutine from sync code, including a caller's active event loop."""

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coroutine).result()


__all__ = [
    "ZhiyanEngine",
    "EngineConfig",
    "QueryResult",
    "EngineError",
    "LLMConnectionError",
    "LLMTimeoutError",
    "LLMRateLimitError",
    "LLMResponseError",
    "validate_output",
    "discover_api_key",
    "run_llm",
]
