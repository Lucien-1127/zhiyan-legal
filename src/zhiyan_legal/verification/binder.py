"""Bind claims returned by analysis to retrieved evidence.

The domain models are deliberately immutable.  Consequently the binder does
not mutate a ``Claim`` or an ``Evidence`` instance; it returns copies with the
new semantic edges together with the generated citations.
"""

from __future__ import annotations

from array import array
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import cached_property
from typing import Any
from uuid import uuid4

from ..domain import (
    Claim,
    ClaimId,
    ClaimStatus,
    Citation,
    Evidence,
    Jurisdiction,
    VerificationStatus,
)

from ..domain.support import assess_support, matches_citation


def _normalise(value: str) -> str:
    return "".join(value.split()).casefold()


def _source_text(evidence: Evidence, contents: Mapping[Any, str] | None = None) -> str | None:
    # Canonical evidence takes precedence over an adapter's sidecar mapping.
    return evidence.original_text if evidence.original_text is not None else (contents or {}).get(evidence.source_id)


@dataclass
class _SourceText:
    raw: str

    @cached_property
    def normalised(self) -> str:
        return _normalise(self.raw)

    @cached_property
    def offsets(self) -> array:
        # Needed only for non-literal hits. Case folding can expand one
        # source character into multiple search characters (e.g. ß -> ss).
        return array("Q", (
            i for i, ch in enumerate(self.raw) if not ch.isspace() for _ in ch.casefold()
        ))

    def quote(self, text: str, needle: str) -> str | None:
        if not needle:
            return None
        start = self.normalised.find(needle)
        if start < 0:
            return None
        if text in self.raw:
            return text
        offsets = self.offsets
        while start >= 0:
            end = start + len(needle)
            at_start = start == 0 or offsets[start - 1] != offsets[start]
            at_end = end == len(offsets) or offsets[end - 1] != offsets[end]
            if at_start and at_end:
                return self.raw[offsets[start]:offsets[end - 1] + 1]
            start = self.normalised.find(needle, start + 1)
        return None


@dataclass
class BindingResult(Sequence[Citation]):
    """Result of one binding pass.

    Iterating/indexing the result yields citations for callers that only need
    the generated edges.  The updated claims and evidence remain available for
    callers handing the result to ``ExecutionContext``.
    """

    claims: list[Claim]
    evidence: list[Evidence]
    citations: list[Citation]
    statuses: dict[ClaimId, VerificationStatus]
    failures: list[str]
    status: VerificationStatus

    def __len__(self) -> int:
        return len(self.citations)

    def __getitem__(self, index: int | slice) -> Citation | list[Citation]:
        return self.citations[index]

    @property
    def verified_claim_ids(self) -> list[ClaimId]:
        return [claim_id for claim_id, status in self.statuses.items() if status is VerificationStatus.VERIFIED]


class ClaimEvidenceBinder:
    """Bind auditable quotes and verify only supported, eligible claims."""

    def __init__(self, citation_id_factory: Any | None = None) -> None:
        self._citation_id_factory = citation_id_factory or (lambda: f"citation-{uuid4().hex}")

    def bind(
        self,
        claims: Claim | Iterable[Claim],
        evidence: Evidence | Iterable[Evidence],
        *,
        citations: Iterable[Citation] | None = None,
        contents: Mapping[Any, str] | None = None,
        verified_at: datetime | None = None,
        applicable_at: datetime | None = None,
        jurisdiction: Jurisdiction = Jurisdiction.TW,
    ) -> BindingResult:
        claim_list = [claims] if isinstance(claims, Claim) else list(claims)
        evidence_list = [evidence] if isinstance(evidence, Evidence) else list(evidence)
        if any(not isinstance(item, Evidence) for item in evidence_list):
            raise TypeError("evidence items must be canonical Evidence instances")
        citation_list = list(citations or [])
        now = verified_at or datetime.now(timezone.utc)
        sources = [
            item.model_copy(update={"original_text": _source_text(item, contents)})
            for item in evidence_list
        ]
        if len({item.source_id for item in sources}) != len(sources):
            raise ValueError("Evidence source IDs must be unique")
        if len({item.claim_id for item in claim_list}) != len(claim_list):
            raise ValueError("Claim IDs must be unique")
        searchable = {
            item.source_id: _SourceText(item.original_text) for item in sources
            if item.original_text and not item.withdrawn
        }
        citations_by_claim: dict[ClaimId, list[Citation]] = {}
        for citation in citation_list:
            citations_by_claim.setdefault(citation.claim_id, []).append(citation)
        statuses: dict[ClaimId, VerificationStatus] = {}
        failures: list[str] = []
        blocked = {ClaimStatus.STALE, ClaimStatus.CONFLICT}
        for claim in claim_list:
            statuses[claim.claim_id] = VerificationStatus.UNVERIFIED
            if claim.status in blocked:
                statuses[claim.claim_id] = VerificationStatus(claim.status.value)
                continue
            text = claim.text.strip()
            needle = _normalise(text)
            supplied = citations_by_claim.get(claim.claim_id, [])
            for index, item in enumerate(sources):
                source = searchable.get(item.source_id)
                if source is None:
                    continue
                existing = [
                    citation for citation in supplied
                    if matches_citation(claim, citation, item)
                ]
                quote = source.quote(text, needle)
                if (
                    quote is not None
                    and item.verification not in {VerificationStatus.STALE, VerificationStatus.CONFLICT}
                    and all(citation.exact_quote != quote for citation in existing)
                ):
                    if claim.claim_id not in item.supports_claims:
                        item = item.model_copy(update={"supports_claims": [*item.supports_claims, claim.claim_id]})
                        sources[index] = item
                    citation = Citation(
                        citation_id=self._citation_id_factory(), claim_id=claim.claim_id,
                        source_id=item.source_id, locator=item.locator, exact_quote=quote,
                        evidence_level=item.level, verified_at=now,
                    )
                    citation_list.append(citation)
                    existing.append(citation)
                for citation in existing:
                    status = assess_support(claim, citation, item, jurisdiction, applicable_at or now)
                    current = statuses[claim.claim_id]
                    if status is VerificationStatus.CONFLICT or (
                        current is not VerificationStatus.CONFLICT
                        and (status is VerificationStatus.VERIFIED or current is VerificationStatus.UNVERIFIED)
                    ):
                        statuses[claim.claim_id] = status
            if statuses[claim.claim_id] is not VerificationStatus.VERIFIED:
                failures.append(f"命題 {claim.claim_id} 缺少通過原文與支撐驗證的引註")

        updated_claims = [
            claim.model_copy(update={"status": ClaimStatus(statuses[claim.claim_id].value)})
            for claim in claim_list
        ]
        overall = (
            VerificationStatus.VERIFIED
            if claim_list and all(status is VerificationStatus.VERIFIED for status in statuses.values())
            else VerificationStatus.UNVERIFIED
        )
        return BindingResult(updated_claims, sources, citation_list, statuses, failures, overall)

    def bind_context(
        self,
        context: Any,
        *,
        contents: Mapping[Any, str] | None = None,
        verified_at: datetime | None = None,
    ) -> Any:
        """Return an immutable ``ExecutionContext`` with binding applied."""

        result = self.bind(
            context.claims,
            context.evidence,
            citations=context.citations,
            contents=contents,
            verified_at=verified_at,
            applicable_at=context.applicable_at,
            jurisdiction=context.jurisdiction,
        )
        return context.model_copy(
            update={
                "claims": result.claims,
                "evidence": result.evidence,
                "citations": result.citations,
            }
        )

    apply = bind_context

    # Descriptive aliases used by callers that bind a single claim or only
    # need the generated citation collection.
    bind_claims = bind
    bind_claim = bind
    create_citations = bind


__all__ = ["BindingResult", "ClaimEvidenceBinder"]
