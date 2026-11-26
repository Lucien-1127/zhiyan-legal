from datetime import datetime, timezone

import pytest

from zhiyan_legal.domain import (
    Citation,
    Claim,
    ClaimKind,
    ClaimMateriality,
    ClaimStatus,
    Evidence,
    EvidenceLevel,
    SourceType,
    VerificationStatus,
)
from zhiyan_legal.verification import ClaimEvidenceBinder


NOW = datetime(2026, 8, 25, tzinfo=timezone.utc)


def make_claim(status=ClaimStatus.UNVERIFIED):
    return Claim(
        claim_id="c-1",
        text="契約須以書面確認",
        kind=ClaimKind.LAW,
        materiality=ClaimMateriality.CORE,
        status=status,
    )


def make_evidence(locator="https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=SYNTHETIC", original=None):
    return Evidence(
        source_id="s-1",
        source_type=SourceType.STATUTE,
        title="法規",
        locator=locator,
        retrieved_at=NOW,
        effective_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        version="synthetic-v1",
        original_text=original,
        verification=VerificationStatus.VERIFIED,
        level=EvidenceLevel.VERIFIED,
    )


def test_binder_creates_citation_and_support_edge_without_mutating_inputs():
    claim = make_claim()
    evidence = make_evidence(original=claim.text)
    result = ClaimEvidenceBinder(citation_id_factory=lambda: "cite-1").bind([claim], [evidence])

    assert result.status is VerificationStatus.VERIFIED
    assert result.claims[0].status is ClaimStatus.VERIFIED
    assert result.evidence[0].supports_claims == [claim.claim_id]
    assert result.citations[0].exact_quote == claim.text
    assert claim.status is ClaimStatus.UNVERIFIED
    assert evidence.supports_claims == []


def test_invalid_exact_quote_does_not_verify_claim():
    result = ClaimEvidenceBinder().bind([make_claim()], [make_evidence("law.example/#其他內容")])
    assert result.status is VerificationStatus.UNVERIFIED
    assert result.claims[0].status is ClaimStatus.UNVERIFIED
    assert result.citations == []


def test_bind_context_produces_context_compatible_verified_core_claim():
    from zhiyan_legal.domain import ExecutionContext

    context = ExecutionContext(execution_id="e-1", user_goal="test", claims=[make_claim()], evidence=[make_evidence(original=make_claim().text)])
    bound = ClaimEvidenceBinder(citation_id_factory=lambda: "cite-1").bind_context(context)
    assert bound.claims[0].status is ClaimStatus.VERIFIED
    assert bound.citations[0].claim_id == bound.claims[0].claim_id


def prebound(claim, evidence):
    return Citation(
        citation_id="existing", claim_id=claim.claim_id, source_id=evidence.source_id,
        locator=evidence.locator, exact_quote=claim.text, evidence_level=evidence.level,
        verified_at=NOW,
    )


@pytest.mark.parametrize("status", [VerificationStatus.STALE, VerificationStatus.CONFLICT])
def test_prebound_citation_from_ineligible_evidence_does_not_verify(status):
    claim = make_claim()
    evidence = make_evidence().model_copy(update={
        "supports_claims": [claim.claim_id], "verification": status,
    })
    citation = prebound(claim, evidence)
    result = ClaimEvidenceBinder().bind(claim, evidence, citations=[citation])
    assert result.verified_claim_ids == []
    assert result.claims[0].status is ClaimStatus.UNVERIFIED
    assert result.citations == [citation]  # keep the audit record


@pytest.mark.parametrize("status", [ClaimStatus.STALE, ClaimStatus.CONFLICT])
@pytest.mark.parametrize("supply_citation", [False, True])
def test_text_match_cannot_clear_explicit_claim_status(status, supply_citation):
    claim = make_claim(status)
    evidence = make_evidence().model_copy(update={"supports_claims": [claim.claim_id]})
    existing = [prebound(claim, evidence)] if supply_citation else []
    result = ClaimEvidenceBinder().bind(claim, evidence, citations=existing)
    assert result.claims[0].status is status
    assert result.statuses[claim.claim_id].value == status.value
    assert result.verified_claim_ids == []
    assert result.citations == existing


def test_generated_quote_retains_source_spelling_and_layout_on_rebind():
    claim = make_claim().model_copy(update={"text": "STRASSE甲乙"})
    evidence = make_evidence("test://doc")
    contents = {evidence.source_id: "摘錄：Straße 甲\n乙。"}
    binder = ClaimEvidenceBinder()
    first = binder.bind(claim, evidence, contents=contents)
    assert [c.exact_quote for c in first] == ["Straße 甲\n乙"]
    second = binder.bind(first.claims, first.evidence, citations=first, contents=contents)
    assert second.citations == first.citations
    assert second.verified_claim_ids == []


def test_casefold_match_must_cover_complete_source_characters():
    claim = make_claim().model_copy(update={"text": "s"})
    evidence = make_evidence("test://doc")
    result = ClaimEvidenceBinder().bind(claim, evidence, contents={evidence.source_id: "ß"})
    assert result.citations == []
