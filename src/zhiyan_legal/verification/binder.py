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
    SourceId,
    VerificationStatus,
)


def _value(item: Any, name: str, default: Any = None) -> Any:
    """Read a field from either a canonical model or an adapter payload."""

    if isinstance(item, Mapping):
        return item.get(name, default)
    return getattr(item, name, default)


def _normalise(value: str) -> str:
    return "".join(value.split()).casefold()


def _source_text(evidence: Any, contents: Mapping[Any, str] | None = None) -> str:
    """Return searchable source text without requiring a domain field.

    ``Evidence`` intentionally contains only canonical provenance fields.  A
    retrieval adapter may nevertheless carry source text beside it, so these
    conventional names are accepted as read-only optional attributes.
    """

    source_id = _value(evidence, "source_id")
    if contents:
        for key in (source_id, str(source_id)):
            if key in contents and str(contents[key]).strip():
                return str(contents[key])
    for name in ("content", "full_text", "text", "raw_text"):
        value = _value(evidence, name)
        if value is not None and str(value).strip():
            return str(value)
    return str(_value(evidence, "locator", "") or "")


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
    """Create valid Claim -> Citation -> Evidence semantic edges.

    Evidence is eligible when it explicitly advertises ``supports_claims`` or
    when the claim text can be found in the source material.  In both cases a
    citation is emitted only after an exact quote can be located in the
    locator/content.  This prevents a declared support edge from becoming a
    false VERIFIED claim without source text.
    """

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
    ) -> BindingResult:
        claim_list = [claims] if isinstance(claims, Claim) else list(claims)
        evidence_list = [evidence] if isinstance(evidence, Evidence) else list(evidence)
        if any(not isinstance(item, Evidence) for item in evidence_list):
            raise TypeError("evidence items must be canonical Evidence instances")
        citation_list = list(citations or [])
        now = verified_at or datetime.now(timezone.utc)
        generated_keys: set[tuple[ClaimId, SourceId, str]] = set()
        updated_supports = {item.source_id: list(item.supports_claims) for item in evidence_list}
        statuses: dict[ClaimId, VerificationStatus] = {}
        failures: list[str] = []

        blocked_claims = (ClaimStatus.STALE, ClaimStatus.CONFLICT)
        eligible_claims = {claim.claim_id for claim in claim_list if claim.status not in blocked_claims}
        sources = [
            (item, _SourceText(_source_text(item, contents))) for item in evidence_list
            if item.verification not in (VerificationStatus.STALE, VerificationStatus.CONFLICT)
        ]
        sources_by_id = {item.source_id: (item, source) for item, source in sources}
        verified: set[ClaimId] = set()
        # Preserve supplied citations as audit records. Only eligible, literal
        # source quotes may contribute a verified edge.
        for citation in citation_list:
            claim_id = _value(citation, "claim_id")
            pair = sources_by_id.get(_value(citation, "source_id"))
            if claim_id not in eligible_claims or pair is None:
                continue
            item, source = pair
            quote = _value(citation, "exact_quote")
            if isinstance(quote, str) and quote.strip() and claim_id in item.supports_claims and quote in source.raw:
                verified.add(claim_id)
                generated_keys.add((claim_id, item.source_id, quote))

        for claim in claim_list:
            if claim.status in blocked_claims:
                statuses[claim.claim_id] = VerificationStatus(claim.status.value)
                failures.append(f"命題 {claim.claim_id} 為 {claim.status.value}，不能綁定為 VERIFIED")
                continue

            text = claim.text.strip()
            needle = _normalise(text)
            for item, source in sources:
                quote = source.quote(text, needle)
                if quote is None:
                    continue
                key = (claim.claim_id, item.source_id, quote)
                if key in generated_keys:
                    continue
                citation_list.append(
                    Citation(
                        citation_id=self._citation_id_factory(),
                        claim_id=claim.claim_id,
                        source_id=item.source_id,
                        locator=item.locator,
                        exact_quote=quote,
                        evidence_level=item.level,
                        verified_at=now,
                    )
                )
                generated_keys.add(key)
                updated_supports[item.source_id].append(claim.claim_id)
                verified.add(claim.claim_id)

            if claim.claim_id in verified:
                statuses[claim.claim_id] = VerificationStatus.VERIFIED
            else:
                statuses[claim.claim_id] = VerificationStatus.UNVERIFIED
                failures.append(f"命題 {claim.claim_id} 找不到可核對的 exact_quote")

        updated_claims = [
            claim.model_copy(update={"status": ClaimStatus(statuses[claim.claim_id].value)})
            for claim in claim_list
        ]
        updated_evidence = [
            item.model_copy(update={"supports_claims": list(dict.fromkeys(updated_supports[item.source_id]))})
            for item in evidence_list
        ]
        overall = (
            VerificationStatus.VERIFIED
            if claim_list and all(status is VerificationStatus.VERIFIED for status in statuses.values())
            else VerificationStatus.UNVERIFIED
        )
        return BindingResult(updated_claims, updated_evidence, citation_list, statuses, failures, overall)

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
