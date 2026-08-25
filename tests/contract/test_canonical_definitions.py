from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from zhiyan_legal.domain import (
    AnswerMeta,
    Claim,
    ClaimKind,
    ClaimMateriality,
    ClaimStatus,
    Citation,
    DecisionRecord,
    DecisionStrictness,
    DeliveryDecision,
    Evidence,
    EvidenceLevel,
    ExecutionContext,
    ExecutionStatus,
    GateId,
    GateResult,
    Jurisdiction,
    ProcedureStage,
    RiskLevel,
    SourceType,
    TaskMode,
    VerificationStatus,
)


NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


def test_canonical_model_fields_and_defaults() -> None:
    assert Claim.model_fields.keys() == {
        "claim_id",
        "text",
        "kind",
        "materiality",
        "status",
    }
    assert Evidence.model_fields.keys() == {
        "source_id",
        "source_type",
        "title",
        "locator",
        "jurisdiction",
        "retrieved_at",
        "effective_at",
        "supports_claims",
        "verification",
        "level",
    }
    assert Citation.model_fields.keys() == {
        "citation_id",
        "claim_id",
        "source_id",
        "locator",
        "exact_quote",
        "evidence_level",
        "verified_at",
    }
    assert GateResult.model_fields.keys() == {
        "gate_id",
        "passed",
        "reason",
        "target_decision",
        "evaluated_at",
    }
    assert ExecutionContext.model_fields.keys() == {
        "execution_id",
        "status",
        "jurisdiction",
        "task_mode",
        "procedure_stage",
        "risk_level",
        "user_goal",
        "known_facts",
        "missing_facts",
        "available_tools",
        "required_sources",
        "claims",
        "evidence",
        "citations",
        "gate_results",
    }
    assert AnswerMeta.model_fields.keys() == {
        "execution_id",
        "decision",
        "strictness_level",
        "task_mode",
        "risk_level",
        "verified_claim_ids",
        "unverified_claim_ids",
        "conflicts",
        "tool_failures",
        "human_review_required",
    }
    assert DecisionRecord.model_fields.keys() == {
        "execution_id",
        "decision",
        "strictness_level",
        "evaluated_at",
    }

    context = ExecutionContext(execution_id="exec-1", user_goal="檢視契約")
    assert context.status is ExecutionStatus.INTAKE
    assert context.jurisdiction is Jurisdiction.TW
    assert context.task_mode is TaskMode.QC
    assert context.procedure_stage is ProcedureStage.NONE
    assert context.risk_level is RiskLevel.MEDIUM
    assert context.claims == []
    assert context.current_decision is DeliveryDecision.STOP


def test_enums_are_canonical_and_fail_closed() -> None:
    assert [level.value for level in DecisionStrictness] == [0, 1, 2, 3]
    assert DeliveryDecision.DELIVER.strictness is DecisionStrictness.ALLOW
    assert DeliveryDecision.ASK.strictness is DecisionStrictness.ABSTAIN
    assert DeliveryDecision.SAFE.strictness is DecisionStrictness.ABSTAIN
    assert DeliveryDecision.HUMAN_REVIEW.strictness is DecisionStrictness.HUMAN_REVIEW
    assert DeliveryDecision.STOP.strictness is DecisionStrictness.BLOCK


def test_models_are_frozen_and_forbid_extra_fields() -> None:
    claim = Claim(claim_id="c-1", text="事實", kind=ClaimKind.FACT)

    with pytest.raises(ValidationError):
        claim.text = "變更"

    with pytest.raises(ValidationError):
        Claim(claim_id="c-1", text="事實", kind=ClaimKind.FACT, unexpected=True)

    with pytest.raises(ValidationError):
        Evidence(
            source_id="s-1",
            source_type=SourceType.STATUTE,
            title="法規",
            locator="law.example/1",
            retrieved_at=NOW,
            unexpected=True,
        )

    with pytest.raises(ValidationError):
        GateResult(
            gate_id=GateId.G_FACTS,
            passed=True,
            reason="ok",
            target_decision=DeliveryDecision.DELIVER,
            evaluated_at=NOW,
            unexpected=True,
        )


def test_core_verified_claim_requires_citation_and_evidence() -> None:
    claim = Claim(
        claim_id="c-core",
        text="核心命題",
        kind=ClaimKind.LAW,
        materiality=ClaimMateriality.CORE,
        status=ClaimStatus.VERIFIED,
    )

    with pytest.raises(ValidationError, match="requires a related"):
        ExecutionContext(execution_id="exec-1", user_goal="test", claims=[claim])

    evidence = Evidence(
        source_id="s-1",
        source_type=SourceType.STATUTE,
        title="法規",
        locator="law.example/1",
        retrieved_at=NOW,
        supports_claims=[claim.claim_id],
        verification=VerificationStatus.VERIFIED,
        level=EvidenceLevel.VERIFIED,
    )
    citation = Citation(
        citation_id="cite-1",
        claim_id=claim.claim_id,
        source_id=evidence.source_id,
        locator=evidence.locator,
        exact_quote="核心命題",
        evidence_level=EvidenceLevel.VERIFIED,
        verified_at=NOW,
    )
    context = ExecutionContext(
        execution_id="exec-1",
        user_goal="test",
        claims=[claim],
        evidence=[evidence],
        citations=[citation],
    )
    assert context.claims[0].status is ClaimStatus.VERIFIED
