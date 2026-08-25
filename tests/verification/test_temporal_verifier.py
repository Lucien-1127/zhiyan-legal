from datetime import datetime, timezone

from zhiyan_legal.domain import Evidence, SourceType, VerificationStatus
from zhiyan_legal.verification import TemporalVerifier


def evidence(**updates):
    values = {
        "source_id": "s-1",
        "source_type": SourceType.STATUTE,
        "title": "民法",
        "locator": "law.example/article/1",
        "retrieved_at": datetime(2026, 8, 25, tzinfo=timezone.utc),
        "effective_at": datetime(2020, 1, 1, tzinfo=timezone.utc),
    }
    values.update(updates)
    return Evidence(**values)


def test_temporal_verifier_accepts_effective_source_at_case_time():
    verifier = TemporalVerifier()
    assert verifier.verify(evidence(), datetime(2025, 1, 1, tzinfo=timezone.utc)) is VerificationStatus.VERIFIED


def test_temporal_verifier_returns_stale_for_future_or_marked_stale_source():
    verifier = TemporalVerifier()
    assert verifier.verify(evidence(effective_at=datetime(2026, 1, 1, tzinfo=timezone.utc)), datetime(2025, 1, 1, tzinfo=timezone.utc)) is VerificationStatus.STALE
    assert verifier.verify(evidence(verification=VerificationStatus.STALE)) is VerificationStatus.STALE


def test_temporal_verifier_keeps_unknown_effective_date_unverified():
    assert TemporalVerifier().verify(evidence(effective_at=None)) is VerificationStatus.UNVERIFIED

