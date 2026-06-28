"""
智研 SaaS 版 — 法律引擎封裝層 (v2.0 → v3.0)

⚠️  DEPRECATED — 直接 re-export 自 src/zhiyan_legal/engine.py

請改為:
    from zhiyan_legal.engine import ZhiyanEngine, EngineConfig, QueryResult

保留此檔案供向後相容，新的開發請直接匯入 src/zhiyan_legal/engine。
"""
from __future__ import annotations

import logging
import warnings

logger = logging.getLogger(__name__)

# Emit deprecation warning once on import
warnings.warn(
    "backend/engine.py 已棄用，請改為 from zhiyan_legal.engine import ZhiyanEngine",
    DeprecationWarning,
    stacklevel=2,
)

# ── Re-export from canonical location ────────────────
import sys
from pathlib import Path

_SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from zhiyan_legal.engine import (        # noqa: E402, F401
    ZhiyanEngine,
    EngineConfig,
    QueryResult,
    EngineError,
    LLMConnectionError,
    LLMTimeoutError,
    LLMRateLimitError,
    LLMResponseError,
    validate_output,
    discover_api_key,
)

logger.info("backend/engine.py → re-exported from zhiyan_legal.engine (deprecated path)")
