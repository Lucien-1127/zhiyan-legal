"""Adapt verified-live judgment search hits to the canonical answer context.

The vector index remains responsible for filtering stale or removed points.
This module only accepts hits that still contain an exact excerpt and an
official source locator, then expresses them as Claim -> Citation -> Evidence
edges for the application gates and provider boundary.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping
from urllib.parse import quote

from .domain import (
    Citation,
    Claim,
    ClaimKind,
    ClaimMateriality,
    ClaimStatus,
    Evidence,
    EvidenceLevel,
    ExecutionContext,
    ExecutionStatus,
    SourceType,
    TaskMode,
    VerificationStatus,
)


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _judgment_date(value: Any) -> datetime | None:
    raw = _text(value)
    for pattern in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, pattern).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _locator(source_url: str, jid: str, chunk_id: str, sequence: Any) -> str:
    # Fragments preserve the configured API/proxy endpoint while making the
    # JID and exact vector chunk visible in every exported citation.
    return (
        f"{source_url}#jid={quote(jid, safe='')}&chunk={quote(chunk_id, safe='')}"
        f"&sequence={quote(str(sequence), safe='')}"
    )


def build_judgment_research_context(
    query: str,
    results: Iterable[Mapping[str, Any]],
    *,
    execution_id: str,
    retrieved_at: datetime | None = None,
) -> ExecutionContext:
    """Build a fail-closed RESEARCH context from live Qdrant search results.

    A semantic match proves only that the excerpt was retrieved, not that the
    judgment governs the user's facts.  Therefore every source is PARTIAL /
    NEED_CHECK and every excerpt claim remains supporting + unverified.  The
    answer layer may quote it, but must disclose applicability limitations.
    """

    now = retrieved_at or datetime.now(timezone.utc)
    claims: list[Claim] = []
    evidence: list[Evidence] = []
    citations: list[Citation] = []
    seen_chunks: set[str] = set()

    for position, result in enumerate(results):
        jid = _text(result.get("jid"))
        excerpt = _text(result.get("text"))
        source_url = _text(result.get("source_url"))
        chunk_id = _text(result.get("id"))
        judgment_date = _judgment_date(result.get("judgment_date"))
        if not all((jid, excerpt, source_url, chunk_id)) or judgment_date is None:
            continue
        if chunk_id in seen_chunks:
            continue
        seen_chunks.add(chunk_id)

        claim_id = f"judgment-excerpt:{chunk_id}"
        source_id = f"judgment:{jid}:{chunk_id}"
        locator = _locator(source_url, jid, chunk_id, result.get("sequence", position))
        title = _text(result.get("title")) or f"司法院裁判書 {jid}"
        claim = Claim(
            claim_id=claim_id,
            text=excerpt,
            kind=ClaimKind.FACT,
            materiality=ClaimMateriality.SUPPORTING,
            status=ClaimStatus.UNVERIFIED,
        )
        source = Evidence(
            source_id=source_id,
            source_type=SourceType.JUDGMENT,
            title=title,
            locator=locator,
            retrieved_at=now,
            effective_at=judgment_date,
            supports_claims=[claim.claim_id],
            verification=VerificationStatus.PARTIAL,
            level=EvidenceLevel.NEED_CHECK,
        )
        citation = Citation(
            citation_id=f"judgment-citation:{chunk_id}",
            claim_id=claim.claim_id,
            source_id=source.source_id,
            locator=locator,
            exact_quote=excerpt,
            evidence_level=EvidenceLevel.NEED_CHECK,
            verified_at=now,
        )
        claims.append(claim)
        evidence.append(source)
        citations.append(citation)

    missing = [] if citations else ["未找到同時具備原文、裁判日期與來源定位的判決切片"]
    return ExecutionContext(
        execution_id=execution_id,
        status=ExecutionStatus.RETRIEVE,
        task_mode=TaskMode.RESEARCH,
        user_goal=query,
        missing_facts=missing,
        claims=claims,
        evidence=evidence,
        citations=citations,
    )


__all__ = ["build_judgment_research_context"]
