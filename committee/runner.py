"""執行器 — 將查詢送給多個模型，收集結果。

支援：
  - OpenAI-compatible API (Agnes, DeepSeek, Perplexity等)
  - Google Gemini (原生 SDK)
  - 429 自動 key 輪換
  - 平行執行多模型
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .core import ModelVerdict, Verdict

# 從統一設定入口載入 — 不再 hardcode 任何金鑰
try:
    from zhiyan_legal.config import settings as _cfg
    AGNES_KEY1 = _cfg.agnes_key_1
    AGNES_KEY2 = _cfg.agnes_key_2
    _AGNES_BASE_URL = _cfg.agnes_base_url
    _AGNES_MODEL = _cfg.agnes_model
except ImportError:
    # committee 在 src/ 外被直接執行時的 fallback
    AGNES_KEY1 = os.environ.get("AGNES_API_KEY_1") or os.environ.get("AGNES_KEY1", "")
    AGNES_KEY2 = os.environ.get("AGNES_API_KEY_2") or os.environ.get("AGNES_KEY2", "")
    _AGNES_BASE_URL = os.environ.get("AGNES_BASE_URL", "https://apihub.agnes-ai.com/v1")
    _AGNES_MODEL = os.environ.get("AGNES_MODEL", "agnes-2.0-flash")

logger = logging.getLogger("committee.runner")

if not AGNES_KEY1 or not AGNES_KEY2:
    logger.warning(
        "AGNES_API_KEY_1/2 未設定 — 請在 .env 填入 Agnes 金鑰，或匯出環境變數。"
    )

PROJECT_DIR = str(Path.home() / "zhiyan-legal")
ABLATION_SCRIPT = str(Path.home() / "zhiyan-legal" / "tests" / "run_ablation.py")
PYTHON = sys.executable


@dataclass
class ModelConfig:
    """單一模型的執行設定。"""
    name: str
    model_id: str
    provider: str = "openai"
    api_key: str = ""
    api_key_2: str = ""
    base_url: str = _AGNES_BASE_URL
    extra_env: Dict[str, str] = field(default_factory=dict)


# ── 預設模型清單（從 .env 動態讀取，不 hardcode）──
DEFAULT_MODELS = [
    ModelConfig(
        name="agnes-k1", model_id=_AGNES_MODEL,
        api_key=AGNES_KEY1, api_key_2=AGNES_KEY2,
        base_url=_AGNES_BASE_URL,
    ),
    ModelConfig(
        name="agnes-k2", model_id=_AGNES_MODEL,
        api_key=AGNES_KEY2, api_key_2=AGNES_KEY1,
        base_url=_AGNES_BASE_URL,
    ),
    ModelConfig(
        name="gemini",
        model_id=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
        provider="gemini",
        extra_env={
            "ZHIYAN_API_KEY": "nokey",
            "ZHIYAN_API_KEY_2": "",
            "ZHIYAN_API_BASE_URL": "",
        },
    ),
]


def load_queries(categories: str) -> List[Dict]:
    """從 ablation_queries.json 載入指定類別的查詢。"""
    qp = Path.home() / "zhiyan-legal" / "tests" / "ablation_queries.json"
    with open(qp) as f:
        data = json.load(f)
    allowed = set(c.strip() for c in categories.split(","))
    return [q for q in data["queries"] if q.get("category") in allowed]


def run_model_batch(
    config: ModelConfig,
    queries: List[Dict],
    condition: str = "A",
    timeout: int = 600,
) -> List[ModelVerdict]:
    """透過 run_ablation.py 執行一個模型的批次查詢。"""
    cats = ",".join(sorted(set(q["category"] for q in queries)))
    logger.info("[%s] Starting batch: %d queries, cats=%s", config.name, len(queries), cats)

    env = os.environ.copy()
    if config.provider == "gemini":
        env |= {
            "ZHIYAN_PROVIDER": "gemini",
            "ZHIYAN_MODEL": config.model_id,
            "PYTHONPATH": "src",
        }
        if config.extra_env:
            env |= config.extra_env
    else:
        env |= {
            "ZHIYAN_API_KEY": config.api_key,
            "ZHIYAN_API_KEY_2": config.api_key_2 or config.api_key,
            "ZHIYAN_API_BASE_URL": config.base_url,
            "ZHIYAN_MODEL": config.model_id,
            "ZHIYAN_PROVIDER": "openai",
            "PYTHONPATH": "src",
        }

    t0 = time.time()
    result = subprocess.run(
        [PYTHON, "-u", ABLATION_SCRIPT,
         "--conditions", condition,
         "--categories", cats,
         "--model", config.model_id],
        cwd=PROJECT_DIR, env=env, capture_output=True, text=True,
        timeout=timeout,
    )
    elapsed = time.time() - t0

    results_path = (
        Path.home() / "zhiyan-legal" / "tests"
        / "ablation_results" / "ablation_results.json"
    )
    verdicts: List[ModelVerdict] = []

    if results_path.exists() and result.returncode == 0:
        try:
            with open(results_path) as f:
                raw_results = json.load(f)
            for r in raw_results:
                qid = r.get("query_id", "")
                h_score = r.get("hallucination_score", {})
                score = h_score.get("score", "UNKNOWN")
                verdict = (
                    Verdict.PASS if score == "PASS"
                    else Verdict.FAIL if score == "FAIL"
                    else Verdict.ERROR
                )
                verdicts.append(ModelVerdict(
                    model_name=config.name,
                    query_id=qid,
                    query_text=r.get("query", "")[:120],
                    category=r.get("category", ""),
                    verdict=verdict,
                    hallucination_score=1.0 if verdict == Verdict.FAIL else 0.0,
                    raw_response=r.get("response", ""),
                    elapsed_s=r.get("elapsed_s", 0.0),
                    error=r.get("error"),
                ))
        except (json.JSONDecodeError, KeyError) as e:
            logger.error("[%s] Failed to parse results: %s", config.name, e)

    logger.info("[%s] Done (%d/%d parsed, %.0fs)",
                config.name, len(verdicts), len(queries), elapsed)
    return verdicts


def run_committee(
    queries: List[Dict],
    models: Optional[List[ModelConfig]] = None,
    condition: str = "A",
    max_workers: int = 3,
) -> Dict[str, List[ModelVerdict]]:
    """平行執行多個模型，收集所有結果。"""
    models = models or DEFAULT_MODELS
    results: Dict[str, List[ModelVerdict]] = {}

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {
            ex.submit(run_model_batch, cfg, queries, condition): cfg.name
            for cfg in models
        }
        for f in as_completed(futures):
            name = futures[f]
            try:
                results[name] = f.result()
            except Exception as e:
                logger.error("[%s] Batch failed: %s", name, e)
                results[name] = []

    return results
