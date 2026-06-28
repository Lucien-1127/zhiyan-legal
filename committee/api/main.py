#!/usr/bin/env python3
"""committee/api/main.py — FastAPI 橋接層"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
import logging, time, uuid

from .adapter import run_parallel, normalize, build_synthesis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("committee.api")

app = FastAPI(title="committee/ API", version="0.1.0",
              description="多模型委員會橋接層 — 不裁決·只標示")

app.add_middleware(CORSMiddleware,
                   allow_origins=["*"],
                   allow_methods=["POST", "GET"],
                   allow_headers=["*"])


# ── Schema ──

class NormalizationConfig(BaseModel):
    citation: bool = True
    terminology: bool = True
    semantic: bool = False

class CommitteeRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=8000)
    models: list[str] = Field(default=["agnes-k1", "agnes-k2", "gemini"])
    normalization: NormalizationConfig = NormalizationConfig()
    synthesis: str = Field(default="mark", pattern="^(mark|majority|cot)$")
    agree_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024, ge=64, le=8192)

class ModelResult(BaseModel):
    status: str
    response: str
    elapsed_s: float
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None

class ConsensusItem(BaseModel):
    claim: str
    models: list[str]

class DivergenceItem(BaseModel):
    claim: str
    model_a: str
    position_a: str
    model_b: str
    position_b: str

class UniqueItem(BaseModel):
    claim: str
    model: str

class SynthesisResult(BaseModel):
    consensus: list[ConsensusItem]
    divergence: list[DivergenceItem]
    unique: list[UniqueItem]

class CommitteeResponse(BaseModel):
    query_id: str
    query: str
    models: dict[str, ModelResult]
    synthesis: SynthesisResult
    norm_layers_applied: list[str]
    synthesis_mode: str
    elapsed_total_s: float
    quota: dict[str, int] = {}


# ── Endpoints ──

@app.get("/health")
def health():
    return {"status": "ok", "version": "0.1.0",
            "modules": ["runner", "normalizer", "mapper"]}


@app.post("/api/committee/run", response_model=CommitteeResponse)
async def committee_run(req: CommitteeRequest):
    t0 = time.time()
    qid = str(uuid.uuid4())[:8]
    logger.info("[%s] query='%s' models=%s", qid, req.query[:60], req.models)

    # 1. 平行呼叫
    try:
        raw = await run_parallel(
            query=req.query, models=req.models,
            temperature=req.temperature, max_tokens=req.max_tokens,
        )
    except Exception as e:
        logger.error("[%s] runner: %s", qid, e)
        raise HTTPException(502, detail=str(e))

    # 2. 正規化
    norm_layers = []
    if req.normalization.citation:
        raw = normalize(raw, layer="L1"); norm_layers.append("L1")
    if req.normalization.terminology:
        raw = normalize(raw, layer="L2"); norm_layers.append("L2")
    if req.normalization.semantic:
        raw = normalize(raw, layer="L3"); norm_layers.append("L3")

    # 3. 合議庭標示
    syn = build_synthesis(results=raw, mode=req.synthesis, threshold=req.agree_threshold)

    elapsed = round(time.time() - t0, 3)
    logger.info("[%s] done %.3fs norm=%s", qid, elapsed, norm_layers)

    return CommitteeResponse(
        query_id=qid, query=req.query,
        models={m: ModelResult(**raw[m]) for m in req.models if m in raw},
        synthesis=SynthesisResult(
            consensus=[ConsensusItem(**i) for i in syn.get("consensus", [])],
            divergence=[DivergenceItem(**i) for i in syn.get("divergence", [])],
            unique=[UniqueItem(**i) for i in syn.get("unique", [])],
        ),
        norm_layers_applied=norm_layers,
        synthesis_mode=req.synthesis,
        elapsed_total_s=elapsed,
        quota=syn.get("quota", {}),
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
