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
import time
from typing import Optional

from openai import OpenAI, RateLimitError

from .loader import count_tokens

logger = logging.getLogger("zhiyan_legal")

MODEL_DEFAULT = "deepseek-v4-flash"

# ── Gemini SDK (optional) ──
try:
    import google.genai as genai
    HAS_GEMINI_SDK = True
except ImportError:
    HAS_GEMINI_SDK = False


def _get_gemini_key() -> str:
    """Get Gemini API key from env or Hermes config."""
    key = os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")
    if key:
        return key
    # Fallback: read from Hermes config
    cfg_path = os.path.expanduser("~/.hermes/profiles/lenien-gcp/config.yaml")
    try:
        import subprocess
        out = subprocess.run(
            ["grep", "-A1", "gemini:", cfg_path],
            capture_output=True, text=True, timeout=5,
        ).stdout
        for line in out.split("\n"):
            if "api_key" in line:
                return line.split("api_key:")[1].strip()
    except Exception:
        pass
    return ""


def get_client(key_num: int = 1) -> OpenAI:
    """Create an OpenAI-compatible client.

    Parameters
    ----------
    key_num : int
        Which key to use (1 = ZHIYAN_API_KEY, 2 = ZHIYAN_API_KEY_2, etc.)

    Raises RuntimeError if the requested key is not set.
    """
    base_url = os.getenv("ZHIYAN_API_BASE_URL", "https://api.openai.com/v1")

    if key_num == 1:
        api_key = os.getenv("ZHIYAN_API_KEY", "")
    else:
        api_key = os.getenv(f"ZHIYAN_API_KEY_{key_num}", "")

    if not api_key and key_num == 1:
        # Try common env-var names as fallback
        for fallback in ("OPENAI_API_KEY", "OPENROUTER_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
            val = os.getenv(fallback)
            if val:
                api_key = val
                break

    if not api_key:
        raise RuntimeError(f"API key {key_num} not found")

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
        "patterns": ["依據", "見解", "實務", "判決"],
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


def _run_gemini(
    system_prompt: str,
    user_message: str,
    model: str,
    temperature: float = 0.3,
    max_tokens: int = 4096,
    task: str = "QC",
) -> str:
    """Run LLM via Google GenAI SDK."""
    if not HAS_GEMINI_SDK:
        raise RuntimeError("google.genai SDK not installed. Run: pip install google-genai")

    api_key = _get_gemini_key()
    if not api_key:
        raise RuntimeError("Gemini API key not found. Set GEMINI_API_KEY env var.")

    gemini_mod = genai  # genai is guaranteed bound if HAS_GEMINI_SDK is True
    client = gemini_mod.Client(api_key=api_key)

    # Strip 'models/' prefix if present
    gemini_model = model.removeprefix("models/")

    logger.info("Calling Gemini %s (temp=%.1f, max=%d)", gemini_model, temperature, max_tokens)

    try:
        response = client.models.generate_content(
            model=gemini_model,
            contents=user_message,
            config={
                "system_instruction": system_prompt,
                "max_output_tokens": max_tokens,
                "temperature": temperature,
            },
        )
        content = response.text or ""
        logger.info("Gemini call succeeded (%d chars)", len(content))
        return validate_output(content, task)
    except Exception as e:
        logger.error("Gemini API call failed: %s", e, exc_info=True)
        print(f"\n❌ Gemini API 呼叫失敗：{e}")
        return ""


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
        print(f"📋 Provider:   {os.getenv('ZHIYAN_PROVIDER', 'openai')}")
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

    # ── Provider routing ──
    provider = os.getenv("ZHIYAN_PROVIDER", "openai").lower()
    if provider == "gemini":
        return _run_gemini(system_prompt, user_message, model, temperature, max_tokens, task)

    # ── OpenAI-compatible: 嘗試 key 輪換（429 → 自動切下一把 key） ──
    max_key_attempts = 3  # 最多試 key 1, key 2, key 3
    last_error = None

    for attempt in range(1, max_key_attempts + 1):
        try:
            client = get_client(key_num=attempt)
            logger.info(
                "Calling %s (key=%d, %s, temp=%.1f, max=%d)",
                model, attempt, os.getenv("ZHIYAN_API_BASE_URL", "https://api.openai.com/v1"),
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
            logger.info("API call succeeded (key=%d, %d chars)", attempt, len(content))
            return validate_output(content, task)

        except RateLimitError as e:
            last_error = e
            if attempt < max_key_attempts and os.getenv(f"ZHIYAN_API_KEY_{attempt + 1}"):
                wait = 1.0
                logger.warning(
                    "Rate limited on key=%d (429). Waiting %.1fs then trying key=%d ...",
                    attempt, wait, attempt + 1,
                )
                time.sleep(wait)
                continue
            else:
                logger.error("Rate limited on all available keys: %s", e)
                break

        except Exception as e:
            logger.error("API call failed (key=%d): %s", attempt, e, exc_info=True)
            last_error = e
            raise

    # ── 所有 key 都失敗 ──
    logger.error("All API keys exhausted. Last error: %s", last_error)
    print(f"\n❌ API 呼叫失敗（嘗試了 {max_key_attempts} 把 key）：{last_error}")
    print("   請檢查 API Key 與端點設定是否正確。")
    print("   可執行 python -m zhiyan_legal \"你的問題\" --dry-run 先行測試。")
    return ""
