"""Temporal validity checks for legal evidence."""

from __future__ import annotations

from datetime import datetime
import re
from collections.abc import Iterable, Mapping
from typing import Any

from ..domain import Evidence, SourceId, VerificationStatus


_REPEALED = re.compile(r"(?:廢止|失效|撤銷|repealed|revoked|superseded|obsolete)", re.IGNORECASE)


def _field(item: Any, name: str, default: Any = None) -> Any:
    if isinstance(item, Mapping):
        return item.get(name, default)
    return getattr(item, name, default)


def _aware_pair(left: datetime, right: datetime) -> tuple[datetime, datetime]:
    if left.tzinfo is None and right.tzinfo is not None:
        left = left.replace(tzinfo=right.tzinfo)
    elif right.tzinfo is None and left.tzinfo is not None:
        right = right.replace(tzinfo=left.tzinfo)
    return left, right


class TemporalVerifier:
    """Determine whether evidence is usable at an applicable point in time.

    ``effective_at`` is the only canonical date describing legal effect.  A
    missing date therefore remains ``UNVERIFIED`` (unknown), while an
    effective date after the requested point, after retrieval, or an explicit
    repeal marker is ``STALE``.
    """

    def verify(
        self,
        evidence: Evidence,
        applicable_at: datetime | None = None,
        *,
        as_of: datetime | None = None,
    ) -> VerificationStatus:
        point = applicable_at or as_of
        current = _field(evidence, "verification", VerificationStatus.UNVERIFIED)
        if current is VerificationStatus.STALE or str(current) == VerificationStatus.STALE.value:
            return VerificationStatus.STALE

        marker = " ".join(
            str(_field(evidence, name, "") or "")
            for name in ("title", "locator", "status", "repealed_at", "valid_until", "expires_at")
        )
        if _REPEALED.search(marker):
            return VerificationStatus.STALE

        effective_at = _field(evidence, "effective_at")
        retrieved_at = _field(evidence, "retrieved_at")
        if effective_at is None:
            return VerificationStatus.UNVERIFIED
        if not isinstance(effective_at, datetime) or not isinstance(retrieved_at, datetime):
            return VerificationStatus.UNVERIFIED

        effective_at, retrieved_at = _aware_pair(effective_at, retrieved_at)
        if effective_at > retrieved_at:
            return VerificationStatus.STALE
        if point is not None:
            effective_at, point = _aware_pair(effective_at, point)
            if effective_at > point:
                return VerificationStatus.STALE

        valid_until = _field(evidence, "valid_until") or _field(evidence, "expires_at")
        if isinstance(valid_until, datetime):
            valid_until, point_for_expiry = _aware_pair(valid_until, point or retrieved_at)
            if point_for_expiry >= valid_until:
                return VerificationStatus.STALE

        return VerificationStatus.VERIFIED

    check = verify
    evaluate = verify

    def verify_all(
        self,
        evidence: Iterable[Evidence],
        applicable_at: datetime | None = None,
        *,
        as_of: datetime | None = None,
    ) -> dict[SourceId, VerificationStatus]:
        return {
            _field(item, "source_id"): self.verify(item, applicable_at, as_of=as_of)
            for item in evidence
        }

    def is_stale(self, evidence: Evidence, applicable_at: datetime | None = None) -> bool:
        return self.verify(evidence, applicable_at) is VerificationStatus.STALE


__all__ = ["TemporalVerifier"]
