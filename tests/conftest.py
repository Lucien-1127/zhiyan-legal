"""Shared synthetic legal source fixtures for offline application tests."""

from datetime import datetime, timezone

import pytest

from zhiyan_legal.domain import Claim, ClaimKind, ClaimMateriality, Evidence, EvidenceLevel, SourceType, VerificationStatus
from zhiyan_legal.verification import ClaimEvidenceBinder


@pytest.fixture
def bound_citation_fields():
    text = "合成規範要求提供書面資料。"
    claim = Claim(claim_id="synthetic-claim", text=text, kind=ClaimKind.LAW, materiality=ClaimMateriality.CORE)
    evidence = Evidence(
        source_id="synthetic-rule-v1", source_type=SourceType.STATUTE, title="合成規範",
        locator="https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=SYNTHETIC",
        retrieved_at=datetime(2026, 11, 26, tzinfo=timezone.utc),
        effective_at=datetime(2024, 1, 1, tzinfo=timezone.utc), original_text=text, version="v1",
        verification=VerificationStatus.VERIFIED, level=EvidenceLevel.VERIFIED,
    )
    bound = ClaimEvidenceBinder().bind(claim, evidence)
    return {"claims": bound.claims, "evidence": bound.evidence, "citations": bound.citations}
