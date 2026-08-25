"""Consensus calculation for the Phase 4 committee.

The evaluator only compares candidate analyses.  It deliberately has no
operation that promotes an unverified claim to ``VERIFIED``.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Iterable, Sequence

from zhiyan_legal.domain import (
    Claim,
    Citation,
    ClaimStatus,
    DeliveryDecision,
    Evidence,
)

from .models import CommitteeMemberVerdict, CommitteeReportVNext, ConsensusStatus


class ConsensusEvaluator:
    """Evaluate member verdicts without overriding deterministic fact gates."""

    def __init__(self, quorum: int = 1) -> None:
        if quorum < 1:
            raise ValueError("quorum must be at least one successful seat")
        self.quorum = quorum

    def evaluate(
        self,
        task_id: str,
        member_verdicts: Sequence[CommitteeMemberVerdict],
        *,
        citations: Iterable[Citation] = (),
        evidence: Iterable[Evidence] = (),
        evaluated_at: datetime | None = None,
    ) -> CommitteeReportVNext:
        """Return an immutable candidate report for supplied seat results."""

        members = list(member_verdicts)
        successful = [member for member in members if self._is_successful(member)]
        failed = [member for member in members if not self._is_successful(member)]
        citation_list = list(citations)
        evidence_list = list(evidence)

        if len(successful) < self.quorum:
            status = ConsensusStatus.BLIND_SPOT
            consensus_claims: list[Claim] = []
            divergent_claims = self._unique_claims(
                claim for member in successful for claim in member.claims
            )
            decision = DeliveryDecision.STOP
        else:
            consensus_claims, divergent_claims = self._compare_claims(
                successful, citation_list, evidence_list
            )
            blind_spot = bool(successful) and all(
                self._normalise_verdict(member.verdict) == "FAIL"
                for member in successful
            )
            disagreement = self._has_substantive_disagreement(
                successful, divergent_claims
            )

            if blind_spot:
                status = ConsensusStatus.BLIND_SPOT
                decision = DeliveryDecision.STOP
            elif disagreement:
                status = ConsensusStatus.DISAGREEMENT
                decision = DeliveryDecision.HUMAN_REVIEW
            elif failed:
                status = ConsensusStatus.PARTIAL_FAILURE
                decision = DeliveryDecision.HUMAN_REVIEW
            else:
                status = ConsensusStatus.CONSENSUS
                decision = self._decision_for_consensus(consensus_claims)

        timestamp = evaluated_at or datetime.now(timezone.utc)
        return CommitteeReportVNext(
            task_id=task_id,
            status=status,
            member_verdicts=members,
            consensus_claims=consensus_claims,
            divergent_claims=divergent_claims,
            recommended_decision=decision,
            recommended_strictness=decision.strictness,
            evaluated_at=timestamp,
        )

    assess = evaluate
    compute = evaluate

    @staticmethod
    def _normalise_verdict(verdict: str) -> str:
        return str(verdict).strip().upper()

    @classmethod
    def _is_successful(cls, member: CommitteeMemberVerdict) -> bool:
        return member.error is None and cls._normalise_verdict(member.verdict) in {
            "PASS",
            "FAIL",
        }

    @staticmethod
    def _supported_claim(
        claim: Claim,
        citations: Sequence[Citation],
        evidence: Sequence[Evidence],
    ) -> bool:
        matches = [citation for citation in citations if citation.claim_id == claim.claim_id]
        if not matches:
            return False
        if not evidence:
            return True
        return any(
            any(
                item.source_id == citation.source_id
                and claim.claim_id in item.supports_claims
                for item in evidence
            )
            for citation in matches
        )

    @classmethod
    def _safe_claim(
        cls,
        claim: Claim,
        citations: Sequence[Citation],
        evidence: Sequence[Evidence],
    ) -> Claim:
        # A model vote is never evidence.  Repair unsupported VERIFIED input
        # as well, so candidate analysis cannot launder an unsafe claim.
        if claim.status is ClaimStatus.VERIFIED and not cls._supported_claim(
            claim, citations, evidence
        ):
            return claim.model_copy(update={"status": ClaimStatus.UNVERIFIED})
        return claim

    @classmethod
    def _compare_claims(
        cls,
        members: Sequence[CommitteeMemberVerdict],
        citations: Sequence[Citation],
        evidence: Sequence[Evidence],
    ) -> tuple[list[Claim], list[Claim]]:
        by_id: dict[str, list[Claim]] = defaultdict(list)
        presence: dict[str, set[int]] = defaultdict(set)
        for member_index, member in enumerate(members):
            for claim in member.claims:
                safe_claim = cls._safe_claim(claim, citations, evidence)
                claim_id = str(safe_claim.claim_id)
                by_id[claim_id].append(safe_claim)
                presence[claim_id].add(member_index)

        consensus: list[Claim] = []
        divergent: list[Claim] = []
        for claim_id, claims in by_id.items():
            first = claims[0]
            same_claim = all(
                cls._claim_fingerprint(claim) == cls._claim_fingerprint(first)
                for claim in claims
            )
            present_in_all = len(presence[claim_id]) == len(members)
            if same_claim and present_in_all:
                consensus.append(first)
            else:
                divergent.extend(cls._unique_claims(claims))
        return consensus, divergent

    @staticmethod
    def _claim_fingerprint(claim: Claim) -> tuple[object, ...]:
        return (
            str(claim.claim_id),
            claim.text,
            claim.kind,
            claim.materiality,
            claim.status,
        )

    @staticmethod
    def _unique_claims(claims: Iterable[Claim]) -> list[Claim]:
        result: list[Claim] = []
        seen: set[tuple[object, ...]] = set()
        for claim in claims:
            fingerprint = ConsensusEvaluator._claim_fingerprint(claim)
            if fingerprint not in seen:
                seen.add(fingerprint)
                result.append(claim)
        return result

    @classmethod
    def _has_substantive_disagreement(
        cls,
        members: Sequence[CommitteeMemberVerdict],
        divergent_claims: Sequence[Claim],
    ) -> bool:
        if divergent_claims:
            return True
        verdicts = {cls._normalise_verdict(member.verdict) for member in members}
        return len(verdicts) > 1

    @staticmethod
    def _decision_for_consensus(claims: Sequence[Claim]) -> DeliveryDecision:
        # Candidate analysis stays conservative around unresolved facts.  The
        # application GatePipeline remains the final authority.
        if any(
            claim.status in {
                ClaimStatus.UNVERIFIED,
                ClaimStatus.CONFLICT,
                ClaimStatus.STALE,
            }
            for claim in claims
        ):
            return DeliveryDecision.HUMAN_REVIEW
        return DeliveryDecision.DELIVER


__all__ = ["ConsensusEvaluator"]
