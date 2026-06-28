"""adapter.py — 橋接 FastAPI ↔ committee/ 真實模組。

替換掉 stubs 的三個函數：
  run_parallel()  →  committee.runner + run_llm
  normalize()     →  committee.normalizer
  build_synthesis() →  committee.mapper
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from ..core import ModelVerdict, Verdict, ClaimStatus
from ..normalizer import normalize_response, _match_status, normalize_citation
from ..mapper import generate_report
from ..quota import get_remaining, record_call, warn_if_low

logger = logging.getLogger("committee.api.adapter")

# ── 模型執行器設定 ──
# 每個模型的 (label, model_id, provider, api_key_config)
# 真實 key 由 runner.py 的 AGNES_KEY1 / AGNES_KEY2 提供
from ..runner import DEFAULT_MODELS as MODEL_CONFIGS
from zhiyan_legal.runner import run_llm


async def run_parallel(
    query: str,
    models: List[str],
    temperature: float = 0.3,
    max_tokens: int = 4096,
) -> Dict[str, Any]:
    """平行呼叫多個模型，回傳 {model_name: ModelResult dict}。

    使用 asyncio.to_thread 包裝同步的 run_llm() 呼叫。
    """
    # 過濾出要用的模型設定
    active_configs = [c for c in MODEL_CONFIGS if c.name in models]
    if not active_configs:
        raise ValueError(f"沒有可用的模型 (requested={models}, available={[c.name for c in MODEL_CONFIGS]})")

    # 配額檢查
    for cfg in active_configs:
        warn_if_low(cfg.model_id)

    async def call_one(cfg) -> tuple[str, dict]:
        t0 = time.time()
        model_id = cfg.model_id
        record_call(model_id)

        # 設定環境變數 (run_llm 會讀)
        import os
        if cfg.provider == "gemini":
            os.environ["ZHIYAN_PROVIDER"] = "gemini"
            os.environ["ZHIYAN_MODEL"] = model_id
        else:
            os.environ["ZHIYAN_API_KEY"] = cfg.api_key
            os.environ["ZHIYAN_API_KEY_2"] = cfg.api_key_2 or cfg.api_key
            os.environ["ZHIYAN_API_BASE_URL"] = cfg.base_url
            os.environ["ZHIYAN_PROVIDER"] = "openai"
            os.environ["ZHIYAN_MODEL"] = model_id

        try:
            response = await asyncio.to_thread(
                run_llm,
                system_prompt="你是台灣民法專家。回答時請引用具體法條。",
                user_message=query,
                model=model_id,
                temperature=temperature,
                max_tokens=max_tokens,
                task="QC",
            )
            elapsed = round(time.time() - t0, 3)

            # 判斷狀態
            status = _classify_response(response, cfg.name)
            return cfg.name, {
                "status": status,
                "response": response,
                "elapsed_s": elapsed,
                "tokens_in": None,
                "tokens_out": None,
            }
        except Exception as e:
            elapsed = round(time.time() - t0, 3)
            logger.error("[%s] call failed: %s", cfg.name, e)
            return cfg.name, {
                "status": "error",
                "response": f"API call failed: {e}",
                "elapsed_s": elapsed,
                "tokens_in": None,
                "tokens_out": None,
            }

    results = dict(await asyncio.gather(*[call_one(c) for c in active_configs]))
    return results


def _classify_response(response: str, model_name: str) -> str:
    """根據回應內容分類模型狀態。

    Returns: "agree" | "diverge" | "unique" | "error"
    """
    if not response or len(response.strip()) < 5:
        return "error"
    # 檢查是否為 API 錯誤
    status = _match_status(response)
    if status == ClaimStatus.ERROR:
        return "error"
    # 有實質內容 → 預設 agree (mapper 會細分)
    return "agree"


def normalize(results: dict, layer: str) -> dict:
    """三層正規化 — 直接對應 normalizer.py 的邏輯。

    Layer 意義：
      L1 — 條號正規化 (normalize_citation)
      L2 — 用語正規化 (_match_status)
      L3 — 語意兜底 (are_semantically_equivalent)

    目前 L3 尚未實作語意 embedding。
    """
    if layer == "L1":
        # 條號正規化：統一引用格式
        for model_name, data in results.items():
            resp = data.get("response", "")
            data["response_normalized"] = normalize_citation(resp)
        logger.debug("L1 applied: citation normalization")

    elif layer == "L2":
        # 用語正規化：統一狀態表述
        for model_name, data in results.items():
            resp = data.get("response", "")
            status = _match_status(resp)
            data["claim_status"] = status.value if status else "unknown"
        logger.debug("L2 applied: terminology normalization")

    elif layer == "L3":
        # 語意兜底 (stub — 待 sample 累積後實作)
        logger.info("L3 not yet implemented (needs 10+ safety_unknown samples)")
        pass

    return results


def build_synthesis(results: dict, mode: str = "mark", threshold: float = 0.75) -> dict:
    """合議庭標示 — 呼叫 mapper.generate_report 並轉換為 API schema。

    mode:
      "mark"     — 不裁決，只標示 (預設)
      "majority" — 多數決 (實驗性)
      "cot"      — 思維鏈 (實驗性)
    """
    # 1. 將 raw results 轉為 ModelVerdict 列表
    verdicts: List[ModelVerdict] = []
    for model_name, data in results.items():
        resp = data.get("response", "")
        status = data.get("claim_status", _match_status(resp))
        is_error = status == ClaimStatus.ERROR or len(resp.strip()) < 5

        verdicts.append(ModelVerdict(
            model_name=model_name,
            query_id="api",
            query_text="",
            category="api_query",
            verdict=Verdict.ERROR if is_error else Verdict.PASS,
            raw_response=resp,
            elapsed_s=data.get("elapsed_s", 0),
        ))

    # 2. 產生合議庭報告
    report = generate_report(verdicts)

    # 3. 轉換為 API schema
    consensus = []
    divergence = []
    unique = []

    for cluster in report.clusters:
        claim = cluster.canonical_ref
        models_in = cluster.models
        label = cluster.label.value

        if label == "consensus":
            consensus.append({"claim": claim, "models": models_in})
        elif label == "disagreement":
            divergence.append({
                "claim": claim,
                "model_a": models_in[0] if models_in else "?",
                "position_a": cluster.statuses[0].value if cluster.statuses else "?",
                "model_b": models_in[-1] if models_in else "?",
                "position_b": cluster.statuses[-1].value if cluster.statuses else "?",
            })
        elif label == "unique":
            unique.append({"claim": claim, "model": models_in[0] if models_in else "?"})

    # 配額資訊
    quota = {}
    for m in MODEL_CONFIGS:
        rem = get_remaining(m.model_id)
        if rem is not None:
            quota[m.name] = rem

    return {
        "consensus": consensus,
        "divergence": divergence,
        "unique": unique,
        "quota": quota,
    }
