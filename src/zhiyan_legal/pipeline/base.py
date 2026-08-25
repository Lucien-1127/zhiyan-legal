"""Interfaces shared by the executable quality gates.

The gate layer deliberately depends only on the canonical domain package.  A
gate is an ordinary, stateless object so that it can be evaluated repeatedly
in tests or in a replay of an execution without creating side effects.
"""

from abc import ABC, abstractmethod
from typing import ClassVar

from ..domain import ExecutionContext, GateId, GateResult


class BaseGate(ABC):
    """Pure interface implemented by every pipeline gate."""

    gate_id: ClassVar[GateId]

    @abstractmethod
    def evaluate(self, context: ExecutionContext) -> GateResult:
        """Evaluate this gate against *context* without mutating it."""


__all__ = ["BaseGate"]
