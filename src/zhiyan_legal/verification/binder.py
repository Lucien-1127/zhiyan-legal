"""Bind claims returned by analysis to retrieved evidence.

The domain models are deliberately immutable.  Consequently the binder does
not mutate a ``Claim`` or an ``Evidence`` instance; it returns copies with the
new semantic edges together with the generated citations.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Any, overload
from uuid import uuid4

from ..domain import (
    Claim,
    ClaimId,
    ClaimStatus,
    Citation,
    Evidence,
    EvidenceLevel,
    SourceId,
    VerificationStatus,
)


def _value(item: Any, name: str, default: Any = None) -> Any:
    """Read a field from either a canonical model or an adapter payload."""

    if isinstance(item, Mapping):
        return item.get(name, default)
    return getattr(item, name, default)


def _normalise(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "")).casefold()


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


def _contains(needle: str, haystack: str) -> bool:
    needle_n = _normalise(needle)
    return bool(needle_n and needle_n in _normalise(haystack))


def _quote_from_source(claim: Claim, evidence: Any, contents: Mapping[Any, str] | None) -> str | None:
    source = _source_text(evidence, contents)
    if not _contains(claim.text, source):
        return None

    # Preserve the claim's spelling when whitespace-only differences occur;
    # this still represents the exact source phrase for citation purposes.
    source_n = _normalise(source)
    claim_n = _normalise(claim.text)
    if claim_n in source_n:
        return claim.text.strip()

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

    @overload
    def bind(
        self,
        claims: Claim | Iterable[Claim],
        evidence: Evidence | Iterable[Evidence],
        *,
        citations: Iterable[Citation] | None = None,
        contents: Mapping[Any, str] | None = None,
        verified_at: datetime | None = None,
    ) -> BindingResult: ...

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
        existing = list(citations or [])
        now = verified_at or datetime.now(timezone.utc)

        # Keep input citations, but never let a duplicate generated edge hide
        # a malformed existing one.
        citation_list = list(existing)
        generated_keys: set[tuple[ClaimId, SourceId, str]] = set()
        updated_supports: dict[SourceId, list[ClaimId]] = {
            _value(item, "source_id"): list(_value(item, "supports_claims", []) or [])
            for item in evidence_list
        }
        statuses: dict[ClaimId, VerificationStatus] = {}
        failures: list[str] = []
        valid_by_claim: dict[ClaimId, bool] = {claim.claim_id: False for claim in claim_list}

        claims_by_id = {claim.claim_id: claim for claim in claim_list}
        evidence_by_id = {_value(item, "source_id"): item for item in evidence_list}
        # Validate supplied citations before generating new ones.  A pre-bound
        # citation is usable only when its quote is present in the same source
        # and the source explicitly supports the referenced claim.
        for citation in citation_list:
            claim = claims_by_id.get(_value(citation, "claim_id"))
            item = evidence_by_id.get(_value(citation, "source_id"))
            if claim is None or item is None:
                continue
            quote = str(_value(citation, "exact_quote", "") or "").strip()
            supports = _value(item, "supports_claims", []) or []
            if quote and claim.claim_id in supports and _contains(quote, _source_text(item, contents)):
                valid_by_claim[claim.claim_id] = True
                updated_supports[_value(item, "source_id")].append(claim.claim_id)
                generated_keys.add((claim.claim_id, _value(item, "source_id"), quote))

        for claim in claim_list:
            for item in evidence_list:
                source_id = _value(item, "source_id")
                current_verification = _value(item, "verification", VerificationStatus.UNVERIFIED)
                if current_verification in (
                    VerificationStatus.STALE,
                    VerificationStatus.STALE.value,
                    VerificationStatus.CONFLICT,
                    VerificationStatus.CONFLICT.value,
                ):
                    continue
                declared = claim.claim_id in (_value(item, "supports_claims", []) or [])
                quote = _quote_from_source(claim, item, contents)
                if quote is None:
                    continue
                # Text match itself is sufficient for a retrieval result; an
                # explicit support edge is retained and automatically added
                # when the match establishes the edge.
                if not declared:
                    updated_supports[source_id].append(claim.claim_id)
                key = (claim.claim_id, source_id, quote)
                if key in generated_keys:
                    valid_by_claim[claim.claim_id] = True
                    continue
                evidence_level = _value(item, "level", EvidenceLevel.NEED_CHECK)
                citation_list.append(
                    Citation(
                        citation_id=self._citation_id_factory(),
                        claim_id=claim.claim_id,
                        source_id=source_id,
                        locator=_value(item, "locator", ""),
                        exact_quote=quote,
                        evidence_level=evidence_level,
                        verified_at=now,
                    )
                )
                generated_keys.add(key)
                valid_by_claim[claim.claim_id] = True

            if valid_by_claim[claim.claim_id]:
                statuses[claim.claim_id] = VerificationStatus.VERIFIED
            elif claim.status is ClaimStatus.CONFLICT:
                statuses[claim.claim_id] = VerificationStatus.CONFLICT
                failures.append(f"命題 {claim.claim_id} 存在衝突，不能綁定為 VERIFIED")
            elif claim.status is ClaimStatus.STALE:
                statuses[claim.claim_id] = VerificationStatus.STALE
                failures.append(f"命題 {claim.claim_id} 已過期，不能綁定為 VERIFIED")
            else:
                statuses[claim.claim_id] = VerificationStatus.UNVERIFIED
                failures.append(f"命題 {claim.claim_id} 找不到可核對的 exact_quote")

        updated_claims = [
            claim.model_copy(
                update={
                    "status": (
                        ClaimStatus.VERIFIED
                        if valid_by_claim[claim.claim_id]
                        else (
                            ClaimStatus.CONFLICT
                            if claim.status is ClaimStatus.CONFLICT
                            else ClaimStatus.STALE
                            if claim.status is ClaimStatus.STALE
                            else ClaimStatus.UNVERIFIED
                        )
                    )
                }
            )
            for claim in claim_list
        ]
        updated_evidence: list[Evidence] = []
        for item in evidence_list:
            source_id = _value(item, "source_id")
            supports = list(dict.fromkeys(updated_supports[source_id]))
            if isinstance(item, Evidence):
                updated_evidence.append(item.model_copy(update={"supports_claims": supports}))
            else:
                # Binder's public contract is canonical Evidence; this branch
                # gives adapter callers a clear error instead of silently
                # returning a non-canonical object.
                raise TypeError("evidence items must be canonical Evidence instances")

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
