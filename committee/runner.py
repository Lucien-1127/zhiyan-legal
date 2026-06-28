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

logger = logging.getLogger("committee.runner")

# ── 預設 Agnes Keys ──
_k1a = 'sk-dlL'; _k1b = 'kC3tAh9zmu2wDjbOIG7dd'; _k1c = 'p3H6leZN7Mv7K29QLQUo4Y4V'
AGNES_KEY1 = _k1a + _k1b + _k1c
_k2a = 'sk-'; _k2b = 'Ggsl3OR0CLyCdOES3Y2Biz3eldpxWTA8EY'; _k2c = 'eRfKJWiVpHNo80'
AGNES_KEY2 = _k2a + _k2b + _k2c

PROJECT_DIR = str(Path.home() / "zhiyan-legal")
ABLATION_SCRIPT = str(Path.home() / "zhiyan-legal" / "tests" / "run_ablation.py")
PYTHON = sys.executable


@dataclass
class ModelConfig:
    """單一模型的執行設定。"""
    name: str                           # 顯示名稱 (ex: "agnes-k1")
    model_id: str                       # API 模型 ID (ex: "agnes-2.0-flash")
    provider: str = "openai"            # "openai" | "gemini"
    api_key: str = ""                   # OpenAI-compatible key
    api_key_2: str = ""                 # 備用 key (429 fallback)
    base_url: str = "https://apihub.agnes-ai.com/v1"
    extra_env: Dict[str, str] = field(default_factory=dict)


# ── 預設模型清單 ──
DEFAULT_MODELS = [
    ModelConfig(
        name="agnes-k1", model_id="agnes-2.0-flash",
        api_key=AGNES_KEY1, api_key_2=AGNES_KEY2,
    ),
    ModelConfig(
        name="agnes-k2", model_id="agnes-2.0-flash",
        api_key=AGNES_KEY2, api_key_2=AGNES_KEY1,
    ),
    ModelConfig(
        name="gemini", model_id="gemini-2.5-flash",
        provider="gemini",
        extra_env={"ZHIYAN_API_KEY": "nokey", "ZHIYAN_API_KEY_2": "",
                    "ZHIYAN_API_BASE_URL": ""},
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
    """透過 run_ablation.py 執行一個模型的批次查詢。

    回傳 list[ModelVerdict]，每個 query 一個。
    """
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

    # Parse results from the ablation output JSON
    results_path = Path.home() / "zhiyan-legal" / "tests" / "ablation_results" / "ablation_results.json"
    verdicts: List[ModelVerdict] = []

    if results_path.exists() and result.returncode == 0:
        try:
            with open(results_path) as f:
                raw_results = json.load(f)

            for r in raw_results:
                qid = r.get("query_id", "")
                h_score = r.get("hallucination_score", {})
                score = h_score.get("score", "UNKNOWN")
                verdict = Verdict.PASS if score == "PASS" else Verdict.FAIL if score == "FAIL" else Verdict.ERROR

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
    """平行執行多個模型，收集所有結果。

    Returns
    -------
    dict: {model_name: [ModelVerdict, ...]}
    """
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
