from datetime import datetime, timezone

import pytest

from zhiyan_legal.domain import (
    Claim,
    ClaimKind,
    ClaimMateriality,
    ClaimStatus,
    Citation,
    Evidence,
    EvidenceLevel,
    ExecutionContext,
    Jurisdiction,
    RiskLevel,
    SourceType,
    TaskMode,
    VerificationStatus,
)
from zhiyan_legal.pipeline import (
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


NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


def context(**updates) -> ExecutionContext:
    values = {
        "execution_id": "gate-test",
        "user_goal": "檢視契約風險",
        "known_facts": ["甲", "2025-01-01", "臺北", "簽署契約", "發生損害"],
    }
    values.update(updates)
    return ExecutionContext(**values)


def source_context(**updates) -> ExecutionContext:
    claim = Claim(
        claim_id="c-core",
        text="契約須以書面確認",
        kind=ClaimKind.LAW,
        materiality=ClaimMateriality.CORE,
        status=ClaimStatus.UNVERIFIED,
    )
    evidence = Evidence(
        source_id="s-law",
        source_type=SourceType.STATUTE,
        title="法規",
        locator="law.example/statute#1",
        retrieved_at=NOW,
        effective_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        supports_claims=[claim.claim_id],
        verification=VerificationStatus.VERIFIED,
        level=EvidenceLevel.VERIFIED,
    )
    citation = Citation(
        citation_id="cite-1",
        claim_id=claim.claim_id,
        source_id=evidence.source_id,
        locator=evidence.locator,
        exact_quote=claim.text,
        evidence_level=EvidenceLevel.VERIFIED,
        verified_at=NOW,
    )
    values = {"claims": [claim], "evidence": [evidence], "citations": [citation]}
    values.update(updates)
    return context(**values)


def test_safety_gate_passes_and_blocks_safety_mode_or_high_risk_goal():
    assert SafetyGate().evaluate(context()).passed
    result = SafetyGate().evaluate(context(task_mode=TaskMode.SAFETY))
    assert not result.passed
    assert result.target_decision.value == "STOP"
    assert not SafetyGate().evaluate(context(user_goal="如何自殺")).passed


def test_jurisdiction_gate_requires_tw():
    assert JurisdictionGate().evaluate(context()).passed
    result = JurisdictionGate().evaluate(context(jurisdiction=Jurisdiction.OTHER))
    assert not result.passed
    assert result.target_decision.value == "ASK"


def test_facts_gate_requires_five_elements_and_honours_explicit_missing():
    assert FactsGate().evaluate(context()).passed
    result = FactsGate().evaluate(context(known_facts=["甲", "臺北"]))
    assert not result.passed
    assert result.target_decision.value == "ASK"
    assert not FactsGate().evaluate(context(missing_facts=["結果"])).passed


def test_source_gate_requires_primary_evidence_for_every_core_claim():
    assert SourceGate().evaluate(source_context()).passed
    result = SourceGate().evaluate(source_context(evidence=[], citations=[]))
    assert not result.passed
    assert result.target_decision.value == "STOP"


def test_support_gate_requires_nonempty_quote_that_supports_claim():
    assert SupportGate().evaluate(source_context()).passed
    result = SupportGate().evaluate(
        source_context(citations=[
            Citation(
                citation_id="cite-1",
                claim_id="c-core",
                source_id="s-law",
                locator="law.example/statute#1",
                exact_quote="完全不相關的文字",
                evidence_level=EvidenceLevel.VERIFIED,
                verified_at=NOW,
            )
        ])
    )
    assert not result.passed
    assert result.target_decision.value == "STOP"


def test_temporal_gate_rejects_stale_or_unknown_primary_source_time():
    assert TemporalGate().evaluate(source_context()).passed
    stale = source_context(
        evidence=[source_context().evidence[0].model_copy(update={"verification": VerificationStatus.STALE})]
    )
    result = TemporalGate().evaluate(stale)
    assert not result.passed
    assert result.target_decision.value == "HUMAN_REVIEW"
    unknown_time = source_context(
        evidence=[source_context().evidence[0].model_copy(update={"effective_at": None})]
    )
    assert not TemporalGate().evaluate(unknown_time).passed


def test_conflict_gate_rejects_explicit_conflicts():
    assert ConflictGate().evaluate(context()).passed
    claim = Claim(
        claim_id="c-conflict",
        text="有衝突的命題",
        kind=ClaimKind.LAW,
        status=ClaimStatus.CONFLICT,
    )
    result = ConflictGate().evaluate(context(claims=[claim]))
    assert not result.passed
    assert result.target_decision.value == "HUMAN_REVIEW"


def test_high_impact_gate_requires_human_review_for_high_risk_case():
    assert HighImpactGate().evaluate(context()).passed
    result = HighImpactGate().evaluate(context(risk_level=RiskLevel.HIGH))
    assert not result.passed
    assert result.target_decision.value == "HUMAN_REVIEW"
    assert not HighImpactGate().evaluate(context(user_goal="涉及強制執行書狀")).passed


def test_output_gate_checks_optional_outgoing_payload():
    assert OutputGate().evaluate(context()).passed
    valid = {
        "information_status": "部分驗證",
        "legal_basis": "民法第184條",
        "limitations": "仍須核對完整卷證",
        "prohibited_statement": "不保證訴訟結果",
    }
    assert OutputGate().evaluate(context().model_copy(update={"output": valid})).passed
    incomplete = context().model_copy(update={"output": {"legal_basis": "民法第184條"}})
    result = OutputGate().evaluate(incomplete)
    assert not result.passed
    assert result.target_decision.value == "SAFE"
    guaranteed = context().model_copy(update={"output": {**valid, "limitations": "保證一定會勝訴"}})
    assert not OutputGate().evaluate(guaranteed).passed
