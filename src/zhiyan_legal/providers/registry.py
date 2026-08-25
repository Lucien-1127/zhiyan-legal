"""Provider configuration, secure environment discovery, and fallback routing."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Iterable, Mapping
from urllib.parse import urlparse

import httpx

from .base import (
    BaseProviderAdapter,
    ProviderConnectionError,
    ProviderError,
    ProviderHTTPError,
    ProviderRateLimitError,
    ProviderRequest,
    ProviderResponse,
    ProviderTimeoutError,
    ProviderUnavailableError,
)


@dataclass(frozen=True)
class ProviderConfig:
    """Immutable credentials and endpoint for exactly one provider instance."""

    name: str
    base_url: str
    api_key: str = field(repr=False)
    default_model: str
    priority: int
    timeout_seconds: float = 60.0

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("provider name must not be empty")
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("provider base_url must be an absolute HTTP(S) URL")
        if not self.api_key.strip():
            raise ValueError("provider api_key must not be empty")
        if not self.default_model.strip():
            raise ValueError("provider default_model must not be empty")
        if self.priority < 0:
            raise ValueError("provider priority must be non-negative")
        if self.timeout_seconds <= 0:
            raise ValueError("provider timeout_seconds must be positive")

    @property
    def timeout(self) -> float:
        """Short alias retained for clients that expose timeout in seconds."""

        return self.timeout_seconds


_PROVIDER_DEFAULTS: tuple[tuple[str, str, str, str, int], ...] = (
    ("openai", "OPENAI_API_KEY", "https://api.openai.com/v1", "gpt-4o-mini", 10),
    ("deepseek", "DEEPSEEK_API_KEY", "https://api.deepseek.com/v1", "deepseek-chat", 20),
    (
        "gemini",
        "GEMINI_API_KEY",
        "https://generativelanguage.googleapis.com/v1beta/openai",
        "gemini-2.5-flash",
        30,
    ),
    (
        "openrouter",
        "OPENROUTER_API_KEY",
        "https://openrouter.ai/api/v1",
        "openai/gpt-4o-mini",
        40,
    ),
)


def _adapter_for(config: ProviderConfig) -> BaseProviderAdapter:
    # Local import keeps the contracts independent from adapter construction
    # and avoids a registry <-> adapter import cycle.
    from .adapters import (
        DeepSeekProviderAdapter,
        GeminiProviderAdapter,
        OpenAIProviderAdapter,
        OpenRouterProviderAdapter,
    )

    adapters = {
        "openai": OpenAIProviderAdapter,
        "deepseek": DeepSeekProviderAdapter,
        "gemini": GeminiProviderAdapter,
        "openrouter": OpenRouterProviderAdapter,
    }
    adapter_class = adapters.get(config.name)
    if adapter_class is None:
        raise ValueError(f"unsupported provider: {config.name}")
    return adapter_class(config)


class ProviderRegistry:
    """Sorted provider chain with provider-specific adapter isolation."""

    def __init__(
        self,
        providers: Iterable[ProviderConfig] | None = None,
        *,
        adapters: Mapping[str, BaseProviderAdapter] | None = None,
    ) -> None:
        configs = tuple(providers or ())
        self._providers = tuple(sorted(configs, key=lambda item: item.priority))
        supplied_adapters = adapters or {}
        self._bindings: tuple[tuple[ProviderConfig, BaseProviderAdapter], ...] = tuple(
            (
                config,
                supplied_adapters.get(config.name) or _adapter_for(config),
            )
            for config in self._providers
        )

    @property
    def providers(self) -> tuple[ProviderConfig, ...]:
        """Configured providers in fallback order."""

        return self._providers

    def __len__(self) -> int:
        return len(self._providers)

    def __iter__(self):
        return iter(self._providers)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "ProviderRegistry":
        """Discover configured providers from standard provider env vars only.

        No files, shell commands, home-directory profiles, aliases belonging
        to another provider, or application-wide generic key are consulted.
        Passing ``env`` makes discovery deterministic and is useful for tests.
        """

        source = os.environ if env is None else env
        configs: list[ProviderConfig] = []
        for name, key_var, default_url, default_model, priority in _PROVIDER_DEFAULTS:
            api_key = source.get(key_var, "").strip()
            if not api_key:
                continue
            base_url = source.get(f"{name.upper()}_BASE_URL", default_url).strip()
            model = source.get(f"{name.upper()}_MODEL", default_model).strip()
            timeout_value = source.get(f"{name.upper()}_TIMEOUT_SECONDS", "60").strip()
            try:
                timeout_seconds = float(timeout_value)
            except ValueError as exc:
                raise ValueError(
                    f"{name.upper()}_TIMEOUT_SECONDS must be numeric"
                ) from exc
            configs.append(
                ProviderConfig(
                    name=name,
                    base_url=base_url,
                    api_key=api_key,
                    default_model=model,
                    priority=priority,
                    timeout_seconds=timeout_seconds,
                )
            )
        return cls(configs)

    def get(self, name: str) -> ProviderConfig:
        """Return a provider config by canonical name."""

        for config in self._providers:
            if config.name == name:
                return config
        raise KeyError(name)

    async def complete(self, request: ProviderRequest) -> ProviderResponse:
        """Call providers in priority order, falling back on transient errors."""

        if not self._bindings:
            raise ProviderUnavailableError("no providers are configured")

        errors: list[ProviderError] = []
        for config, adapter in self._bindings:
            try:
                response = await adapter.complete(request)
                # The registry is the source of truth for which binding was
                # called.  This also makes metadata safe for test/custom
                # adapters that omit provider metadata.
                return response.model_copy(
                    update={
                        "provider_name": config.name,
                        "model": response.model or config.default_model,
                    }
                )
            except Exception as exc:
                error = _as_provider_error(exc, config.name)
                if not _is_retryable(error):
                    raise error from exc
                errors.append(error)

        details = "; ".join(
            f"{error.provider_name}: {error}" for error in errors
        )
        raise ProviderUnavailableError(
            f"all providers failed during fallback: {details}",
            tuple(errors),
        )

    async def request(self, request: ProviderRequest) -> ProviderResponse:
        return await self.complete(request)

    async def call(self, request: ProviderRequest) -> ProviderResponse:
        """Compatibility alias for callers that describe an invocation as a call."""

        return await self.complete(request)

    async def route(self, request: ProviderRequest) -> ProviderResponse:
        """Alias used by orchestration code that treats the registry as a router."""

        return await self.complete(request)


def _as_provider_error(exc: Exception, provider_name: str) -> ProviderError:
    if isinstance(exc, ProviderError):
        if exc.provider_name:
            return exc
        return type(exc)(
            str(exc), provider_name=provider_name, status_code=exc.status_code
        )
    status_code = getattr(exc, "status_code", None)
    if status_code == 429:
        return ProviderRateLimitError(
            str(exc), provider_name=provider_name, status_code=429
        )
    if isinstance(exc, (TimeoutError, httpx.TimeoutException)):
        return ProviderTimeoutError(str(exc), provider_name=provider_name)
    if isinstance(exc, (ConnectionError, httpx.TransportError, OSError)):
        return ProviderConnectionError(str(exc), provider_name=provider_name)
    return ProviderHTTPError(str(exc), provider_name=provider_name, status_code=status_code)


def _is_retryable(error: ProviderError) -> bool:
    return isinstance(
        error,
        (ProviderRateLimitError, ProviderTimeoutError, ProviderConnectionError),
    ) or error.status_code == 429


__all__ = ["ProviderConfig", "ProviderRegistry"]
