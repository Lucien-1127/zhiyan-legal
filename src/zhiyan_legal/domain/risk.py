"""Risk, task, procedure, and canonical identifier domain types."""

from enum import Enum
from typing import NewType


ClaimId = NewType("ClaimId", str)
SourceId = NewType("SourceId", str)
CitationId = NewType("CitationId", str)


class Jurisdiction(str, Enum):
    TW = "TW"
    UNKNOWN = "UNKNOWN"
    OTHER = "OTHER"


class TaskMode(str, Enum):
    QC = "QC"
    RESEARCH = "RESEARCH"
    REPORT = "REPORT"
    CONTRACT_REVIEW = "CONTRACT_REVIEW"
    LEGAL_DRAFT = "LEGAL_DRAFT"
    LITIGATION = "LITIGATION"
    TUTOR = "TUTOR"
    COURTROOM = "COURTROOM"
    SAFETY = "SAFETY"


class ProcedureStage(str, Enum):
    NONE = "NONE"
    FILED = "FILED"
    INVESTIGATION = "INVESTIGATION"
    TRIAL = "TRIAL"
    JUDGMENT = "JUDGMENT"
    ENFORCEMENT = "ENFORCEMENT"
    UNKNOWN = "UNKNOWN"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


__all__ = [
    "ClaimId",
    "SourceId",
    "CitationId",
    "Jurisdiction",
    "TaskMode",
    "ProcedureStage",
    "RiskLevel",
]
