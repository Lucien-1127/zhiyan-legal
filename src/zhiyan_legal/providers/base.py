"""Provider-independent request and response contracts.

The provider layer deliberately owns the wire-format translation.  Callers
only need to know about these contracts and never need to construct a
provider-specific SDK client.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from .registry import ProviderConfig


class ProviderRole(str, Enum):
    """The approved reasoning role for a provider invocation."""

    DRAFTER = "DRAFTER"
    VERIFIER = "VERIFIER"
    CRITIC = "CRITIC"


class ProviderRequest(BaseModel):
    """Canonical input shared by every provider adapter."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    task_id: str
    role: ProviderRole = ProviderRole.DRAFTER
    instructions: str
    evidence_ids: list[str] = Field(default_factory=list)
    output_schema: str = "default"
    timeout_seconds: float = 60.0


class ProviderResponse(BaseModel):
    """Canonical successful provider result and call metadata."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    task_id: str
    content: str
    model: str
    provider_name: str
    tokens_used: int = 0
    latency_ms: float = 0.0
    error: str | None = None


class ProviderError(RuntimeError):
    """Base error raised by an adapter or the registry."""

    def __init__(
        self,
        message: str,
        *,
        provider_name: str = "",
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.provider_name = provider_name
        self.status_code = status_code


class ProviderRateLimitError(ProviderError):
    """The provider rejected the request because of rate limiting (HTTP 429)."""


class ProviderTimeoutError(ProviderError):
    """The provider did not answer before the configured timeout."""


class ProviderConnectionError(ProviderError):
    """The provider could not be reached."""


class ProviderHTTPError(ProviderError):
    """A non-retryable provider HTTP error."""


class ProviderUnavailableError(ProviderError):
    """All retryable providers in a fallback chain failed."""

    def __init__(self, message: str, errors: tuple[ProviderError, ...] = ()) -> None:
        super().__init__(message)
        self.errors = errors


class BaseProviderAdapter(ABC):
    """Adapter boundary implemented by each supported provider.

    An adapter receives one immutable request and is permanently bound to one
    :class:`ProviderConfig`.  In particular, the registry never replaces an
    adapter's URL or key while falling back to another provider.
    """

    def __init__(self, config: "ProviderConfig") -> None:
        self.config = config

    @property
    def provider_name(self) -> str:
        return self.config.name

    @property
    def base_url(self) -> str:
        return self.config.base_url

    @property
    def model(self) -> str:
        return self.config.default_model

    @abstractmethod
    async def complete(self, request: ProviderRequest) -> ProviderResponse:
        """Execute a request against this adapter's own provider endpoint."""

    async def request(self, request: ProviderRequest) -> ProviderResponse:
        """Descriptive alias for :meth:`complete`."""

        return await self.complete(request)

    async def __call__(self, request: ProviderRequest) -> ProviderResponse:
        return await self.complete(request)


__all__ = [
    "BaseProviderAdapter",
    "ProviderConnectionError",
    "ProviderError",
    "ProviderHTTPError",
    "ProviderRateLimitError",
    "ProviderRequest",
    "ProviderResponse",
    "ProviderRole",
    "ProviderTimeoutError",
    "ProviderUnavailableError",
]
