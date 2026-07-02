"""
智研 AI — Cloud Run API 伺服器

用法：
  PYTHONPATH=src python docker/api_server.py

或者透過 Docker + Cloud Run：
  docker build -t zhiyan-api -f docker/Dockerfile .
  docker run -p 8080:8080 zhiyan-api
"""

import os
import logging
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("zhiyan-api")

app = FastAPI(
    title="智研 AI 法律系統 API",
    description="以分層架構、強制引用政策與安全路由為核心的台灣法律 AI API",
    version="3.08.0",
    contact={"name": "Lucien", "email": "Lucien127@proton.me"},
)


class QueryRequest(BaseModel):
    prompt: str = Field(..., description="法律問題")
    mode: str = Field(default="qc", description="模式: qc / research / report / chat")
    model: Optional[str] = Field(default=None, description="模型覆寫")
    dry_run: bool = Field(default=False, description="乾執行模式（零成本）")


class QueryResponse(BaseModel):
    status: str
    output: Optional[str] = None
    error: Optional[str] = None


@app.get("/health")
async def health():
    """健康檢查"""
    return {"status": "ok", "version": "3.08.0"}


@app.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    """法律問題查詢 — 整合 zhiyan_legal.runner"""
    try:
        from zhiyan_legal.runner import ZhiyanRunner
        runner = ZhiyanRunner()

        logger.info(f"Query: mode={req.mode}, dry_run={req.dry_run}, prompt={req.prompt[:60]}")

        if req.dry_run:
            return QueryResponse(
                status="dry_run",
                output=f"[乾執行] 模式={req.mode}，問題={req.prompt[:80]}"
            )

        result = runner.run(prompt=req.prompt, mode=req.mode, model=req.model)
        return QueryResponse(status="success", output=result)

    except ImportError as ie:
        logger.warning(f"zhiyan_legal.runner 尚未安裝或無法匯入: {ie}")
        return QueryResponse(
            status="success",
            output=f"[開發模式] 模式={req.mode}，問題={req.prompt[:80]}"
        )
    except Exception as e:
        logger.error(f"Query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze", response_model=QueryResponse)
async def analyze(req: QueryRequest):
    """合約/文件分析（未來擴充）"""
    return QueryResponse(
        status="not_implemented",
        output="此功能開發中"
    )


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
