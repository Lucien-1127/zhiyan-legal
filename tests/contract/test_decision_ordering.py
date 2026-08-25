from datetime import datetime, timezone

from zhiyan_legal.domain import (
    DecisionReducer,
    DecisionStrictness,
    DeliveryDecision,
    GateId,
    GateResult,
)


NOW = datetime(2026, 8, 25, tzinfo=timezone.utc)


def gate(decision: DeliveryDecision, gate_id: GateId = GateId.G_FACTS) -> GateResult:
    return GateResult(
        gate_id=gate_id,
        passed=decision is DeliveryDecision.DELIVER,
        reason="contract test",
        target_decision=decision,
        evaluated_at=NOW,
    )


def test_strictness_lattice_is_monotonic() -> None:
    assert DecisionStrictness.ALLOW < DecisionStrictness.ABSTAIN
    assert DecisionStrictness.ABSTAIN < DecisionStrictness.HUMAN_REVIEW
    assert DecisionStrictness.HUMAN_REVIEW < DecisionStrictness.BLOCK

    for decisions in (
        [DeliveryDecision.DELIVER, DeliveryDecision.ASK],
        [DeliveryDecision.ASK, DeliveryDecision.HUMAN_REVIEW],
        [DeliveryDecision.HUMAN_REVIEW, DeliveryDecision.STOP],
        [DeliveryDecision.DELIVER, DeliveryDecision.SAFE, DeliveryDecision.STOP],
    ):
        decision, strictness = DecisionReducer.reduce([gate(item) for item in decisions])
        assert strictness is max(item.strictness for item in decisions)
        assert decision.strictness is strictness


def test_reducer_preserves_same_level_first_decision() -> None:
    decision, strictness = DecisionReducer.reduce(
        [gate(DeliveryDecision.ASK), gate(DeliveryDecision.SAFE)]
    )
    assert decision is DeliveryDecision.ASK
    assert strictness is DecisionStrictness.ABSTAIN


def test_empty_reduction_is_fail_closed_block() -> None:
    assert DecisionReducer.reduce([]) == (
        DeliveryDecision.STOP,
        DecisionStrictness.BLOCK,
    )
