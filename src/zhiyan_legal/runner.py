"""
Zhiyan AI Legal System — API-agnostic runner.

Supports any OpenAI-compatible API provider:
- OpenAI (api.openai.com)
- OpenRouter (openrouter.ai/api/v1)
- DeepSeek (api.deepseek.com)
- Google Gemini (generativelanguage.googleapis.com/v1beta/openai)
- MiniMax (api.minimax.chat/v1)
- NVIDIA (api.nvidia.com/v1 — free tier available)
- Any custom endpoint
"""

from __future__ import annotations

import os
import json
import sys
import logging
from typing import Optional

from openai import OpenAI

from .loader import count_tokens

logger = logging.getLogger("zhiyan_legal")

MODEL_DEFAULT = "gpt-5.1"


def get_client() -> OpenAI:
    """Create an OpenAI-compatible client using environment config."""
    base_url = os.getenv("ZHIYAN_API_BASE_URL", "https://api.openai.com/v1")
    api_key = os.getenv("ZHIYAN_API_KEY", "")

    if not api_key:
        # Try common env-var names as fallback
        for fallback in ("OPENAI_API_KEY", "OPENROUTER_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
            val = os.getenv(fallback)
            if val:
                api_key = val
                break

    if not api_key:
        logger.error("No API key found")
        print("❌ No API key found. Set ZHIYAN_API_KEY or one of:")
        print("   OPENAI_API_KEY, OPENROUTER_API_KEY, GEMINI_API_KEY")
        sys.exit(1)

    return OpenAI(base_url=base_url, api_key=api_key)


_TASK_VALIDATION = {
    "QC": {
        "patterns": ["條款", "條文", "第.", "違反", "缺失", "風險"],
        "hint": "QC 輸出應指出具體條款與風險點",
    },
    "LITIGATION": {
        "patterns": ["原告", "被告", "主張", "抗辯", "攻防", "策略"],
        "hint": "訴訟分析應涵蓋雙方立場與攻防策略",
    },
    "REPORT": {
        "patterns": ["摘要", "結論", "建議", "分析"],
        "hint": "報告應包含摘要、分析、結論三層結構",
    },
    "RESEARCH": {
        "patterns": ["依據", "見解", "實務", "判決", "見解"],
        "hint": "研究應附法規或判決依據",
    },
    "CONSULTANT": {
        "patterns": ["方案", "選項", "比較", "利弊", "風險"],
        "hint": "顧問分析應比較不同選項的優劣",
    },
    "SAFETY": {
        "patterns": ["協助", "資源", "專線", "求助", "諮詢"],
        "hint": "安全相關回應應提供求助資源",
    },
    "SIMULATION": {
        "patterns": ["假設", "模擬", "推演", "⚠"],
        "hint": "模擬模式應標示免責聲明",
    },
}


def validate_output(result: str, task: str = "QC") -> str:
    """Post-LLM output validation — simplified DeepThink.

    Checks the output for task-essential keywords.
    If core patterns are missing, appends a structured advisory
    rather than modifying the original content.
    """
    if not result:
        return result

    checks = _TASK_VALIDATION.get(task)
    if not checks:
        return result

    matched = sum(1 for p in checks["patterns"] if p in result)
    threshold = max(1, len(checks["patterns"]) // 3)

    if matched < threshold:
        advisory = (
            f"\n\n---\n"
            f"⚠️ 【輸出校驗警示】此 {task} 輸出未偵測到關鍵要素\n"
            f"建議補充：{checks['hint']}\n"
            f"請確認上述分析是否完整，必要時補充論述。"
        )
        logger.warning(
            "Output validation: task=%s, matched=%d/%d patterns, threshold=%d",
            task, matched, len(checks["patterns"]), threshold,
        )
        return result + advisory

    logger.info(
        "Output validation passed: task=%s, matched=%d/%d patterns",
        task, matched, len(checks["patterns"]),
    )
    return result


def run_llm(
    system_prompt: str,
    user_message: str,
    model: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = 4096,
    dry_run: bool = False,
    task: str = "QC",
) -> str:
    """
    Run the composed system prompt against an LLM.

    Parameters
    ----------
    system_prompt : str
        The fully composed system prompt (loaded from docs/).
    user_message : str
        The user's input query.
    model : str, optional
        Model name override. Defaults to ZHIYAN_MODEL env or gpt-5.1.
    temperature : float
        LLM temperature (default 0.3 for legal precision).
    max_tokens : int
        Max output tokens.
    dry_run : bool
        If True, print the composed prompt and exit without calling the API.
    """
    model = model or os.getenv("ZHIYAN_MODEL") or MODEL_DEFAULT

    if dry_run:
        print("=" * 60)
        print("🔍 DRY RUN — No API call will be made")
        print("=" * 60)
        print(f"\n📋 Model:      {model}")
        print(f"📋 Base URL:   {os.getenv('ZHIYAN_API_BASE_URL', 'https://api.openai.com/v1')}")
        print(f"📋 System PMT: {len(system_prompt):,} chars ({count_tokens(system_prompt):,} tokens approx)")
        print(f"📋 User MSG:   {len(user_message):,} chars")
        print("\n" + "=" * 60)
        print("📄 COMPOSED SYSTEM PROMPT")
        print("=" * 60)
        print(system_prompt[:5000] + ("\n… (truncated)" if len(system_prompt) > 5000 else ""))
        print("\n" + "=" * 60)
        print("📄 USER MESSAGE")
        print("=" * 60)
        print(user_message)
        print("\n" + "=" * 60)
        print("✅ Dry-run complete — 0 tokens consumed.")
        return ""

    client = get_client()

    try:
        logger.info(
            "Calling %s (%s, temp=%.1f, max=%d)",
            model, os.getenv("ZHIYAN_API_BASE_URL", "https://api.openai.com/v1"),
            temperature, max_tokens,
        )
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = response.choices[0].message.content or ""
        logger.info("API call succeeded (%d chars returned)", len(content))
        return validate_output(content, task)
    except Exception as e:
        logger.error("API call failed: %s", e, exc_info=True)
        print(f"\n❌ API 呼叫失敗：{e}")
        print("   請檢查 API Key 與端點設定是否正確。")
        print("   可執行 python -m zhiyan_legal \"你的問題\" --dry-run 先行測試。")
        return ""
