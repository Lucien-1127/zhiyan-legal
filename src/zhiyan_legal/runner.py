"""
Zhiyan AI Legal System — API-agnostic runner.

⚠️  DEPRECATED — 請改用 src/zhiyan_legal/engine.py 的 ZhiyanEngine

此檔案保留供向後相容，將在下一版本移除。
"""
from __future__ import annotations

import warnings

warnings.warn(
    "runner.py 已棄用，請改用 zhiyan_legal.engine.ZhiyanEngine",
    DeprecationWarning,
    stacklevel=2,
)


def run_llm(prompt: str = "", **kwargs):
    """Backward-compatible synchronous wrapper around ``ZhiyanEngine``."""
    from .engine import ZhiyanEngine

    engine = ZhiyanEngine()
    query = getattr(engine, "query_sync", engine.query)
    query_kwargs = {
        key: kwargs[key]
        for key in ("model", "temperature", "max_tokens", "conversation_history", "task")
        if key in kwargs
    }
    result = query(kwargs.get("user_message", prompt), **query_kwargs)
    return result.get("content", "") if isinstance(result, dict) else result
