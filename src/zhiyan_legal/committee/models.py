"""Canonical data contracts for the Phase 4 multi-model committee."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from zhiyan_legal.domain import Claim, DecisionStrictness, DeliveryDecision
from zhiyan_legal.providers import ProviderRole


class ConsensusStatus(str, Enum):
    """Outcome of comparing the successful committee seats."""

    CONSENSUS = "CONSENSUS"
    DISAGREEMENT = "DISAGREEMENT"
    BLIND_SPOT = "BLIND_SPOT"
    PARTIAL_FAILURE = "PARTIAL_FAILURE"


class CommitteeMemberVerdict(BaseModel):
    """One immutable, auditable seat result."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider_name: str
    model: str
    role: ProviderRole
    claims: list[Claim] = Field(default_factory=list)
    verdict: str
    confidence: float = 1.0
    error: str | None = None


class CommitteeReportVNext(BaseModel):
    """Candidate analysis produced by the committee."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    task_id: str
    status: ConsensusStatus
    member_verdicts: list[CommitteeMemberVerdict]
    consensus_claims: list[Claim] = Field(default_factory=list)
    divergent_claims: list[Claim] = Field(default_factory=list)
    recommended_decision: DeliveryDecision
    recommended_strictness: DecisionStrictness
    evaluated_at: datetime

    @classmethod
    def from_legacy(cls, report, task_id: str | None = None) -> "CommitteeReportVNext":
        """Compatibility constructor for the legacy ``committee`` package."""
        return report.to_vnext(task_id=task_id)

    from_committee_report = from_legacy


__all__ = [
    "ConsensusStatus",
    "CommitteeMemberVerdict",
    "CommitteeReportVNext",
]
