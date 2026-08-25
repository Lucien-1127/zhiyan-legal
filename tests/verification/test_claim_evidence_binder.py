from datetime import datetime, timezone

from zhiyan_legal.domain import (
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


def make_evidence(locator="law.example/#契約須以書面確認"):
    return Evidence(
        source_id="s-1",
        source_type=SourceType.STATUTE,
        title="法規",
        locator=locator,
        retrieved_at=NOW,
        level=EvidenceLevel.VERIFIED,
    )


def test_binder_creates_citation_and_support_edge_without_mutating_inputs():
    claim, evidence = make_claim(), make_evidence()
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

    context = ExecutionContext(execution_id="e-1", user_goal="test", claims=[make_claim()], evidence=[make_evidence()])
    bound = ClaimEvidenceBinder(citation_id_factory=lambda: "cite-1").bind_context(context)
    assert bound.claims[0].status is ClaimStatus.VERIFIED
    assert bound.citations[0].claim_id == bound.claims[0].claim_id

