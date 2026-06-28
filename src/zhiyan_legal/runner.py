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
