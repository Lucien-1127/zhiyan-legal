"""Canonical decisions and pure decision aggregation."""

from datetime import datetime
from enum import Enum, IntEnum

from pydantic import BaseModel, ConfigDict, Field

from .claims import ClaimId
from .risk import RiskLevel, TaskMode


class DecisionStrictness(IntEnum):
    ALLOW = 0
    ABSTAIN = 1
    HUMAN_REVIEW = 2
    BLOCK = 3


class DeliveryDecision(str, Enum):
    DELIVER = "DELIVER"
    ASK = "ASK"
    SAFE = "SAFE"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    STOP = "STOP"

    @property
    def strictness(self) -> DecisionStrictness:
        if self is DeliveryDecision.DELIVER:
            return DecisionStrictness.ALLOW
        if self in (DeliveryDecision.ASK, DeliveryDecision.SAFE):
            return DecisionStrictness.ABSTAIN
        if self is DeliveryDecision.HUMAN_REVIEW:
            return DecisionStrictness.HUMAN_REVIEW
        return DecisionStrictness.BLOCK


class GateId(str, Enum):
    G_SAFETY = "G-SAFETY"
    G_JURISDICTION = "G-JURISDICTION"
    G_FACTS = "G-FACTS"
    G_SOURCE = "G-SOURCE"
    G_SUPPORT = "G-SUPPORT"
    G_TEMPORAL = "G-TEMPORAL"
    G_CONFLICT = "G-CONFLICT"
    G_HIGH_IMPACT = "G-HIGH-IMPACT"
    G_OUTPUT = "G-OUTPUT"


class GateResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    gate_id: GateId
    passed: bool
    reason: str
    target_decision: DeliveryDecision
    evaluated_at: datetime

    @property
    def strictness(self) -> DecisionStrictness:
        return self.target_decision.strictness


class DecisionReducer:
    """Pure monotonic decision reducer; strictness can only increase."""

    @staticmethod
    def reduce(
        gate_results: list[GateResult],
    ) -> tuple[DeliveryDecision, DecisionStrictness]:
        if not gate_results:
            return DeliveryDecision.STOP, DecisionStrictness.BLOCK

        highest_strictness = max(result.strictness for result in gate_results)
        for result in gate_results:
            if result.strictness == highest_strictness:
                return result.target_decision, highest_strictness

        return DeliveryDecision.STOP, DecisionStrictness.BLOCK


class AnswerMeta(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    execution_id: str
    decision: DeliveryDecision
    strictness_level: DecisionStrictness
    task_mode: TaskMode
    risk_level: RiskLevel
    verified_claim_ids: list[ClaimId] = Field(default_factory=list)
    unverified_claim_ids: list[ClaimId] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    tool_failures: list[str] = Field(default_factory=list)
    human_review_required: bool = False


class DecisionRecord(BaseModel):
    """Immutable record of a decision at a particular evaluation time.

    The approved specification names this public type but does not prescribe
    additional fields; these are the smallest fields needed to identify and
    audit one canonical decision.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    execution_id: str
    decision: DeliveryDecision
    strictness_level: DecisionStrictness
    evaluated_at: datetime


__all__ = [
    "DecisionStrictness",
    "DeliveryDecision",
    "GateId",
    "GateResult",
    "DecisionReducer",
    "AnswerMeta",
    "DecisionRecord",
]
