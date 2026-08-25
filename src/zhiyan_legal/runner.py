"""Deprecated compatibility import for the historical runner entry point."""
from __future__ import annotations

import warnings

warnings.warn(
    "runner.py 已棄用，請改用 zhiyan_legal.engine.ZhiyanEngine",
    DeprecationWarning,
    stacklevel=2,
)

from .engine import run_llm  # noqa: E402, F401

__all__ = ["run_llm"]
