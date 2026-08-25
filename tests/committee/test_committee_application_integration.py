"""End-to-end contracts for Committee vNext at the application boundary."""

from __future__ import annotations

import json

import pytest

from zhiyan_legal.application import ZhiyanApplicationEngine
from zhiyan_legal.domain import DeliveryDecision, ExecutionContext
from zhiyan_legal.providers import (
    BaseProviderAdapter,
    ProviderConfig,
    ProviderRegistry,
    ProviderRequest,
    ProviderResponse,
)
from zhiyan_legal.committee import CommitteeEngine, ConsensusStatus


class RecordingAdapter(BaseProviderAdapter):
    def __init__(self, config: ProviderConfig, content: str) -> None:
        super().__init__(config)
        self.content = content
        self.calls = 0

    async def complete(self, request: ProviderRequest) -> ProviderResponse:
        self.calls += 1
        return ProviderResponse(
            task_id=request.task_id,
            content=self.content,
            model=self.model,
            provider_name=self.provider_name,
        )


def _context() -> ExecutionContext:
    return ExecutionContext(
        execution_id="committee-application-integration",
        user_goal="檢視一般契約",
        known_facts=["甲", "2025-01-01", "臺北", "簽署契約", "發生損害"],
    )


def _registry(contents: tuple[str, str]):
    configs = [
        ProviderConfig(
            name=name,
            base_url=f"https://{name}.example/v1",
            api_key="test-key",
            default_model=f"{name}-model",
            priority=index,
        )
        for index, name in enumerate(("one", "two"))
    ]
    adapters = {
        config.name: RecordingAdapter(config, contents[index])
        for index, config in enumerate(configs)
    }
    return ProviderRegistry(configs, adapters=adapters), adapters


@pytest.mark.asyncio
async def test_disagreement_is_raised_to_human_review_and_blocks_delivery() -> None:
    registry, adapters = _registry((json.dumps({"verdict": "PASS"}), json.dumps({"verdict": "FAIL"})))
    engine = ZhiyanApplicationEngine(
        provider_registry=registry,
        committee_engine=CommitteeEngine(provider_registry=registry),
    )

    _evaluated, meta, response = await engine.execute(_context())

    assert engine.last_committee_report is not None
    assert engine.last_committee_report.status is ConsensusStatus.DISAGREEMENT
    assert meta.decision is DeliveryDecision.HUMAN_REVIEW
    assert json.loads(response)["security"]["blocked_provider_call"] is True
    # Two committee seats ran; no post-committee drafter was allowed to run.
    assert [adapter.calls for adapter in adapters.values()] == [1, 1]


@pytest.mark.asyncio
async def test_blind_spot_is_raised_to_stop_and_cannot_degrade_to_deliver() -> None:
    registry, adapters = _registry(("not-json", "also-not-json"))
    engine = ZhiyanApplicationEngine(
        provider_registry=registry,
        committee_engine=CommitteeEngine(provider_registry=registry),
    )

    _evaluated, meta, response = await engine.execute(_context())

    assert engine.last_committee_report is not None
    assert engine.last_committee_report.status is ConsensusStatus.BLIND_SPOT
    assert meta.decision is DeliveryDecision.STOP
    assert json.loads(response)["decision"] == "STOP"
    assert [adapter.calls for adapter in adapters.values()] == [1, 1]
