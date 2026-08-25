"""Fail-closed adapters for official legal information tools."""

from .base import BaseToolAdapter, ToolCapabilityStatus, ToolResult
from .judicial import JudicialApiAdapter
from .regulation import RegulationApiAdapter

__all__ = [
    "BaseToolAdapter",
    "ToolCapabilityStatus",
    "ToolResult",
    "JudicialApiAdapter",
    "RegulationApiAdapter",
]
