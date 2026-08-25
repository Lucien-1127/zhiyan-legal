from datetime import datetime, timezone

from zhiyan_legal.domain import (
    Claim,
    ClaimKind,
    ClaimStatus,
    Evidence,
    SourceType,
    VerificationStatus,
)
from zhiyan_legal.verification import ConflictDetector


NOW = datetime(2026, 8, 25, tzinfo=timezone.utc)


def test_explicit_claim_or_evidence_conflict_is_reported():
    claim = Claim(claim_id="c-1", text="命題", kind=ClaimKind.LAW, status=ClaimStatus.CONFLICT)
    assert ConflictDetector().detect([claim]) is VerificationStatus.CONFLICT

    evidence = Evidence(
        source_id="s-1",
        source_type=SourceType.JUDGMENT,
        title="判決",
        locator="court.example/1",
        retrieved_at=NOW,
        verification=VerificationStatus.CONFLICT,
    )
    assert ConflictDetector().detect([evidence]) is VerificationStatus.CONFLICT


def test_same_claim_with_explicit_opposed_authority_is_conflict():
    claim = Claim(claim_id="c-1", text="爭點", kind=ClaimKind.LAW)
    left = Evidence(
        source_id="j-1",
        source_type=SourceType.JUDGMENT,
        title="最高法院見解成立",
        locator="court.example/article/1",
        retrieved_at=NOW,
        supports_claims=[claim.claim_id],
    )
    right = Evidence(
        source_id="j-2",
        source_type=SourceType.JUDGMENT,
        title="最高法院見解不成立，與前案分歧",
        locator="court.example/article/1",
        retrieved_at=NOW,
        supports_claims=[claim.claim_id],
    )
    assert ConflictDetector().detect([claim], [left, right]) is VerificationStatus.CONFLICT


def test_unrelated_authorities_are_not_declared_conflicting():
    claim = Claim(claim_id="c-1", text="爭點", kind=ClaimKind.LAW)
    first = Evidence(
        source_id="j-1", source_type=SourceType.JUDGMENT, title="判決一", locator="court/1", retrieved_at=NOW, supports_claims=[claim.claim_id]
    )
    second = Evidence(
        source_id="j-2", source_type=SourceType.JUDGMENT, title="判決二", locator="court/2", retrieved_at=NOW, supports_claims=[claim.claim_id]
    )
    assert ConflictDetector().detect([claim], [first, second]) is VerificationStatus.VERIFIED

