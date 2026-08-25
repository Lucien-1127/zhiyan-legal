"""Canonical execution state and execution context aggregate."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .claims import Claim, ClaimMateriality, ClaimStatus
from .decision import (
    DecisionReducer,
    DecisionStrictness,
    DeliveryDecision,
    GateResult,
)
from .evidence import Citation, Evidence
from .risk import Jurisdiction, ProcedureStage, RiskLevel, TaskMode


class ExecutionStatus(str, Enum):
    INTAKE = "INTAKE"
    SAFETY_ROUTE = "SAFETY_ROUTE"
    TASK_ROUTE = "TASK_ROUTE"
    PLAN = "PLAN"
    RETRIEVE = "RETRIEVE"
    VERIFY = "VERIFY"
    ANALYZE = "ANALYZE"
    QUALITY_GATE = "QUALITY_GATE"
    DECIDE = "DECIDE"


class ExecutionContext(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    execution_id: str
    status: ExecutionStatus = ExecutionStatus.INTAKE
    jurisdiction: Jurisdiction = Jurisdiction.TW
    task_mode: TaskMode = TaskMode.QC
    procedure_stage: ProcedureStage = ProcedureStage.NONE
    risk_level: RiskLevel = RiskLevel.MEDIUM
    user_goal: str
    known_facts: list[str] = Field(default_factory=list)
    missing_facts: list[str] = Field(default_factory=list)
    available_tools: list[str] = Field(default_factory=list)
    required_sources: list[str] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    gate_results: list[GateResult] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_core_claim_provenance(self) -> "ExecutionContext":
        evidence_by_source = {evidence.source_id: evidence for evidence in self.evidence}
        citations_by_claim: dict[object, list[Citation]] = {}
        for citation in self.citations:
            citations_by_claim.setdefault(citation.claim_id, []).append(citation)

        for claim in self.claims:
            if claim.materiality is not ClaimMateriality.CORE:
                continue
            if claim.status is not ClaimStatus.VERIFIED:
                continue

            has_valid_provenance = any(
                citation.source_id in evidence_by_source
                and claim.claim_id in evidence_by_source[citation.source_id].supports_claims
                for citation in citations_by_claim.get(claim.claim_id, [])
            )
            if not has_valid_provenance:
                raise ValueError(
                    f"Verified core claim {claim.claim_id!r} requires a related "
                    "Citation and Evidence"
                )
        return self

    @property
    def current_decision(self) -> DeliveryDecision:
        decision, _ = DecisionReducer.reduce(self.gate_results)
        return decision

    @property
    def current_strictness(self) -> DecisionStrictness:
        _, strictness = DecisionReducer.reduce(self.gate_results)
        return strictness


__all__ = [
    "ExecutionStatus",
    "ExecutionContext",
]
