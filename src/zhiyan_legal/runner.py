"""
Zhiyan AI Legal System — API-agnostic runner.

Supports any OpenAI-compatible API provider:
- OpenAI (api.openai.com)
- OpenRouter (openrouter.ai/api/v1)
- DeepSeek (api.deepseek.com)
- Google Gemini (generativelanguage.googleapis.com/v1beta/openai)
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

MODEL_DEFAULT = "gpt-4o"


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


def run_llm(
    system_prompt: str,
    user_message: str,
    model: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = 4096,
    dry_run: bool = False,
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
        Model name override. Defaults to ZHIYAN_MODEL env or gpt-4o.
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
        return content
    except Exception as e:
        logger.error("API call failed: %s", e, exc_info=True)
        print(f"\n❌ API 呼叫失敗：{e}")
        print("   請檢查 API Key 與端點設定是否正確。")
        print("   可執行 python -m zhiyan_legal \"你的問題\" --dry-run 先行測試。")
        return ""
