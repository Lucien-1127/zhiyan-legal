"""End-to-end contracts for the Phase 3 application boundary.

The providers used here are deterministic in-process fakes.  The test still
uses the real Judicial/Regulation adapters, binder, nine-gate pipeline, and
application engine, so a test run never needs network credentials or a model.
"""

from __future__ import annotations

import json

import pytest

from zhiyan_legal.application import ZhiyanApplicationEngine
from zhiyan_legal.domain import (
    Claim,
    ClaimKind,
    ClaimMateriality,
    DeliveryDecision,
    ExecutionContext,
    ExecutionStatus,
    GateId,
    RiskLevel,
    TaskMode,
)
from zhiyan_legal.providers import (
    BaseProviderAdapter,
    ProviderConfig,
    ProviderRegistry,
    ProviderRequest,
    ProviderResponse,
)
from zhiyan_legal.tools import (
    JudicialApiAdapter,
    RegulationApiAdapter,
    ToolCapabilityStatus,
)
from zhiyan_legal.verification import ClaimEvidenceBinder


CLAIM_TEXT = "契約須以書面確認"
GATE_IDS = tuple(GateId(item) for item in (
    "G-SAFETY",
    "G-JURISDICTION",
    "G-FACTS",
    "G-SOURCE",
    "G-SUPPORT",
    "G-TEMPORAL",
    "G-CONFLICT",
    "G-HIGH-IMPACT",
    "G-OUTPUT",
))


class FakeJudicialApi:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def search_judgments(self, keyword: str, **_filters: object) -> list[dict[str, str]]:
        self.calls.append(keyword)
        return [{
            "source_id": "judgment-1",
            "title": "契約判決",
            "locator": f"judgment://judgment-1/{CLAIM_TEXT}",
            "judgment_date": "2020-01-01",
        }]


class FakeRegulationTracker:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def search_law(self, keyword: str) -> list[dict[str, str]]:
        self.calls.append(keyword)
        return [{
            "pcode": "A0001",
            "name": "契約法規",
            "locator": "law://A0001",
            "modifiedDate": "2019-01-01",
        }]


class CountingProvider(BaseProviderAdapter):
    def __init__(self, provider_config: ProviderConfig) -> None:
        super().__init__(provider_config)
        self.calls = 0
        self.requests: list[ProviderRequest] = []

    async def complete(self, request: ProviderRequest) -> ProviderResponse:
        self.calls += 1
        self.requests.append(request)
        return ProviderResponse(
            task_id=request.task_id,
            content="已通過九道閘門的受控回答",
            model=self.model,
            provider_name=self.provider_name,
        )


def _provider() -> tuple[ProviderRegistry, CountingProvider]:
    config = ProviderConfig(
        name="openai",
        base_url="https://provider.example/v1",
        api_key="test-key",
        default_model="test-model",
        priority=0,
    )
    adapter = CountingProvider(config)
    return ProviderRegistry([config], adapters={"openai": adapter}), adapter


async def _retrieved_context() -> tuple[ExecutionContext, FakeJudicialApi, FakeRegulationTracker]:
    judicial_api = FakeJudicialApi()
    regulation_tracker = FakeRegulationTracker()
    judicial = JudicialApiAdapter(api=judicial_api)
    regulation = RegulationApiAdapter(tracker=regulation_tracker)

    judicial_result = await judicial.search_judgments("契約")
    regulation_result = await regulation.search_law("契約")
    assert judicial_result.status is ToolCapabilityStatus.AVAILABLE
    assert regulation_result.status is ToolCapabilityStatus.AVAILABLE
    assert judicial_result.evidence
    assert regulation_result.evidence

    claim = Claim(
        claim_id="claim-contract-1",
        text=CLAIM_TEXT,
        kind=ClaimKind.LAW,
        materiality=ClaimMateriality.CORE,
    )
    bound = ClaimEvidenceBinder(
        citation_id_factory=lambda: "citation-contract-1"
    ).bind(
        claim,
        [*judicial_result.evidence, *regulation_result.evidence],
    )
    assert bound.status.value == "VERIFIED"
    assert len(bound.citations) == 1

    return (
        ExecutionContext(
            execution_id="application-integration",
            status=ExecutionStatus.ANALYZE,
            user_goal="檢視一般契約",
            known_facts=["甲", "2025-01-01", "臺北", "簽署契約", "發生損害"],
            claims=bound.claims,
            evidence=bound.evidence,
            citations=bound.citations,
        ),
        judicial_api,
        regulation_tracker,
    )


@pytest.mark.asyncio
async def test_complete_application_path_binds_sources_runs_nine_gates_and_delivers() -> None:
    context, judicial_api, regulation_tracker = await _retrieved_context()
    registry, provider = _provider()
    engine = ZhiyanApplicationEngine(
        provider_registry=registry,
        tool_adapters=[JudicialApiAdapter(api=judicial_api), RegulationApiAdapter(tracker=regulation_tracker)],
    )

    evaluated, meta, content = await engine.execute(context)

    assert evaluated is not context
    assert evaluated.status is ExecutionStatus.DECIDE
    assert tuple(result.gate_id for result in evaluated.gate_results) == GATE_IDS
    assert all(result.passed for result in evaluated.gate_results)
    assert evaluated.claims[0].status.value == "VERIFIED"
    assert evaluated.citations[0].exact_quote == CLAIM_TEXT
    assert meta.decision is DeliveryDecision.DELIVER
    assert meta.strictness_level == DeliveryDecision.DELIVER.strictness
    assert content == "已通過九道閘門的受控回答"
    assert provider.calls == 1
    assert provider.requests[0].evidence_ids == [
        str(evidence.source_id) for evidence in evaluated.evidence
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("updates", "decision"),
    [
        ({"task_mode": TaskMode.SAFETY}, DeliveryDecision.STOP),
        ({"missing_facts": ["適用法域"]}, DeliveryDecision.ASK),
        ({"risk_level": RiskLevel.HIGH}, DeliveryDecision.HUMAN_REVIEW),
    ],
)
async def test_application_strictness_routes_controlled_decisions_without_provider(
    updates: dict[str, object], decision: DeliveryDecision
) -> None:
    registry, provider = _provider()
    engine = ZhiyanApplicationEngine(provider_registry=registry)
    context = ExecutionContext(
        execution_id="application-controlled",
        user_goal="檢視一般契約",
        known_facts=["甲", "2025-01-01", "臺北", "簽署契約", "發生損害"],
        **updates,
    )

    _evaluated, meta, response = await engine.execute(context)

    assert meta.decision is decision
    assert meta.strictness_level == decision.strictness
    assert provider.calls == 0
    payload = json.loads(response)
    assert payload["decision"] == decision.value
    assert payload["security"]["blocked_provider_call"] is True


@pytest.mark.asyncio
async def test_provider_failure_is_promoted_to_stop_and_cannot_degrade_to_delivery() -> None:
    class FailingProvider(CountingProvider):
        async def complete(self, request: ProviderRequest) -> ProviderResponse:
            self.calls += 1
            raise RuntimeError("provider unavailable")

    config = ProviderConfig(
        name="openai",
        base_url="https://provider.example/v1",
        api_key="test-key",
        default_model="test-model",
        priority=0,
    )
    provider = FailingProvider(config)
    engine = ZhiyanApplicationEngine(
        provider_registry=ProviderRegistry([config], adapters={"openai": provider})
    )

    _context, meta, response = await engine.execute(
        ExecutionContext(
            execution_id="application-provider-failure",
            user_goal="檢視一般契約",
            known_facts=["甲", "2025-01-01", "臺北", "簽署契約", "發生損害"],
        )
    )

    assert meta.decision is DeliveryDecision.STOP
    assert meta.strictness_level == DeliveryDecision.STOP.strictness
    assert meta.tool_failures and "provider" in meta.tool_failures[0]
    assert json.loads(response)["security"]["blocked_provider_call"] is True
