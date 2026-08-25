"""Common contracts for external legal-tool adapters.

Adapters deliberately keep the payload returned by a provider separate from
the canonical domain projection.  A provider can therefore be inspected when
debugging, while downstream pipeline stages only consume ``normalized_data``.
"""

from __future__ import annotations

import inspect
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict


class ToolCapabilityStatus(str, Enum):
    """The three states a tool invocation can have."""

    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    FAILED = "FAILED"


class ToolResult(BaseModel):
    """Immutable, fail-closed result of a tool invocation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tool_name: str
    status: ToolCapabilityStatus
    raw_output: Any = None
    normalized_data: Any = None
    error_message: str | None = None
    executed_at: datetime
    execution_duration_ms: float = 0.0

    @property
    def is_usable(self) -> bool:
        """Whether downstream code may consume ``normalized_data``."""

        return (
            self.status is ToolCapabilityStatus.AVAILABLE
            and self.error_message is None
        )

    @property
    def evidence(self) -> list[Any]:
        """Convenience view for adapters whose normalized output is evidence.

        This is a property, rather than another model field, so the serialized
        contract remains exactly the seven fields specified for ToolResult.
        """

        return self.normalized_data if isinstance(self.normalized_data, list) else []


class BaseToolAdapter(ABC):
    """Base implementation of capability checks and exception containment.

    Subclasses provide a synchronous capability check, argument validation,
    and one provider call.  Provider calls may be either sync or async; all
    public adapter methods can consequently use the same fail-closed wrapper.
    """

    tool_name: str

    def __init__(self, tool_name: str | None = None) -> None:
        if tool_name is not None:
            self.tool_name = tool_name

    def capability(self) -> tuple[ToolCapabilityStatus, str | None]:
        """Return the provider's current capability state.

        The default is intentionally unavailable.  A subclass must opt in
        after checking that its dependency is installed/connected.
        """

        return ToolCapabilityStatus.UNAVAILABLE, "工具未連線或未安裝"

    # Compatibility-friendly alias used by callers that prefer a predicate.
    def is_available(self) -> bool:
        return self.capability()[0] is ToolCapabilityStatus.AVAILABLE

    def check_capability(self) -> tuple[ToolCapabilityStatus, str | None]:
        """Explicitly named alias for :meth:`capability`."""

        return self.capability()

    def _validate(self, operation: str, kwargs: dict[str, Any]) -> str | None:
        """Return a validation error, or ``None`` when arguments are valid."""

        return None

    @abstractmethod
    async def _call(self, operation: str, **kwargs: Any) -> Any:
        """Invoke the provider.  Implementations must not normalize here."""

    @abstractmethod
    def _normalize(self, operation: str, raw_output: Any, **kwargs: Any) -> Any:
        """Project a provider payload into canonical data."""

    async def execute(self, operation: str, **kwargs: Any) -> ToolResult:
        """Run an operation without allowing provider errors to escape."""

        executed_at = datetime.now(timezone.utc)
        started = time.perf_counter()
        raw_output: Any = None

        def result(
            status: ToolCapabilityStatus,
            *,
            raw_output: Any = None,
            normalized_data: Any = None,
            error_message: str | None = None,
        ) -> ToolResult:
            return ToolResult(
                tool_name=self.tool_name,
                status=status,
                raw_output=raw_output,
                normalized_data=normalized_data,
                error_message=error_message,
                executed_at=executed_at,
                execution_duration_ms=(time.perf_counter() - started) * 1000,
            )

        try:
            status, capability_error = self.capability()
        except Exception as exc:  # capability checks are part of the boundary
            return result(ToolCapabilityStatus.FAILED, error_message=_error_text(exc))

        if status is not ToolCapabilityStatus.AVAILABLE:
            return result(status, error_message=capability_error or "工具不可用")

        validation_error = self._validate(operation, kwargs)
        if validation_error:
            return result(
                ToolCapabilityStatus.UNAVAILABLE,
                error_message=validation_error,
            )

        try:
            provider_output = self._call(operation, **kwargs)
            if inspect.isawaitable(provider_output):
                provider_output = await provider_output
            raw_output = provider_output
            normalized_data = self._normalize(operation, raw_output, **kwargs)
            return result(
                ToolCapabilityStatus.AVAILABLE,
                raw_output=raw_output,
                normalized_data=normalized_data,
            )
        except Exception as exc:
            # A malformed provider response is indistinguishable from a failed
            # provider call to the verification pipeline, so both are FAILED.
            return result(
                ToolCapabilityStatus.FAILED,
                raw_output=raw_output,
                error_message=_error_text(exc),
            )

    async def run(self, operation: str, **kwargs: Any) -> ToolResult:
        """Alias for ``execute`` for command-style adapter callers."""

        return await self.execute(operation, **kwargs)


def _error_text(exc: Exception) -> str:
    message = str(exc).strip()
    return f"{type(exc).__name__}: {message}" if message else type(exc).__name__


__all__ = ["ToolCapabilityStatus", "ToolResult", "BaseToolAdapter"]
