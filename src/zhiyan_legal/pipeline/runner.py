"""Sequential execution and immutable result aggregation for gate checks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from ..domain import (
    AnswerMeta,
    ClaimStatus,
    DecisionRecord,
    DecisionReducer,
    DecisionStrictness,
    DeliveryDecision,
    ExecutionContext,
    ExecutionStatus,
    GateResult,
)
from .base import BaseGate
from .gates import (
    ConflictGate,
    FactsGate,
    HighImpactGate,
    JurisdictionGate,
    OutputGate,
    SafetyGate,
    SourceGate,
    SupportGate,
    TemporalGate,
)


@dataclass(frozen=True)
class GatePipelineResult:
    """The complete immutable result of one pipeline execution."""

    context: ExecutionContext
    answer_meta: AnswerMeta
    decision_record: DecisionRecord

    @property
    def gate_results(self) -> list[GateResult]:
        return self.context.gate_results

    @property
    def decision(self) -> DeliveryDecision:
        return self.answer_meta.decision

    @property
    def strictness(self) -> DecisionStrictness:
        return self.answer_meta.strictness_level

    @property
    def execution_context(self) -> ExecutionContext:
        return self.context

    @property
    def meta(self) -> AnswerMeta:
        return self.answer_meta

    @property
    def record(self) -> DecisionRecord:
        return self.decision_record

    def __iter__(self):
        """Allow convenient ``context, meta, record = pipeline.run(...)``."""
        yield self.context
        yield self.answer_meta
        yield self.decision_record


class GatePipeline:
    """Run all nine gates in specification order and reduce their decisions."""

    DEFAULT_GATES = (
        SafetyGate,
        JurisdictionGate,
        FactsGate,
        SourceGate,
        SupportGate,
        TemporalGate,
        ConflictGate,
        HighImpactGate,
        OutputGate,
    )

    def __init__(self, gates: Iterable[BaseGate] | None = None) -> None:
        self.gates = tuple(gates) if gates is not None else tuple(gate() for gate in self.DEFAULT_GATES)
        expected = tuple(gate_id for gate_id in (
            "G-SAFETY", "G-JURISDICTION", "G-FACTS", "G-SOURCE", "G-SUPPORT",
            "G-TEMPORAL", "G-CONFLICT", "G-HIGH-IMPACT", "G-OUTPUT",
        ))
        actual = tuple(gate.gate_id.value for gate in self.gates)
        if actual != expected:
            raise ValueError("GatePipeline gates must contain the nine gates in specification order")

    def run(self, context: ExecutionContext) -> GatePipelineResult:
        """Evaluate every gate, including after a blocking result.

        The input context is never mutated.  Each result is accumulated in a
        frozen model copy, and the final copy is marked ``DECIDE`` only after
        all nine checks have run.
        """
        working = context.model_copy(
            update={"status": ExecutionStatus.QUALITY_GATE, "gate_results": []}
        )
        results: list[GateResult] = []
        for gate in self.gates:
            result = gate.evaluate(working)
            results.append(result)
            working = working.model_copy(update={"gate_results": list(results)})

        decision, strictness = DecisionReducer.reduce(results)
        working = working.model_copy(update={"status": ExecutionStatus.DECIDE})
        evaluated_at = datetime.now(timezone.utc)
        answer_meta = AnswerMeta(
            execution_id=working.execution_id,
            decision=decision,
            strictness_level=strictness,
            task_mode=working.task_mode,
            risk_level=working.risk_level,
            verified_claim_ids=[
                claim.claim_id for claim in working.claims if claim.status is ClaimStatus.VERIFIED
            ],
            unverified_claim_ids=[
                claim.claim_id for claim in working.claims if claim.status is not ClaimStatus.VERIFIED
            ],
            conflicts=[
                result.reason for result in results
                if result.gate_id.value == "G-CONFLICT" and not result.passed
            ],
            tool_failures=[],
            human_review_required=decision is DeliveryDecision.HUMAN_REVIEW,
        )
        decision_record = DecisionRecord(
            execution_id=working.execution_id,
            decision=decision,
            strictness_level=strictness,
            evaluated_at=evaluated_at,
        )
        return GatePipelineResult(working, answer_meta, decision_record)

    # These names make the runner usable from callers that describe the
    # operation as evaluation rather than execution.
    execute = run
    evaluate = run


__all__ = ["GatePipeline", "GatePipelineResult"]
