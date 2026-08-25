"""HTTP adapters for the supported provider APIs.

OpenAI, DeepSeek, Gemini's compatibility endpoint, and OpenRouter all expose
the chat-completions wire shape.  They still have separate adapter classes so
that a config (and therefore its URL and credential) cannot silently migrate
between providers during fallback.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from .base import (
    BaseProviderAdapter,
    ProviderConnectionError,
    ProviderHTTPError,
    ProviderRateLimitError,
    ProviderRequest,
    ProviderResponse,
    ProviderTimeoutError,
)
from .registry import ProviderConfig


class _OpenAICompatibleAdapter(BaseProviderAdapter):
    """Shared transport for providers with OpenAI-compatible APIs."""

    def _payload(self, request: ProviderRequest) -> dict[str, Any]:
        role_context = (
            f"Role: {request.role.value}\n"
            f"Output schema: {request.output_schema}\n"
            f"Evidence IDs: {', '.join(request.evidence_ids) or '(none)'}"
        )
        return {
            "model": self.config.default_model,
            "messages": [
                {"role": "system", "content": role_context},
                {"role": "user", "content": request.instructions},
            ],
        }

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

    async def complete(self, request: ProviderRequest) -> ProviderResponse:
        url = self.config.base_url.rstrip("/") + "/chat/completions"
        started = time.monotonic()
        try:
            timeout = min(request.timeout_seconds, self.config.timeout_seconds)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    url,
                    headers=self._headers(),
                    json=self._payload(request),
                )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                f"{self.provider_name} request timed out",
                provider_name=self.provider_name,
            ) from exc
        except httpx.TransportError as exc:
            raise ProviderConnectionError(
                f"{self.provider_name} connection failed: {exc}",
                provider_name=self.provider_name,
            ) from exc

        if response.status_code == 429:
            raise ProviderRateLimitError(
                f"{self.provider_name} rate limited (HTTP 429)",
                provider_name=self.provider_name,
                status_code=429,
            )
        if response.status_code >= 400:
            raise ProviderHTTPError(
                f"{self.provider_name} returned HTTP {response.status_code}",
                provider_name=self.provider_name,
                status_code=response.status_code,
            )

        try:
            data = response.json()
            content = _content_from_response(data)
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderHTTPError(
                f"{self.provider_name} returned an invalid response",
                provider_name=self.provider_name,
            ) from exc

        usage = data.get("usage") or {}
        tokens_used = usage.get("total_tokens", 0)
        if not isinstance(tokens_used, int):
            tokens_used = 0
        return ProviderResponse(
            task_id=request.task_id,
            content=content,
            model=str(data.get("model") or self.config.default_model),
            provider_name=self.provider_name,
            tokens_used=tokens_used,
            latency_ms=(time.monotonic() - started) * 1000,
        )


class OpenAIProviderAdapter(_OpenAICompatibleAdapter):
    """Adapter bound to OpenAI's endpoint and an OpenAI key/model."""


class DeepSeekProviderAdapter(_OpenAICompatibleAdapter):
    """Adapter bound to DeepSeek's endpoint and a DeepSeek key/model."""


class GeminiProviderAdapter(_OpenAICompatibleAdapter):
    """Adapter bound to Gemini's OpenAI-compatible endpoint and model."""


class OpenRouterProviderAdapter(_OpenAICompatibleAdapter):
    """Adapter bound to OpenRouter's endpoint and an OpenRouter key/model."""


def _content_from_response(data: dict[str, Any]) -> str:
    choices = data["choices"]
    message = choices[0]["message"]
    content = message["content"]
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and isinstance(part.get("text", ""), str)
        )
    raise TypeError("message content is not text")


__all__ = [
    "DeepSeekProviderAdapter",
    "GeminiProviderAdapter",
    "OpenAIProviderAdapter",
    "OpenRouterProviderAdapter",
]
