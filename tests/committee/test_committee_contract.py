"""Phase 4 integration contracts for committee safety and degradation.

The committee produces candidate analysis only.  These tests intentionally
exercise the boundary between that candidate report and the deterministic
GatePipeline decision reducer.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from zhiyan_legal.application import ZhiyanApplicationEngine
from zhiyan_legal.committee import (
    CommitteeMemberVerdict,
    CommitteeReportVNext,
    ConsensusEvaluator,
    ConsensusStatus,
)
from zhiyan_legal.domain import (
    AnswerMeta,
    Claim,
    ClaimKind,
    ClaimStatus,
    Citation,
    DecisionStrictness,
    DeliveryDecision,
    Evidence,
    EvidenceLevel,
    ExecutionContext,
    RiskLevel,
    SourceType,
    TaskMode,
    VerificationStatus,
)
from zhiyan_legal.providers import ProviderRole


NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


def _claim(
    status: ClaimStatus = ClaimStatus.UNVERIFIED,
    *,
    claim_id: str = "contract-claim",
) -> Claim:
    return Claim(
        claim_id=claim_id,
        text="契約責任須以已驗證資料判斷",
        kind=ClaimKind.LAW,
        status=status,
    )


def _member(
    name: str,
    verdict: str = "PASS",
    *,
    claims: list[Claim] | None = None,
    error: str | None = None,
) -> CommitteeMemberVerdict:
    return CommitteeMemberVerdict(
        provider_name=name,
        model=f"{name}-model",
        role=ProviderRole.VERIFIER,
        claims=list(claims if claims is not None else [_claim()]),
        verdict=verdict,
        error=error,
    )


def _supported_provenance() -> tuple[list[Evidence], list[Citation]]:
    evidence = Evidence(
        source_id="source-contract",
        source_type=SourceType.STATUTE,
        title="已驗證法規",
        locator="law.example/contracts#1",
        retrieved_at=NOW,
        supports_claims=["contract-claim"],
        verification=VerificationStatus.VERIFIED,
        level=EvidenceLevel.VERIFIED,
    )
    citation = Citation(
        citation_id="citation-contract",
        claim_id="contract-claim",
        source_id=evidence.source_id,
        locator=evidence.locator,
        exact_quote="契約責任須以已驗證資料判斷",
        evidence_level=EvidenceLevel.VERIFIED,
        verified_at=NOW,
    )
    return [evidence], [citation]


def _report(
    *,
    status: ConsensusStatus = ConsensusStatus.CONSENSUS,
    decision: DeliveryDecision = DeliveryDecision.DELIVER,
) -> CommitteeReportVNext:
    return CommitteeReportVNext(
        task_id="contract-task",
        status=status,
        member_verdicts=[],
        recommended_decision=decision,
        recommended_strictness=decision.strictness,
        evaluated_at=NOW,
    )


def _meta(decision: DeliveryDecision) -> AnswerMeta:
    return AnswerMeta(
        execution_id="contract-execution",
        decision=decision,
        strictness_level=decision.strictness,
        task_mode=TaskMode.CONTRACT_REVIEW,
        risk_level=RiskLevel.MEDIUM,
    )


def test_unanimous_model_majority_cannot_promote_unverified_claim() -> None:
    report = ConsensusEvaluator().evaluate(
        "contract-task",
        [_member("one"), _member("two"), _member("three")],
        evaluated_at=NOW,
    )

    assert report.status is ConsensusStatus.CONSENSUS
    assert report.recommended_decision is DeliveryDecision.HUMAN_REVIEW
    assert report.recommended_strictness is DecisionStrictness.HUMAN_REVIEW
    assert report.consensus_claims[0].status is ClaimStatus.UNVERIFIED


def test_unsupported_model_verified_claim_is_repaired_to_unverified() -> None:
    report = ConsensusEvaluator().evaluate(
        "contract-task",
        [
            _member("one", claims=[_claim(ClaimStatus.VERIFIED)]),
            _member("two", claims=[_claim(ClaimStatus.VERIFIED)]),
        ],
        evaluated_at=NOW,
    )

    assert report.consensus_claims[0].status is ClaimStatus.UNVERIFIED
    assert report.recommended_decision is DeliveryDecision.HUMAN_REVIEW


def test_evidence_and_citation_are_required_before_verified_consensus() -> None:
    evidence, citations = _supported_provenance()
    report = ConsensusEvaluator().evaluate(
        "contract-task",
        [
            _member("one", claims=[_claim(ClaimStatus.VERIFIED)]),
            _member("two", claims=[_claim(ClaimStatus.VERIFIED)]),
        ],
        evidence=evidence,
        citations=citations,
        evaluated_at=NOW,
    )

    assert report.consensus_claims[0].status is ClaimStatus.VERIFIED
    assert report.recommended_decision is DeliveryDecision.DELIVER


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (ConsensusStatus.DISAGREEMENT, DeliveryDecision.HUMAN_REVIEW),
        (ConsensusStatus.BLIND_SPOT, DeliveryDecision.STOP),
    ],
)
def test_dangerous_consensus_statuses_raise_strictness(
    status: ConsensusStatus, expected: DeliveryDecision
) -> None:
    report = _report(status=status, decision=DeliveryDecision.DELIVER)
    merged = ZhiyanApplicationEngine._merge_committee_decision(
        _meta(DeliveryDecision.DELIVER), report
    )

    assert merged.decision is expected
    assert merged.strictness_level is expected.strictness


@pytest.mark.parametrize(
    ("gate_decision", "committee_decision"),
    [
        (DeliveryDecision.DELIVER, DeliveryDecision.DELIVER),
        (DeliveryDecision.ASK, DeliveryDecision.DELIVER),
        (DeliveryDecision.HUMAN_REVIEW, DeliveryDecision.DELIVER),
        (DeliveryDecision.STOP, DeliveryDecision.DELIVER),
    ],
)
def test_committee_merge_never_decreases_gate_strictness(
    gate_decision: DeliveryDecision, committee_decision: DeliveryDecision
) -> None:
    merged = ZhiyanApplicationEngine._merge_committee_decision(
        _meta(gate_decision), _report(decision=committee_decision)
    )

    assert merged.strictness_level >= gate_decision.strictness
    if gate_decision is not DeliveryDecision.DELIVER:
        assert merged.decision is gate_decision


def test_gate_stop_prevents_committee_from_bypassing_pipeline() -> None:
    class MustNotRunCommittee:
        async def run(self, *args, **kwargs):
            raise AssertionError("committee must not run after a blocking gate")

    context = ExecutionContext(
        execution_id="blocked-before-committee",
        task_mode=TaskMode.SAFETY,
        user_goal="一般契約檢視",
    )
    engine = ZhiyanApplicationEngine(committee_engine=MustNotRunCommittee())

    _evaluated, meta, _response = asyncio.run(engine.execute(context))

    assert meta.decision is DeliveryDecision.STOP
    assert engine.last_committee_report is None


def test_partial_failure_is_recorded_without_promoting_failure_to_pass() -> None:
    report = ConsensusEvaluator().evaluate(
        "contract-task",
        [
            _member("healthy-one"),
            _member("healthy-two"),
            _member("failed-seat", verdict="ERROR", error="ProviderTimeout"),
        ],
        evaluated_at=NOW,
    )

    assert report.status is ConsensusStatus.PARTIAL_FAILURE
    assert report.recommended_decision is DeliveryDecision.HUMAN_REVIEW
    failed = next(
        member for member in report.member_verdicts if member.provider_name == "failed-seat"
    )
    assert failed.error == "ProviderTimeout"
    assert failed.verdict == "ERROR"


def test_quorum_loss_is_fail_closed_blind_spot() -> None:
    report = ConsensusEvaluator(quorum=2).evaluate(
        "contract-task",
        [_member("failed-seat", error="ProviderUnavailable")],
        evaluated_at=NOW,
    )

    assert report.status is ConsensusStatus.BLIND_SPOT
    assert report.recommended_decision is DeliveryDecision.STOP
