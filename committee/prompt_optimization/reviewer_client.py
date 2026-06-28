"""
reviewer_client — API adapter for multi-model reviewer calls.

Wraps OpenAI-compatible API calls with:
  - Configurable model mapping (reviewer → model_id)
  - Retry + timeout (tenacity)
  - Schema sanity check on output
  - Structured error reporting
  - Latency / token telemetry

Usage:
    client = ReviewerClient()
    report = await client.call(ReviewerModel.DEEPSEEK, prompt_text)
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx
from openai import AsyncOpenAI
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from .prompt_quality import (
    ReviewerModel, PromptDimension, Severity,
    PromptClaim, PromptReviewReport,
)
from .prompt_normalizer import PromptNormalizer

logger = logging.getLogger("reviewer_client")

# ── Default model map ───────────────────────────────────
# Maps ReviewerModel → (model_id, base_url)
# Override by passing a custom dict to ReviewerClient.__init__

DEFAULT_MODEL_MAP: dict[ReviewerModel, tuple[str, str]] = {
    ReviewerModel.DEEPSEEK: (
        "deepseek-v4-flash",
        "https://api.deepseek.com/v1",
    ),
    ReviewerModel.GEMINI: (
        "gemini-2.5-flash",
        "https://generativelanguage.googleapis.com/v1beta/openai",
    ),
    ReviewerModel.AGNES: (
        "agnes-2.0-flash",
        "https://apihub.agnes-ai.com/v1",
    ),
}


@dataclass
class APIUsage:
    """Telemetry for a single API call."""
    model_name: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    elapsed_s: float = 0.0
    retry_count: int = 0


# ── Structured errors ────────────────────────────────────


class ReviewerAPIError(Exception):
    """Base for API errors."""


class ReviewerTimeoutError(ReviewerAPIError):
    """API call timed out."""


class ReviewerAuthError(ReviewerAPIError):
    """Authentication failure (wrong key, expired)."""


class ReviewerRateLimitError(ReviewerAPIError):
    """Rate limited (429)."""


class ReviewerSchemaError(ReviewerAPIError):
    """Output failed schema validation."""


# ── Client ───────────────────────────────────────────────


class ReviewerClient:
    """Adapter for calling reviewer models via OpenAI-compatible API."""

    def __init__(
        self,
        model_map: Optional[dict[ReviewerModel, tuple[str, str]]] = None,
        api_keys: Optional[dict[ReviewerModel, str]] = None,
        normalizer: Optional[PromptNormalizer] = None,
        timeout: float = 30.0,
        max_retries: int = 2,
    ):
        self.model_map = model_map or DEFAULT_MODEL_MAP
        self._normalizer = normalizer or PromptNormalizer()
        self._timeout = timeout
        self._max_retries = max_retries

        # Build API clients per provider (share base_url)
        self._clients: dict[str, AsyncOpenAI] = {}
        self._api_keys = api_keys or {}

    def _get_client(self, reviewer: ReviewerModel) -> AsyncOpenAI:
        """Get or create an AsyncOpenAI client for this reviewer's provider."""
        model_id, base_url = self.model_map.get(reviewer, (
            "unknown", "https://api.deepseek.com/v1"
        ))

        # Use base_url as cache key
        if base_url not in self._clients:
            api_key = self._get_api_key(reviewer)
            http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout),
                limits=httpx.Limits(max_keepalive_connections=2, max_connections=5),
            )
            self._clients[base_url] = AsyncOpenAI(
                base_url=base_url,
                api_key=api_key,
                http_client=http_client,
            )
            logger.debug("Created API client for %s → %s", base_url, model_id)

        return self._clients[base_url]

    def _get_api_key(self, reviewer: ReviewerModel) -> str:
        """Resolve API key for a reviewer.

        Priority:
          1. Explicitly provided in __init__
          2. Environment variable (DEEPSEEK_API_KEY, GEMINI_API_KEY, etc.)
          3. Empty string (will fail at call time)
        """
        # Explicit override
        if reviewer in self._api_keys:
            return self._api_keys[reviewer]

        # Environment variable lookup
        env_map = {
            ReviewerModel.DEEPSEEK: "DEEPSEEK_API_KEY",
            ReviewerModel.GEMINI: "GEMINI_API_KEY",
            ReviewerModel.AGNES: "AGNES_API_KEY",
        }
        import os
        env_var = env_map.get(reviewer)
        if env_var:
            key = os.getenv(env_var, "")
            if key and "***" not in key:
                return key

        # Fallback: try OPENAI_API_KEY
        import os
        return os.getenv("OPENAI_API_KEY", "")

    # ── Retry decorator ─────────────────────────────────

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((
            httpx.TimeoutException,
            httpx.ConnectError,
            httpx.RemoteProtocolError,
            ReviewerRateLimitError,
        )),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def _call_api(
        self,
        reviewer: ReviewerModel,
        system_prompt: str,
        prompt_text: str,
        usage: APIUsage,
    ) -> tuple[str, int, int]:
        """Core API call with retry. Returns (content, prompt_tokens, completion_tokens)."""
        client = self._get_client(reviewer)
        model_id, _ = self.model_map.get(reviewer, ("unknown", ""))

        response = await client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt_text},
            ],
            temperature=0.2,       # Low temp for quality review consistency
            max_tokens=2048,       # Reviews should be concise
        )

        content = response.choices[0].message.content or ""
        prompt_tk = response.usage.prompt_tokens if response.usage else 0
        completion_tk = response.usage.completion_tokens if response.usage else 0

        return content, prompt_tk, completion_tk

    # ── Schema sanity check ──────────────────────────────

    def _validate_schema(self, claims: list[PromptClaim]) -> list[PromptClaim]:
        """Post-normalization sanity check.

        Removes claims that fail basic sanity:
          - Empty issue/suggestion
          - Confidence out of range
          - Dimension mismatch
        """
        valid: list[PromptClaim] = []
        for c in claims:
            problems = []
            if not c.issue.strip():
                problems.append("empty issue")
            if not (0.0 <= c.confidence <= 1.0):
                problems.append(f"confidence={c.confidence}")
            if c.dimension not in PromptDimension:
                problems.append(f"unknown dimension={c.dimension}")

            if problems:
                logger.debug("Schema filter removed claim: %s", "; ".join(problems))
            else:
                valid.append(c)

        dropped = len(claims) - len(valid)
        if dropped:
            logger.warning("Schema sanity check dropped %d/%d claims", dropped, len(claims))
        return valid

    # ── Public API ──────────────────────────────────────

    async def call(
        self,
        reviewer: ReviewerModel,
        prompt_text: str,
        slug: str = "prompt",
    ) -> PromptReviewReport:
        """Call a reviewer model, normalize, validate, return report.

        Never raises — structured errors are embedded in the report.
        """
        usage = APIUsage(model_name=reviewer.value)
        slug = slug or f"prompt_{hash(prompt_text) % 10000:04x}"
        system_prompt = self._normalizer.load_reviewer_prompt(reviewer)
        start = time.perf_counter()

        try:
            # Phase 1: API call with retry
            content, prompt_tk, completion_tk = await self._call_api(
                reviewer, system_prompt, prompt_text, usage,
            )
            usage.prompt_tokens = prompt_tk
            usage.completion_tokens = completion_tk
            usage.total_tokens = prompt_tk + completion_tk

            # Phase 2: Normalize
            raw_claims = self._normalizer.normalize(content, reviewer)

            # Phase 3: Schema sanity
            claims = self._validate_schema(raw_claims)

            elapsed = time.perf_counter() - start
            usage.elapsed_s = elapsed

            logger.info(
                "Reviewer %s: %d claims in %.1fs (%d tokens)",
                reviewer.value, len(claims), elapsed, usage.total_tokens,
            )

            return PromptReviewReport(
                reviewer=reviewer,
                prompt_slug=slug,
                claims=claims,
                summary=f"Reviewed by {reviewer.value} — {len(claims)} issues found",
                raw_response=content,
                elapsed_s=elapsed,
            )

        except ReviewerRateLimitError as e:
            elapsed = time.perf_counter() - start
            logger.warning("Reviewer %s rate limited: %s", reviewer.value, e)
            return PromptReviewReport(
                reviewer=reviewer, prompt_slug=slug, claims=[],
                summary="Rate limited (429)", error=f"rate_limit: {e}",
                elapsed_s=elapsed,
            )

        except (ReviewerTimeoutError, asyncio.TimeoutError) as e:
            elapsed = time.perf_counter() - start
            logger.warning("Reviewer %s timed out: %s", reviewer.value, e)
            return PromptReviewReport(
                reviewer=reviewer, prompt_slug=slug, claims=[],
                summary=f"Timeout after {self._timeout}s", error=f"timeout: {e}",
                elapsed_s=elapsed,
            )

        except ReviewerAuthError as e:
            elapsed = time.perf_counter() - start
            logger.error("Reviewer %s auth failed: %s", reviewer.value, e)
            return PromptReviewReport(
                reviewer=reviewer, prompt_slug=slug, claims=[],
                summary="Authentication failed", error=f"auth: {e}",
                elapsed_s=elapsed,
            )

        except Exception as e:
            elapsed = time.perf_counter() - start
            logger.exception("Reviewer %s unexpected error: %s", reviewer.value, e)
            return PromptReviewReport(
                reviewer=reviewer, prompt_slug=slug, claims=[],
                summary="Unexpected error", error=f"unexpected: {e}",
                elapsed_s=elapsed,
            )

    # ── Shutdown ────────────────────────────────────────

    async def shutdown(self):
        """Close all HTTP clients."""
        for url, client in self._clients.items():
            try:
                if client._client:
                    await client._client.aclose()
            except Exception:
                pass
        self._clients.clear()
        logger.info("ReviewerClient: all HTTP clients closed")
