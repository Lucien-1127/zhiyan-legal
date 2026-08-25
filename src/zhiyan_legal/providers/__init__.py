"""Unified provider boundary for Phase 3."""

from .adapters import (
    DeepSeekProviderAdapter,
    GeminiProviderAdapter,
    OpenAIProviderAdapter,
    OpenRouterProviderAdapter,
)
from .base import (
    BaseProviderAdapter,
    ProviderConnectionError,
    ProviderError,
    ProviderHTTPError,
    ProviderRateLimitError,
    ProviderRequest,
    ProviderResponse,
    ProviderRole,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from .registry import ProviderConfig, ProviderRegistry

__all__ = [
    "BaseProviderAdapter",
    "DeepSeekProviderAdapter",
    "GeminiProviderAdapter",
    "OpenAIProviderAdapter",
    "OpenRouterProviderAdapter",
    "ProviderConfig",
    "ProviderConnectionError",
    "ProviderError",
    "ProviderHTTPError",
    "ProviderRateLimitError",
    "ProviderRegistry",
    "ProviderRequest",
    "ProviderResponse",
    "ProviderRole",
    "ProviderTimeoutError",
    "ProviderUnavailableError",
]
