from datetime import datetime, timezone

from zhiyan_legal.domain import (
    Claim,
    ClaimKind,
    ClaimMateriality,
    ExecutionContext,
    DecisionStrictness,
    DeliveryDecision,
    RiskLevel,
    TaskMode,
)
from zhiyan_legal.pipeline import GatePipeline


def make_context(**updates) -> ExecutionContext:
    values = {
        "execution_id": "pipeline-test",
        "user_goal": "檢視一般契約",
        "known_facts": ["甲", "2025-01-01", "臺北", "簽署契約", "發生損害"],
    }
    values.update(updates)
    return ExecutionContext(**values)


def test_pipeline_runs_all_nine_gates_in_order_and_returns_immutable_records():
    result = GatePipeline().run(make_context())

    assert [item.gate_id.value for item in result.gate_results] == [
        "G-SAFETY",
        "G-JURISDICTION",
        "G-FACTS",
        "G-SOURCE",
        "G-SUPPORT",
        "G-TEMPORAL",
        "G-CONFLICT",
        "G-HIGH-IMPACT",
        "G-OUTPUT",
    ]
    assert result.context.status.value == "DECIDE"
    assert result.answer_meta.execution_id == "pipeline-test"
    assert result.decision_record.decision is result.answer_meta.decision
    assert result.context is not make_context()


def test_pipeline_does_not_short_circuit_after_safety_stop():
    result = GatePipeline().run(make_context(task_mode=TaskMode.SAFETY))
    assert len(result.gate_results) == 9
    assert result.gate_results[0].target_decision is DeliveryDecision.STOP
    assert result.decision is DeliveryDecision.STOP
    assert result.strictness is DecisionStrictness.BLOCK


def test_pipeline_decision_is_monotonic_and_cannot_be_downgraded_by_later_gates():
    blocked = GatePipeline().run(make_context(user_goal="如何自殺"))
    assert blocked.decision is DeliveryDecision.STOP
    assert blocked.strictness is DecisionStrictness.BLOCK

    reviewed = GatePipeline().run(make_context(risk_level=RiskLevel.HIGH))
    assert reviewed.decision is DeliveryDecision.HUMAN_REVIEW
    assert reviewed.strictness is DecisionStrictness.HUMAN_REVIEW


def test_pipeline_result_supports_tuple_style_handoff():
    context, answer_meta, decision_record = GatePipeline().run(make_context())
    assert context.execution_id == answer_meta.execution_id == decision_record.execution_id

