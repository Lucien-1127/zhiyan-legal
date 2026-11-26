"""Offline citation delivery regressions using synthetic source text only."""

from datetime import datetime, timedelta, timezone

import pytest

from zhiyan_legal.application import ZhiyanApplicationEngine
from zhiyan_legal.domain import (
    Citation, Claim, ClaimKind, ClaimMateriality, ClaimStatus, DeliveryDecision,
    Evidence, EvidenceLevel, ExecutionContext, SourceType, VerificationStatus,
)
from zhiyan_legal.pipeline import GatePipeline


NOW = datetime(2026, 11, 26, tzinfo=timezone.utc)
CLAIM = "測試規範要求書面申請。"


def make_context(
    *,
    quote=CLAIM,
    original=CLAIM,
    source_verification=VerificationStatus.VERIFIED,
    source_type=SourceType.STATUTE,
    claim_status=ClaimStatus.UNVERIFIED,
    with_citation=True,
    cited_source="official",
    second_claim=False,
    **evidence_updates,
):
    claim = Claim(
        claim_id="core", text=CLAIM, kind=ClaimKind.LAW,
        materiality=ClaimMateriality.CORE, status=claim_status,
    )
    locator = (
        "https://data.judicial.gov.tw/jdg/api/JDoc#synthetic"
        if source_type is SourceType.JUDGMENT else
        "https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=SYNTHETIC"
    )
    source = Evidence(
        source_id="official", source_type=source_type, title="合成規範",
        locator=locator,
        retrieved_at=NOW, effective_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        supports_claims=[claim.claim_id], verification=source_verification,
        level=EvidenceLevel.VERIFIED,
    ).model_copy(update={
        "original_text": original, "content": original, "version": "synthetic-v1",
        **evidence_updates,
    })
    citation = Citation(
        citation_id="citation", claim_id=claim.claim_id, source_id=cited_source,
        locator=source.locator, exact_quote=quote, evidence_level=source.level,
        verified_at=NOW,
    )
    claims = [claim]
    evidence = [source]
    if second_claim:
        claims.append(claim.model_copy(update={"claim_id": "core-2", "text": "另須書面補件。"}))
        evidence[0] = source.model_copy(update={"supports_claims": ["core", "core-2"]})
    return ExecutionContext(
        execution_id="citation-integrity", user_goal="檢視合成規範",
        known_facts=["甲", "2025-01-01", "臺北", "申請", "收到回覆"],
        claims=claims, evidence=evidence, citations=[citation] if with_citation else [],
    )


@pytest.mark.parametrize(
    "inputs,decision",
    [
        pytest.param({"with_citation": False}, DeliveryDecision.STOP, id="CIT-01"),
        pytest.param({"cited_source": "missing"}, DeliveryDecision.STOP, id="CIT-02"),
        pytest.param({"quote": "規範不要求書面申請。", "original": "規範不要求書面申請。"},
                     DeliveryDecision.STOP, id="CIT-03"),
        pytest.param({"original": "完全無關。"}, DeliveryDecision.STOP, id="CIT-04"),
        pytest.param({"valid_until": datetime(2024, 12, 31, tzinfo=timezone.utc)},
                     DeliveryDecision.HUMAN_REVIEW, id="CIT-05"),
        pytest.param({"source_verification": VerificationStatus.CONFLICT},
                     DeliveryDecision.HUMAN_REVIEW, id="CIT-06"),
        pytest.param({"withdrawn": True, "source_type": SourceType.JUDGMENT}, DeliveryDecision.STOP, id="CIT-07"),
        pytest.param({"second_claim": True}, DeliveryDecision.STOP, id="CIT-09"),
        pytest.param({}, DeliveryDecision.DELIVER, id="CIT-10"),
        pytest.param({"original": None}, DeliveryDecision.STOP, id="locator-is-not-original"),
        pytest.param({"source_verification": VerificationStatus.UNVERIFIED},
                     DeliveryDecision.STOP, id="source-not-verified"),
        pytest.param({"original": "「測試規範要求書面申請。」並非本條規定。"},
                     DeliveryDecision.STOP, id="negated-excerpt"),
    ],
)
def test_citation_delivery(inputs, decision):
    result = GatePipeline().run(make_context(**inputs))
    assert result.decision is decision
    verified = decision is DeliveryDecision.DELIVER or inputs.get("second_claim")
    assert result.answer_meta.verified_claim_ids == (["core"] if verified else [])
    if inputs.get("source_verification") is VerificationStatus.CONFLICT:
        assert result.answer_meta.conflicts
        assert result.context.evidence[0].verification is VerificationStatus.CONFLICT


def test_no_enumerated_core_claims_cannot_authorize_legal_drafting():
    context = make_context().model_copy(update={"claims": [], "citations": [], "evidence": []})
    assert GatePipeline().run(context).decision is DeliveryDecision.STOP


@pytest.mark.asyncio
async def test_provider_cannot_add_an_unverified_legal_claim(monkeypatch):
    engine = ZhiyanApplicationEngine()

    async def draft(_request):
        return {"content": CLAIM + "\n另有一條不存在的規定。"}

    monkeypatch.setattr(engine.registry, "complete", draft)
    _, meta, content = await engine.execute(make_context())
    assert meta.decision is DeliveryDecision.STOP
    assert "不存在的規定" not in content


def test_prior_verified_status_cannot_survive_invalid_quote():
    result = GatePipeline().run(make_context(
        original="不同的原文。", claim_status=ClaimStatus.VERIFIED,
    ))
    assert "core" not in result.answer_meta.verified_claim_ids
    assert result.context.claims[0].status is ClaimStatus.UNVERIFIED


def test_current_inquiry_does_not_use_source_expired_after_retrieval():
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    context = make_context(valid_until=yesterday, retrieved_at=yesterday - timedelta(days=1)).model_copy(update={
        "known_facts": ["甲", "臺北", "申請", "收到回覆", "個案紀錄"],
    })
    result = GatePipeline().run(context)
    assert result.decision is DeliveryDecision.HUMAN_REVIEW
    assert result.answer_meta.verified_claim_ids == []



def test_all_core_claims_can_be_delivered_with_independent_verified_sources():
    context = make_context(second_claim=True)
    first, second = context.claims
    evidence = context.evidence[0]
    second_source = evidence.model_copy(update={
        "source_id": "official-2", "locator": evidence.locator + "#synthetic-2",
        "supports_claims": [second.claim_id], "original_text": second.text,
    })
    citation = context.citations[0].model_copy(update={
        "citation_id": "citation-2", "claim_id": second.claim_id, "source_id": second_source.source_id,
        "locator": second_source.locator, "exact_quote": second.text,
    })
    result = GatePipeline().run(context.model_copy(update={
        "evidence": [evidence, second_source],
        "citations": [*context.citations, citation],
    }))
    assert result.decision is DeliveryDecision.DELIVER
    assert result.answer_meta.verified_claim_ids == [first.claim_id, second.claim_id]
