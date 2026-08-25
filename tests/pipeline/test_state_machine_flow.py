"""Phase 2 state-machine and fail-closed integration contracts.

There is intentionally no network or model call in these tests.  The state
machine is represented by the canonical :class:`ExecutionStatus` snapshots;
the executable quality boundary is the real ``GatePipeline`` and the real
tool/verification contracts.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from zhiyan_legal.domain import (
    Claim,
    ClaimKind,
    ClaimMateriality,
    ClaimStatus,
    DeliveryDecision,
    Evidence,
    EvidenceLevel,
    ExecutionContext,
    ExecutionStatus,
    GateId,
    SourceType,
    VerificationStatus,
)
from zhiyan_legal.pipeline import (
    FactsGate,
    GatePipeline,
    OutputGate,
    SourceGate,
)
from zhiyan_legal.tools import RegulationApiAdapter, ToolCapabilityStatus
from zhiyan_legal.verification import ClaimEvidenceBinder


NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
STATE_FLOW = (
    ExecutionStatus.INTAKE,
    ExecutionStatus.SAFETY_ROUTE,
    ExecutionStatus.TASK_ROUTE,
    ExecutionStatus.PLAN,
    ExecutionStatus.RETRIEVE,
    ExecutionStatus.VERIFY,
    ExecutionStatus.ANALYZE,
    ExecutionStatus.QUALITY_GATE,
    ExecutionStatus.DECIDE,
)


def make_context(**updates: object) -> ExecutionContext:
    values: dict[str, object] = {
        "execution_id": "state-machine-test",
        "status": ExecutionStatus.INTAKE,
        "user_goal": "檢視一般契約",
        "known_facts": ["甲", "2025-01-01", "臺北", "簽署契約", "發生損害"],
    }
    values.update(updates)
    return ExecutionContext(**values)


def advance(context: ExecutionContext, status: ExecutionStatus) -> ExecutionContext:
    """Take one state snapshot without mutating the previous aggregate."""

    return context.model_copy(update={"status": status})


def delivery_is_authorized(context: ExecutionContext, decision: DeliveryDecision) -> bool:
    """The delivery boundary used by the contract, kept deliberately strict."""

    return (
        context.status is ExecutionStatus.DECIDE
        and len(context.gate_results) == 9
        and all(result.passed for result in context.gate_results)
        and decision is DeliveryDecision.DELIVER
    )


def test_complete_state_machine_is_single_step_and_ends_at_decide():
    initial = make_context()
    snapshots = [initial]
    current = initial

    for expected in STATE_FLOW[1:]:
        current = advance(current, expected)
        snapshots.append(current)

    assert tuple(snapshot.status for snapshot in snapshots) == STATE_FLOW
    assert all(
        previous.status is not current.status
        for previous, current in zip(snapshots, snapshots[1:])
    )
    assert initial.status is ExecutionStatus.INTAKE
    assert current.status is ExecutionStatus.DECIDE


def test_pipeline_runs_nine_gates_and_prefix_decisions_converge_monotonically():
    claim = Claim(
        claim_id="c-contract",
        text="契約須以書面確認",
        kind=ClaimKind.LAW,
        materiality=ClaimMateriality.CORE,
    )
    evidence = Evidence(
        source_id="s-official",
        source_type=SourceType.OFFICIAL,
        title="官方契約規範",
        locator="official://contract/契約須以書面確認",
        retrieved_at=NOW,
        effective_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        verification=VerificationStatus.VERIFIED,
        level=EvidenceLevel.VERIFIED,
    )
    bound = ClaimEvidenceBinder(citation_id_factory=lambda: "citation-state").bind(
        claim,
        evidence,
    )
    context = make_context(
        status=ExecutionStatus.ANALYZE,
        claims=bound.claims,
        evidence=bound.evidence,
        citations=bound.citations,
    )

    result = GatePipeline().run(context)
    gate_ids = tuple(item.gate_id for item in result.gate_results)
    assert gate_ids == tuple(GateId(item) for item in (
        "G-SAFETY",
        "G-JURISDICTION",
        "G-FACTS",
        "G-SOURCE",
        "G-SUPPORT",
        "G-TEMPORAL",
        "G-CONFLICT",
        "G-HIGH-IMPACT",
        "G-OUTPUT",
    ))
    assert result.context.status is ExecutionStatus.DECIDE
    assert result.context is not context
    assert result.answer_meta.verified_claim_ids == ["c-contract"]

    # A reducer over every prefix is the monotonic state of the pipeline.  A
    # later gate may report a less strict *local* target, but it can never
    # lower the already accumulated decision.
    prefix_strictness = [
        result.context.model_copy(update={"gate_results": list(result.gate_results[:index])}).current_strictness
        for index in range(1, len(result.gate_results) + 1)
    ]
    assert prefix_strictness == sorted(prefix_strictness)


def test_no_bypass_attempt_can_authorize_delivery_before_verify_and_quality_gate():
    incomplete_claim = Claim(
        claim_id="c-bypass",
        text="尚未核對的核心命題",
        kind=ClaimKind.LAW,
        materiality=ClaimMateriality.CORE,
        status=ClaimStatus.UNVERIFIED,
    )
    for status in STATE_FLOW[:-1]:
        context = make_context(status=status, claims=[incomplete_claim])
        result = GatePipeline().run(context)

        assert result.context.status is ExecutionStatus.DECIDE
        assert len(result.gate_results) == 9
        assert not delivery_is_authorized(context, result.decision)
        assert result.decision is DeliveryDecision.STOP

    # Even an otherwise complete context cannot be delivered by passing a
    # pre-quality status into the pipeline: the actual nine-gate result is the
    # only object eligible for the final delivery boundary.
    result = GatePipeline().run(
        make_context(status=ExecutionStatus.ANALYZE, claims=[incomplete_claim])
    )
    assert result.decision is not DeliveryDecision.DELIVER
    assert not delivery_is_authorized(make_context(status=ExecutionStatus.ANALYZE), result.decision)


class BrokenOfficialTracker:
    def get_articles(self, _pcode: str):
        raise TimeoutError("official source timed out")


def test_official_failure_follows_ask_safe_stop_fail_closed_chain():
    failure = asyncio.run(
        RegulationApiAdapter(tracker=BrokenOfficialTracker()).get_article("A0001", "1")
    )
    assert failure.status is ToolCapabilityStatus.FAILED
    assert failure.error_message and "TimeoutError" in failure.error_message
    assert failure.normalized_data is None

    limited = make_context(missing_facts=["官方來源查詢失敗"]).model_copy(
        update={"output": {
            "information_status": "官方來源失敗，資料尚未驗證",
            "legal_basis": "尚待官方來源確認",
            "limitations": failure.error_message,
        }}
    )
    assert failure.error_message in limited.output["limitations"]  # type: ignore[attr-defined]
    assert FactsGate().evaluate(limited).target_decision is DeliveryDecision.ASK

    safe = OutputGate().evaluate(limited)
    assert not safe.passed
    assert safe.target_decision is DeliveryDecision.SAFE

    core_claim = Claim(
        claim_id="c-unverified",
        text="官方來源尚未確認",
        kind=ClaimKind.LAW,
        materiality=ClaimMateriality.CORE,
        status=ClaimStatus.UNVERIFIED,
    )
    stop = SourceGate().evaluate(make_context(claims=[core_claim]))
    assert not stop.passed
    assert stop.target_decision is DeliveryDecision.STOP

    decisions = [
        FactsGate().evaluate(limited).target_decision,
        safe.target_decision,
        stop.target_decision,
    ]
    assert decisions == [
        DeliveryDecision.ASK,
        DeliveryDecision.SAFE,
        DeliveryDecision.STOP,
    ]
