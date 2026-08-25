"""Contract tests for the Claim-Evidence-Citation semantic graph."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from zhiyan_legal.domain import (
    Claim,
    ClaimKind,
    ClaimMateriality,
    ClaimStatus,
    Citation,
    Evidence,
    EvidenceLevel,
    ExecutionContext,
    SourceType,
    VerificationStatus,
)


NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


def test_one_claim_can_bind_multiple_evidence_and_citations() -> None:
    claim = Claim(
        claim_id="claim-1",
        text="契約須以書面確認",
        kind=ClaimKind.LAW,
        materiality=ClaimMateriality.CORE,
    )
    evidence = [
        Evidence(
            source_id="source-law",
            source_type=SourceType.STATUTE,
            title="法規來源",
            locator="law.example/statute#12",
            retrieved_at=NOW,
            supports_claims=[claim.claim_id],
            verification=VerificationStatus.VERIFIED,
            level=EvidenceLevel.VERIFIED,
        ),
        Evidence(
            source_id="source-judgment",
            source_type=SourceType.JUDGMENT,
            title="裁判來源",
            locator="court.example/judgment#8",
            retrieved_at=NOW,
            supports_claims=[claim.claim_id],
            verification=VerificationStatus.VERIFIED,
            level=EvidenceLevel.CROSS_REFERENCED,
        ),
    ]
    citations = [
        Citation(
            citation_id="citation-law",
            claim_id=claim.claim_id,
            source_id=evidence[0].source_id,
            locator="law.example/statute#12",
            exact_quote="契約須以書面確認",
            evidence_level=EvidenceLevel.VERIFIED,
            verified_at=NOW,
        ),
        Citation(
            citation_id="citation-judgment",
            claim_id=claim.claim_id,
            source_id=evidence[1].source_id,
            locator="court.example/judgment#8",
            exact_quote="相關裁判亦採相同見解",
            evidence_level=EvidenceLevel.CROSS_REFERENCED,
            verified_at=NOW,
        ),
    ]

    context = ExecutionContext(
        execution_id="exec-1",
        user_goal="驗證語意網",
        claims=[claim],
        evidence=evidence,
        citations=citations,
    )

    assert len(context.evidence) == 2
    assert all(claim.claim_id in item.supports_claims for item in context.evidence)
    assert {item.source_id for item in context.citations} == {
        item.source_id for item in context.evidence
    }
    assert all(item.claim_id == claim.claim_id for item in context.citations)
    assert all(item.exact_quote and item.locator for item in context.citations)


def test_citation_requires_exact_quote_and_locator_fields() -> None:
    fields = Citation.model_fields

    assert "exact_quote" in fields
    assert "locator" in fields
    with pytest.raises(ValidationError):
        Citation(
            citation_id="citation-1",
            claim_id="claim-1",
            source_id="source-1",
            evidence_level=EvidenceLevel.VERIFIED,
            verified_at=NOW,
        )


def test_core_claim_without_citation_cannot_be_verified() -> None:
    core_claim = Claim(
        claim_id="core-1",
        text="沒有來源支撐的核心命題",
        kind=ClaimKind.FACT,
        materiality=ClaimMateriality.CORE,
        status=ClaimStatus.VERIFIED,
    )

    with pytest.raises(ValidationError, match="requires a related"):
        ExecutionContext(
            execution_id="exec-2",
            user_goal="拒絕無引用核心命題",
            claims=[core_claim],
        )

    # A context that is admitted without provenance must never expose the
    # forbidden VERIFIED status for a CORE claim.
    admitted = Claim(
        claim_id="core-2",
        text="尚未完成驗證的核心命題",
        kind=ClaimKind.FACT,
        materiality=ClaimMateriality.CORE,
        status=ClaimStatus.UNVERIFIED,
    )
    context = ExecutionContext(
        execution_id="exec-3",
        user_goal="保留未驗證狀態",
        claims=[admitted],
    )
    assert context.claims[0].status is not ClaimStatus.VERIFIED
