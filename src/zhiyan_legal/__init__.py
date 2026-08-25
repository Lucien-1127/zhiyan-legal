"""
智研AI法律工作站 (Zhiyan AI Legal System)
"""

import importlib

from .domain import (
    AnswerMeta,
    Claim,
    ClaimId,
    ClaimKind,
    ClaimMateriality,
    ClaimStatus,
    Citation,
    CitationId,
    DecisionRecord,
    DecisionReducer,
    DecisionStrictness,
    DeliveryDecision,
    Evidence,
    EvidenceLevel,
    ExecutionContext,
    ExecutionStatus,
    GateId,
    GateResult,
    Jurisdiction,
    ProcedureStage,
    RiskLevel,
    SourceId,
    SourceType,
    TaskMode,
    VerificationStatus,
)
from .application import ZhiyanApplicationEngine
from .committee import CommitteeEngine
from .providers import ProviderRegistry

_LAZY_EXPORTS = {
    "GatePipeline": ("zhiyan_legal.pipeline", "GatePipeline"),
    "BaseToolAdapter": ("zhiyan_legal.tools", "BaseToolAdapter"),
}


def __getattr__(name: str):
    """Load lower-layer compatibility exports only when requested."""

    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = target
    value = getattr(importlib.import_module(module_name), attribute_name)
    globals()[name] = value
    return value

__all__ = [
    "ClaimId", "SourceId", "CitationId", "Jurisdiction", "TaskMode",
    "ProcedureStage", "RiskLevel", "ExecutionStatus", "DecisionStrictness",
    "DeliveryDecision", "ClaimKind", "ClaimMateriality", "ClaimStatus",
    "Claim", "SourceType", "EvidenceLevel", "VerificationStatus", "Evidence",
    "Citation", "GateId", "GateResult", "DecisionReducer", "AnswerMeta",
    "DecisionRecord", "ExecutionContext", "ZhiyanApplicationEngine",
    "GatePipeline", "CommitteeEngine", "BaseToolAdapter", "ProviderRegistry",
]
