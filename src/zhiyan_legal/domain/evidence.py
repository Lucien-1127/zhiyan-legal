"""Canonical evidence and citation types."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from .claims import ClaimId
from .risk import CitationId, Jurisdiction, SourceId


class SourceType(str, Enum):
    STATUTE = "STATUTE"
    JUDGMENT = "JUDGMENT"
    OFFICIAL = "OFFICIAL"
    ACADEMIC = "ACADEMIC"
    USER_FILE = "USER_FILE"
    USER_REPORTED = "USER_REPORTED"


class EvidenceLevel(str, Enum):
    VERIFIED = "VERIFIED"
    CROSS_REFERENCED = "CROSS_REFERENCED"
    USER_REPORTED = "USER_REPORTED"
    NEED_CHECK = "NEED_CHECK"


class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    PARTIAL = "PARTIAL"
    UNVERIFIED = "UNVERIFIED"
    STALE = "STALE"
    CONFLICT = "CONFLICT"


class Evidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source_id: SourceId
    source_type: SourceType
    title: str
    locator: str
    jurisdiction: Jurisdiction = Jurisdiction.TW
    retrieved_at: datetime
    effective_at: datetime | None = None
    supports_claims: list[ClaimId] = Field(default_factory=list)
    verification: VerificationStatus = VerificationStatus.UNVERIFIED
    level: EvidenceLevel = EvidenceLevel.NEED_CHECK


class Citation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    citation_id: CitationId
    claim_id: ClaimId
    source_id: SourceId
    locator: str
    exact_quote: str = Field(description="來源精確字句摘錄")
    evidence_level: EvidenceLevel
    verified_at: datetime


__all__ = [
    "SourceId",
    "CitationId",
    "Jurisdiction",
    "SourceType",
    "EvidenceLevel",
    "VerificationStatus",
    "Evidence",
    "Citation",
]
