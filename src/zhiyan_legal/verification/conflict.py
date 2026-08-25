"""Detect unresolved disagreement in authoritative evidence."""

from __future__ import annotations

from dataclasses import dataclass
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import Any

from ..domain import (
    Claim,
    ClaimStatus,
    Citation,
    Evidence,
    SourceType,
    VerificationStatus,
)


_AUTHORITATIVE = frozenset({SourceType.STATUTE, SourceType.JUDGMENT, SourceType.OFFICIAL})
_CONFLICT_WORDS = re.compile(
    r"(?:衝突|矛盾|分歧|不一致|相反|不同見解|conflict|contradict|dissent|overruled)",
    re.IGNORECASE,
)


def _field(item: Any, name: str, default: Any = None) -> Any:
    if isinstance(item, Mapping):
        return item.get(name, default)
    return getattr(item, name, default)


@dataclass(frozen=True)
class Conflict:
    """A concise, auditable description of a detected disagreement."""

    key: str
    source_ids: tuple[str, ...]
    reason: str


def _key(evidence: Any) -> str:
    # Adapter metadata is preferred.  The canonical fallback groups evidence
    # by its declared claim edges; source IDs alone would falsely classify two
    # articles from one statute as a conflict.
    for name in ("issue_id", "article", "article_id", "topic", "dispute_key"):
        value = _field(evidence, name)
        if value is not None and str(value).strip():
            return str(value).strip().casefold()
    locator = str(_field(evidence, "locator", "") or "")
    match = re.search(r"(?:article|art|條文|條|issue|topic)[^/#?=&]*[=#/: -]*([\w.-]+)", locator, re.IGNORECASE)
    return match.group(1).casefold() if match else ""


class ConflictDetector:
    """Detect explicit or strongly indicated authority conflicts.

    Semantic opposition cannot be safely inferred from arbitrary prose.  This
    detector therefore uses explicit conflict states/metadata and conservative
    markers, while grouping only evidence that declares the same claim or
    article/issue.
    """

    def find_conflicts(
        self,
        claims: Iterable[Claim] | None = None,
        evidence: Iterable[Evidence] | None = None,
        citations: Iterable[Citation] | None = None,
    ) -> list[Conflict]:
        claim_list = list(claims or [])
        evidence_list = list(evidence or [])
        citation_list = list(citations or [])
        conflicts: list[Conflict] = []

        if any(claim.status is ClaimStatus.CONFLICT for claim in claim_list):
            conflicts.append(Conflict("claims", tuple(str(c.claim_id) for c in claim_list if c.status is ClaimStatus.CONFLICT), "命題已標記為 CONFLICT"))
        marked = [item for item in evidence_list if _field(item, "verification") in (VerificationStatus.CONFLICT, VerificationStatus.CONFLICT.value)]
        if marked:
            conflicts.append(Conflict("evidence", tuple(str(_field(item, "source_id")) for item in marked), "Evidence 已標記為 CONFLICT"))

        claims_by_id = {claim.claim_id: claim for claim in claim_list}
        groups: defaultdict[str, list[Any]] = defaultdict(list)
        for item in evidence_list:
            if _field(item, "source_type") not in _AUTHORITATIVE:
                continue
            item_claims = list(_field(item, "supports_claims", []) or [])
            for claim_id in item_claims:
                if claim_id in claims_by_id:
                    groups[f"claim:{claim_id}"].append(item)
            issue = _key(item)
            if issue:
                groups[f"issue:{issue}"].append(item)

        # Citation text is optional, but when present it gives a useful
        # conservative signal for clearly opposed authoritative statements.
        quotes_by_source = {citation.source_id: citation.exact_quote for citation in citation_list}
        for group_key, items in groups.items():
            unique = {str(_field(item, "source_id")): item for item in items}
            if len(unique) < 2:
                continue
            rendered = [
                " ".join(
                    str(_field(item, name, "") or "")
                    for name in ("title", "locator", "content", "full_text", "text", "raw_text")
                )
                + " "
                + str(quotes_by_source.get(_field(item, "source_id"), ""))
                for item in unique.values()
            ]
            if any(_CONFLICT_WORDS.search(text) for text in rendered):
                conflicts.append(
                    Conflict(group_key, tuple(unique), "同一命題或爭點存在明示的權威見解分歧")
                )
        return conflicts

    def detect(
        self,
        claims_or_evidence: Iterable[Claim] | Iterable[Evidence] | None = None,
        evidence: Iterable[Evidence] | None = None,
        citations: Iterable[Citation] | None = None,
        *,
        claims: Iterable[Claim] | None = None,
    ) -> VerificationStatus:
        if claims is not None:
            claims_or_evidence = claims
        if evidence is None:
            values = list(claims_or_evidence or [])
            claims = [item for item in values if isinstance(item, Claim)]
            evidence = [item for item in values if isinstance(item, Evidence)]
        else:
            claims = list(claims_or_evidence or [])  # type: ignore[arg-type]
        return VerificationStatus.CONFLICT if self.find_conflicts(claims, evidence, citations) else VerificationStatus.VERIFIED

    verify = detect
    check = detect
    evaluate = detect


__all__ = ["Conflict", "ConflictDetector"]
