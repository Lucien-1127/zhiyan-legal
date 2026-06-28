"""
consensus — Prompt-aware consensus mapper.

Clusters claims from multiple reviewers by dimension + issue content,
then labels each cluster CONSENSUS / DISAGREEMENT / UNIQUE_INSIGHT / BLIND_SPOT.

Parallels committee/mapper.py but specialized for prompt claims.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Optional

from .prompt_quality import (
    PromptClaim, PromptReviewReport, PromptCommitteeReport, ClaimCluster,
    PromptDimension, Severity, ConsensusLabel,
)
from .prompt_normalizer import are_claims_equivalent

logger = logging.getLogger("consensus")


def _cluster_claims(reports: list[PromptReviewReport]) -> list[ClaimCluster]:
    """Group claims across reviewers by equivalent issue.

    Returns list of ClaimCluster, each with a ConsensusLabel.
    """
    all_claims: list[PromptClaim] = []
    for r in reports:
        all_claims.extend(r.claims)

    if not all_claims:
        return []

    # Build adjacency: claims that are equivalent
    # Start with each claim as its own cluster
    clusters: list[list[PromptClaim]] = [[c] for c in all_claims]

    # Merge equivalent claims (simple greedy merge)
    merged = True
    while merged:
        merged = False
        new_clusters: list[list[PromptClaim]] = []
        used = [False] * len(clusters)

        for i in range(len(clusters)):
            if used[i]:
                continue
            current = clusters[i]
            used[i] = True

            for j in range(i + 1, len(clusters)):
                if used[j]:
                    continue
                # Check if any claim in cluster i is equivalent to any in cluster j
                if any(are_claims_equivalent(a, b) for a in current for b in clusters[j]):
                    current.extend(clusters[j])
                    used[j] = True
                    merged = True

            new_clusters.append(current)
        clusters = new_clusters

    # Convert to ClaimCluster objects
    result: list[ClaimCluster] = []
    for group in clusters:
        if not group:
            continue

        # Canonical key: take the most common dimension as key
        dims = [c.dimension for c in group]
        primary_dim = max(set(dims), key=dims.count)

        # Generate key from first claim's issue
        first = group[0]
        key_words = first.issue[:30].strip().replace(" ", "_")
        key = f"{primary_dim.value}:{key_words}"

        models = list(set(c.reviewer.value for c in group))
        issues = [c.issue for c in group]
        suggestions = [c.suggestion for c in group if c.suggestion]
        severities = [c.severity for c in group]

        # Label
        n_models = len(set(c.reviewer for c in group))
        n_total = len(group)

        if n_models >= 2:
            # Multiple models flagged the same issue
            label = ConsensusLabel.CONSENSUS
            detail = f"共{n_models}個模型一致指出 ({', '.join(models)})"
        elif n_models == 1 and n_total >= 1:
            # Only one model flagged it
            label = ConsensusLabel.UNIQUE_INSIGHT
            detail = f"僅{models[0]}提出"
        else:
            label = ConsensusLabel.CONSENSUS
            detail = "單一模型指出"

        result.append(ClaimCluster(
            canonical_key=key,
            dimension=primary_dim,
            models=models,
            issues=issues,
            suggestions=suggestions,
            severities=severities,
            label=label,
            detail=detail,
        ))

    return result


def _estimate_blind_spots(
    reports: list[PromptReviewReport],
    clusters: list[ClaimCluster],
) -> int:
    """Estimate blind spots: dimensions that NO model flagged.

    Heuristic: if a dimension is normally expected to produce findings
    but all reviewers returned empty for it, it may be a blind spot.
    """
    dimensions_flagged = set()
    for c in clusters:
        dimensions_flagged.add(c.dimension)

    # Expected dimensions for a prompt review
    expected = {PromptDimension.STRUCTURE, PromptDimension.COMPLETENESS,
                PromptDimension.PRECISION, PromptDimension.READABILITY}

    blind = expected - dimensions_flagged

    # Also check: if a model returned zero claims, that's suspicious
    empty_models = [r.reviewer.value for r in reports if not r.claims]
    if empty_models:
        logger.warning("Empty reviews from: %s — possible blind spot", empty_models)

    return len(blind)


def generate_report(reports: list[PromptReviewReport]) -> PromptCommitteeReport:
    """Full consensus pipeline: cluster → label → report."""
    if not reports:
        raise ValueError("Need at least one review report")

    prompt_slug = reports[0].prompt_slug

    # 1. Cluster claims
    clusters = _cluster_claims(reports)

    # 2. Estimate blind spots
    n_blind = _estimate_blind_spots(reports, clusters)

    # 3. Count
    n_consensus = sum(1 for c in clusters if c.label == ConsensusLabel.CONSENSUS)
    n_disagreement = sum(1 for c in clusters if c.label == ConsensusLabel.DISAGREEMENT)
    n_unique = sum(1 for c in clusters if c.label == ConsensusLabel.UNIQUE_INSIGHT)

    return PromptCommitteeReport(
        prompt_slug=prompt_slug,
        prompt_vN="",  # filled by caller
        reports=reports,
        clusters=clusters,
        consensus_count=n_consensus,
        disagreement_count=n_disagreement,
        blind_spot_count=n_blind,
        unique_insight_count=n_unique,
    )
