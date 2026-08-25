"""Adapter from the historical committee HTTP shape to Committee vNext.

The API layer is intentionally thin. Provider fan-out, response parsing and
decision recommendations all belong to :class:`CommitteeEngine`; this module
only selects configured seats and maps the canonical report for old clients.
"""

from __future__ import annotations

from typing import Any, Sequence

from zhiyan_legal.committee import CommitteeEngine, CommitteeReportVNext
from zhiyan_legal.providers import ProviderRegistry


def _registry_for_models(models: Sequence[str] | None) -> ProviderRegistry:
    registry = ProviderRegistry.from_env()
    requested = {str(model) for model in (models or ())}
    if not requested:
        return registry

    selected = tuple(
        provider
        for provider in registry.providers
        if provider.name in requested or provider.default_model in requested
    )
    return ProviderRegistry(selected) if selected else registry


async def run_committee(
    query: str,
    models: Sequence[str] = (),
    temperature: float = 0.3,
    max_tokens: int = 4096,
    *,
    task_id: str = "committee-api",
    committee_engine: CommitteeEngine | None = None,
) -> CommitteeReportVNext:
    """Run one canonical vNext committee report.

    ``temperature`` and ``max_tokens`` remain accepted for wire compatibility;
    the canonical ProviderRequest contract currently controls provider limits.
    """
    del temperature, max_tokens
    engine = committee_engine or CommitteeEngine(
        provider_registry=_registry_for_models(models)
    )
    return await engine.run(
        task_id=task_id,
        instructions=query,
        output_schema="committee",
    )


# Historical function name retained as a vNext report-producing compatibility
# boundary.
run_parallel = run_committee


def normalize(report: CommitteeReportVNext, layer: str) -> CommitteeReportVNext:
    """Compatibility no-op; normalization is part of CommitteeEngine parsing."""
    del layer
    return report


def build_synthesis(
    report: CommitteeReportVNext,
    mode: str = "mark",
    threshold: float = 0.75,
) -> dict[str, Any]:
    """Map a canonical report to the legacy synthesis fields."""
    del mode, threshold
    members_by_claim: dict[str, list[str]] = {}
    for member in report.member_verdicts:
        for claim in member.claims:
            members_by_claim.setdefault(str(claim.claim_id), []).append(
                member.provider_name
            )

    consensus = [
        {
            "claim": claim.text,
            "models": members_by_claim.get(str(claim.claim_id), []),
        }
        for claim in report.consensus_claims
    ]
    divergence = [
        {
            "claim": claim.text,
            "model_a": members_by_claim.get(str(claim.claim_id), ["?"])[0],
            "position_a": "candidate",
            "model_b": members_by_claim.get(str(claim.claim_id), ["?", "?"])[-1],
            "position_b": "divergent",
        }
        for claim in report.divergent_claims
    ]
    return {
        "consensus": consensus,
        "divergence": divergence,
        "unique": [],
        "quota": {},
        "status": report.status.value,
        "recommended_decision": report.recommended_decision.value,
        "recommended_strictness": int(report.recommended_strictness),
    }


__all__ = [
    "build_synthesis",
    "normalize",
    "run_committee",
    "run_parallel",
]
