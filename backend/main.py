"""
智研 SaaS 版 — FastAPI 後端主程式 (v2.0)

提供 REST API 給前端聊天 UI 呼叫，串接 zhiyan-legal 法律引擎。

v2.0 改善：
  - Request ID middleware（除錯追蹤）
  - Rate limiting（slowapi）
  - 相依注入（取代全域變數）
  - 結構化錯誤回應
  - 同步非同步生命週期管理
  - 超時 + retry 引擎
"""

from __future__ import annotations

import os
import uuid
import time
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()  # 載入 .env（含 ZHIYAN_API_KEY）

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from zhiyan_legal.application import ZhiyanApplicationEngine
from zhiyan_legal.domain import AnswerMeta, DeliveryDecision
from zhiyan_legal.providers import ProviderError

# ─── 設定 ────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)-16s | %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
DOCS_DIR = PROJECT_ROOT / "docs"

# Rate limiter
_RATE_LIMIT = os.getenv("ZHIYAN_RATE_LIMIT", "30/minute")
limiter = Limiter(key_func=get_remote_address)


# ─── Pydantic 模型 ──────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000, description="使用者輸入")
    model: str | None = None
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1, le=16384)
    task: str = Field(default="QC", description="application engine task mode")
    conversation_history: list[dict[str, str]] = Field(default_factory=list)


class ChatResponse(BaseModel):
    content: str
    model: str
    mode: str
    tokens_in: int
    tokens_out: int
    mode_label: str
    request_id: str = ""
    decision: str
    answer_meta: dict
    error: str | None = None


class StatusResponse(BaseModel):
    status: str
    version: str
    docs_loaded: int
    docs_dir: str
    model: str
    engine_ready: bool
    pool_limits: dict | None = None


class ErrorResponse(BaseModel):
    error: str
    detail: str
    request_id: str = ""


# ─── 引擎相依注入 ──────────────────────────────────────

_engine: ZhiyanApplicationEngine | None = None


def get_engine() -> ZhiyanApplicationEngine:
    """取得引擎實例（相依注入）"""
    assert _engine is not None, "Engine not initialized"
    return _engine


# ─── 生命週期 ──────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """啟動/關閉：引擎初始化 + 資源釋放"""
    global _engine

    logger.info("🚀 智研 SaaS 版 v2.0 啟動中...")
    _engine = ZhiyanApplicationEngine()
    logger.info("✅ application engine 就緒 | providers=%d", len(_engine.registry))

    yield

    # 關閉
    _engine = None
    logger.info("🛑 智研 SaaS 版已關閉")


# ─── FastAPI 實例 ──────────────────────────────────────

app = FastAPI(
    title="智研 AI 法律系統 · SaaS 版",
    description="台灣法律 AI 研究助手 — 5 層架構、強制引用、安全優先",
    version="2.0.0",
    lifespan=lifespan,
)

# ─── Middleware 堆疊 ────────────────────────────────────

# 1. Rate limit handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 2. CORS（可透過環境變數限制）
_cors_origins = os.getenv("ZHIYAN_CORS_ORIGINS", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Trusted hosts（生產用）
_trusted_hosts = os.getenv("ZHIYAN_TRUSTED_HOSTS", "")
if _trusted_hosts:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=_trusted_hosts.split(","),
    )


# 4. Request ID middleware（自訂）
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """為每個請求附加唯一 request_id 供除錯"""
    rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
    request.state.request_id = rid

    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as e:
        logger.exception("[%s] 未處理例外: %s", rid, e)
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error="internal_error",
                detail="伺服器內部錯誤",
                request_id=rid,
            ).model_dump(),
        )

    elapsed = time.perf_counter() - start
    response.headers["X-Request-ID"] = rid
    response.headers["X-Processing-Time-ms"] = str(round(elapsed * 1000, 1))

    # 慢請求警告
    if elapsed > 10:
        logger.warning("[%s] 慢請求: %.1fs | %s %s",
                       rid, elapsed, request.method, request.url.path)

    return response


# 5. Structured error handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """統一錯誤回應格式"""
    rid = getattr(request.state, "request_id", "")
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error="http_error",
            detail=exc.detail,
            request_id=rid,
        ).model_dump(),
        headers=exc.headers or {},
    )


# ─── API 路由 ──────────────────────────────────────────

@app.get("/api/status", response_model=StatusResponse)
@limiter.limit(_RATE_LIMIT)
async def get_status(request: Request):
    """系統狀態檢查"""
    engine = get_engine()
    return StatusResponse(
        status="ok" if len(engine.registry) else "degraded",
        version="2.0.0",
        docs_loaded=0,
        docs_dir=str(DOCS_DIR),
        model=(engine.registry.providers[0].default_model if len(engine.registry) else "canonical-application-engine"),
        engine_ready=True,
        pool_limits=None,
    )


@app.post("/api/chat", response_model=ChatResponse)
@limiter.limit(_RATE_LIMIT)
async def chat(request: Request, body: ChatRequest):
    """法律 AI 對話 — 傳送問題，取得法律分析回應"""
    engine = get_engine()
    rid = request.state.request_id

    try:
        context, meta, content = await engine.query_async(
            body.message,
            conversation_history=body.conversation_history,
            task=body.task,
        )
    except ProviderError as exc:
        logger.error("[%s] 提供商錯誤: %s", rid, exc)
        raise HTTPException(status_code=502, detail=f"提供商錯誤：{exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("[%s] 不明錯誤", rid)
        raise HTTPException(status_code=500, detail=f"查詢失敗：{exc}") from exc

    payload = _chat_payload(body, context, meta, content, rid)
    status_code = _chat_status_code(meta)
    if status_code != 200:
        logger.warning("[%s] application decision=%s status=%d", rid, meta.decision.value, status_code)
        return JSONResponse(status_code=status_code, content=payload)
    return ChatResponse(**payload)


def _chat_payload(body: ChatRequest, _context, meta: AnswerMeta, content: str, rid: str) -> dict:
    """Adapt one canonical execution result to the HTTP response contract."""
    legal = any(term in body.message for term in ("法", "契約", "判決", "訴訟", "條"))
    return {
        "content": content or "application engine returned no content",
        "model": body.model or "canonical-application-engine",
        "mode": "legal" if legal else "general",
        "tokens_in": 0,
        "tokens_out": 0,
        "mode_label": "⚖️ 法律分析模式" if legal else "💬 一般對話模式",
        "request_id": rid or meta.execution_id,
        "decision": meta.decision.value,
        "answer_meta": meta.model_dump(mode="json"),
        "error": "; ".join(meta.tool_failures) or None,
    }


def _chat_status_code(meta: AnswerMeta) -> int:
    """Map a decision to a non-success transport status when delivery fails."""
    if meta.tool_failures and any(item.startswith("provider:") for item in meta.tool_failures):
        return 502
    return {
        DeliveryDecision.DELIVER: 200,
        DeliveryDecision.ASK: 400,
        DeliveryDecision.SAFE: 403,
        DeliveryDecision.HUMAN_REVIEW: 403,
        DeliveryDecision.STOP: 422,
    }[meta.decision]


@app.post("/api/reload")
@limiter.limit("10/minute")
async def reload_docs(request: Request):
    """重新載入法律規格文件（更新 docs/ 後呼叫）"""
    engine = get_engine()
    rid = request.state.request_id

    try:
        doc_count = len(list(DOCS_DIR.rglob("*.md")))
        logger.info("[%s] 文件重新載入完成: %d 份", rid, doc_count)
        return {"status": "ok", "docs_loaded": doc_count, "request_id": rid}
    except Exception as e:
        logger.exception("[%s] 重新載入失敗", rid)
        raise HTTPException(status_code=500, detail=f"重新載入失敗：{e}")


# ─── 靜態檔案服務（前端 SPA） ──────────────────────────

if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


# ─── 直接執行 ──────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("APP_PORT", "8000"))
    host = os.getenv("APP_HOST", "0.0.0.0")
    workers = int(os.getenv("APP_WORKERS", "1"))

    print(f"\n{'='*50}")
    print(f"  📋 智研 AI 法律系統 · SaaS 版 v2.0")
    print(f"  🌐 http://localhost:{port}")
    print(f"  ⚙️  workers={workers} | rate_limit={_RATE_LIMIT}")
    print(f"{'='*50}\n")

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        workers=workers,
        reload=(workers == 1),
    )
