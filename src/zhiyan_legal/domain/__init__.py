"""Canonical, framework-independent domain contracts."""

from .claims import Claim, ClaimId, ClaimKind, ClaimMateriality, ClaimStatus
from .decision import (
    AnswerMeta,
    DecisionRecord,
    DecisionReducer,
    DecisionStrictness,
    DeliveryDecision,
    GateId,
    GateResult,
)
from .evidence import (
    Citation,
    CitationId,
    Evidence,
    EvidenceLevel,
    SourceId,
    SourceType,
    VerificationStatus,
)
from .execution import ExecutionContext, ExecutionStatus
from .risk import Jurisdiction, ProcedureStage, RiskLevel, TaskMode

__all__ = [
    "ClaimId",
    "SourceId",
    "CitationId",
    "Jurisdiction",
    "TaskMode",
    "ProcedureStage",
    "RiskLevel",
    "ExecutionStatus",
    "DecisionStrictness",
    "DeliveryDecision",
    "ClaimKind",
    "ClaimMateriality",
    "ClaimStatus",
    "Claim",
    "SourceType",
    "EvidenceLevel",
    "VerificationStatus",
    "Evidence",
    "Citation",
    "GateId",
    "GateResult",
    "DecisionReducer",
    "AnswerMeta",
    "DecisionRecord",
    "ExecutionContext",
]
