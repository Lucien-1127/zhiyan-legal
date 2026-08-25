"""Acceptance tests for the Phase 4 multi-model committee."""

from __future__ import annotations

import asyncio
import json

from zhiyan_legal.committee import (
    CommitteeEngine,
    CommitteeMemberVerdict,
    ConsensusEvaluator,
    ConsensusStatus,
)
from zhiyan_legal.domain import Claim, ClaimKind, ClaimStatus
from zhiyan_legal.providers import (
    BaseProviderAdapter,
    ProviderConfig,
    ProviderRegistry,
    ProviderRequest,
    ProviderResponse,
    ProviderRole,
)


def _claim(status: ClaimStatus = ClaimStatus.UNVERIFIED) -> Claim:
    return Claim(
        claim_id="claim-1",
        text="待查證命題",
        kind=ClaimKind.FACT,
        status=status,
    )


def _member(name: str, verdict: str = "PASS", *, error: str | None = None):
    return CommitteeMemberVerdict(
        provider_name=name,
        model=f"{name}-model",
        role=ProviderRole.VERIFIER,
        claims=[_claim()],
        verdict=verdict,
        error=error,
    )


def test_unverified_claim_is_not_promoted_by_unanimous_pass() -> None:
    report = ConsensusEvaluator().evaluate(
        "task-1",
        [_member("one"), _member("two"), _member("three")],
    )

    assert report.status is ConsensusStatus.CONSENSUS
    assert report.consensus_claims[0].status is ClaimStatus.UNVERIFIED
    assert report.recommended_decision.value == "HUMAN_REVIEW"


def test_substantive_disagreement_recommends_human_review() -> None:
    first = _member("one", "PASS")
    second = _member("two", "FAIL")

    report = ConsensusEvaluator().evaluate("task-2", [first, second])

    assert report.status is ConsensusStatus.DISAGREEMENT
    assert report.recommended_decision.value == "HUMAN_REVIEW"
    assert report.recommended_strictness.name == "HUMAN_REVIEW"


class _StubAdapter(BaseProviderAdapter):
    def __init__(self, config: ProviderConfig, content: str = "PASS", error=None):
        super().__init__(config)
        self.content = content
        self.error = error

    async def complete(self, request: ProviderRequest) -> ProviderResponse:
        if self.error is not None:
            raise self.error
        return ProviderResponse(
            task_id=request.task_id,
            content=self.content,
            model=self.model,
            provider_name=self.provider_name,
        )


def _config(name: str, priority: int) -> ProviderConfig:
    return ProviderConfig(
        name=name,
        base_url=f"https://{name}.example/v1",
        api_key=f"{name}-key",
        default_model=f"{name}-model",
        priority=priority,
    )


def test_provider_failure_is_recorded_as_partial_failure() -> None:
    first = _config("openai", 10)
    second = _config("deepseek", 20)
    registry = ProviderRegistry(
        [first, second],
        adapters={
            "openai": _StubAdapter(first, error=TimeoutError("timed out")),
            "deepseek": _StubAdapter(
                second,
                content=json.dumps(
                    {
                        "verdict": "PASS",
                        "claims": [
                            {
                                "claim_id": "claim-1",
                                "text": "待查證命題",
                                "kind": "FACT",
                                "status": "UNVERIFIED",
                            }
                        ],
                    }
                ),
            ),
        },
    )

    report = asyncio.run(
        CommitteeEngine(provider_registry=registry).run("task-3", "evaluate")
    )

    assert report.status is ConsensusStatus.PARTIAL_FAILURE
    assert len(report.member_verdicts) == 2
    failed = next(member for member in report.member_verdicts if member.provider_name == "openai")
    assert failed.error and "TimeoutError" in failed.error

