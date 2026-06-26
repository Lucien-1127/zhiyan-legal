"""
智研 SaaS 版 — FastAPI 後端主程式

提供 REST API 給前端聊天 UI 呼叫，串接 zhiyan-legal 法律引擎。
"""

from __future__ import annotations

import os
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from engine import ZhiyanEngine

# ─── 設定 ────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"

# ─── 全域引擎實例 ────────────────────────────────────────
engine = ZhiyanEngine()


# ─── Pydantic 模型 ──────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000, description="使用者輸入")
    model: str | None = None
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1, le=16384)


class ChatResponse(BaseModel):
    content: str
    model: str
    mode: str
    tokens_in: int
    tokens_out: int
    mode_label: str


class StatusResponse(BaseModel):
    status: str
    version: str
    docs_loaded: int
    docs_dir: str
    model: str


# ─── 生命週期 ──────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """啟動時預載法律規格文件。"""
    logger.info("🚀 智研 SaaS 版啟動中...")
    try:
        engine.load_docs()
        doc_count = len(list(Path(DOCS_DIR).rglob("*.md")))
        logger.info(f"✅ 已載入 {doc_count} 份法律規格文件")
    except Exception as e:
        logger.warning(f"⚠️ 法律文件載入失敗（仍可啟動）: {e}")
    yield


# ─── FastAPI 實例 ──────────────────────────────────────

app = FastAPI(
    title="智研 AI 法律系統 · SaaS 版",
    description="台灣法律 AI 研究助手 — 5 層架構、強制引用、安全優先",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS：允許前端開發時跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DOCS_DIR = PROJECT_ROOT / "docs"


# ─── API 路由 ──────────────────────────────────────────

@app.get("/api/status", response_model=StatusResponse)
async def get_status():
    """系統狀態檢查。"""
    doc_count = 0
    if DOCS_DIR.exists():
        doc_count = len(list(DOCS_DIR.rglob("*.md")))

    return StatusResponse(
        status="ok",
        version="1.0.0",
        docs_loaded=doc_count,
        docs_dir=str(DOCS_DIR),
        model=os.getenv("ZHIYAN_MODEL", "deepseek-chat"),
    )


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """法律 AI 對話 — 傳送問題，取得法律分析回應。"""
    try:
        result = engine.query(
            user_message=request.message,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

        mode_labels = {
            "legal": "⚖️ 法律分析模式",
            "general": "💬 一般對話模式",
        }

        return ChatResponse(
            content=result["content"],
            model=result["model"],
            mode=result["mode"],
            tokens_in=result["tokens_in"],
            tokens_out=result["tokens_out"],
            mode_label=mode_labels.get(result["mode"], "💬 一般對話"),
        )
    except Exception as e:
        logger.exception("LLM 查詢失敗")
        raise HTTPException(status_code=500, detail=f"查詢失敗：{str(e)}")


@app.post("/api/reload")
async def reload_docs():
    """重新載入法律規格文件（更新 docs/ 後呼叫）。"""
    try:
        engine.reload()
        doc_count = len(list(DOCS_DIR.rglob("*.md")))
        return {"status": "ok", "docs_loaded": doc_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重新載入失敗：{str(e)}")


# ─── 靜態檔案服務（前端 SPA） ──────────────────────────

if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


# ─── 直接執行 ──────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("APP_PORT", "8000"))
    host = os.getenv("APP_HOST", "0.0.0.0")

    print(f"\n{'='*50}")
    print(f"  📋 智研 AI 法律系統 · SaaS 版")
    print(f"  🌐 http://localhost:{port}")
    print(f"{'='*50}\n")

    uvicorn.run("main:app", host=host, port=port, reload=True)
