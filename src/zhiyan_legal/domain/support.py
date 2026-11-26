"""Deterministic checks on the canonical provenance and support edge."""

from datetime import datetime
from urllib.parse import urlsplit

from .claims import Claim, ClaimKind, ClaimStatus
from .evidence import Citation, Evidence, EvidenceLevel, SourceType, VerificationStatus
from .risk import Jurisdiction

from .temporal import TemporalVerifier


PRIMARY_SOURCE_TYPES = frozenset({SourceType.STATUTE, SourceType.JUDGMENT, SourceType.OFFICIAL})


def is_official_source(evidence: Evidence) -> bool:
    if (
        evidence.source_type not in PRIMARY_SOURCE_TYPES
        or evidence.jurisdiction is not Jurisdiction.TW
        or not evidence.source_id.strip()
        or not evidence.title.strip()
    ):
        return False
    try:
        url = urlsplit(evidence.locator)
    except ValueError:
        return False
    host = url.hostname or ""
    if url.scheme != "https" or url.username is not None or not url.path.strip("/"):
        return False
    if evidence.source_type is SourceType.STATUTE:
        return host == "law.moj.gov.tw"
    if evidence.source_type is SourceType.JUDGMENT:
        return host == "judicial.gov.tw" or host.endswith(".judicial.gov.tw")
    return host.endswith(".gov.tw")


def matches_citation(claim: Claim, citation: Citation, evidence: Evidence) -> bool:
    """Validate the published reference independently of its legal relevance."""
    return (
        bool(citation.citation_id.strip() and citation.exact_quote.strip())
        and citation.claim_id == claim.claim_id
        and citation.source_id == evidence.source_id
        and claim.claim_id in evidence.supports_claims
        and bool(evidence.locator.strip())
        and citation.locator == evidence.locator
        and citation.evidence_level is evidence.level
        and evidence.original_text is not None
        and citation.exact_quote in evidence.original_text
    )


def assess_support(
    claim: Claim,
    citation: Citation,
    evidence: Evidence,
    jurisdiction: Jurisdiction,
    applicable_at: datetime | None,
) -> VerificationStatus:
    if evidence.withdrawn or not matches_citation(claim, citation, evidence):
        return VerificationStatus.UNVERIFIED
    if not is_official_source(evidence) or evidence.jurisdiction is not jurisdiction:
        return VerificationStatus.UNVERIFIED
    if claim.status is ClaimStatus.CONFLICT or evidence.verification is VerificationStatus.CONFLICT:
        return VerificationStatus.CONFLICT
    temporal = TemporalVerifier().verify(evidence, applicable_at)
    if claim.status is ClaimStatus.STALE or temporal is VerificationStatus.STALE:
        return VerificationStatus.STALE
    if (
        temporal is not VerificationStatus.VERIFIED
        or evidence.verification is not VerificationStatus.VERIFIED
        or evidence.level is not EvidenceLevel.VERIFIED
        or not evidence.version
    ):
        return VerificationStatus.UNVERIFIED
    # A complete independently retrieved passage can establish a literal
    # proposition. A fragment may omit negation, exceptions or qualifications.
    # There is no trusted semantic adjudicator for paraphrases or inference.
    if (
        claim.kind in {ClaimKind.LAW, ClaimKind.PROCEDURE}
        and citation.exact_quote.strip() == evidence.original_text.strip()
        and " ".join(claim.text.split()) == " ".join(evidence.original_text.split())
    ):
        return VerificationStatus.VERIFIED
    return VerificationStatus.UNVERIFIED
