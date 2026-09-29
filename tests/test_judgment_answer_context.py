"""Qdrant hits must enter the canonical answer path without fake facts."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from zhiyan_legal.application import ZhiyanApplicationEngine
from zhiyan_legal.domain import DeliveryDecision, GateId, RiskLevel
from zhiyan_legal.judgment_answer import build_judgment_research_context
from zhiyan_legal.providers import (
    BaseProviderAdapter,
    ProviderConfig,
    ProviderRegistry,
    ProviderRequest,
    ProviderResponse,
)


STAMP = datetime(2026, 9, 26, tzinfo=timezone.utc)
HIT = {
    "id": "chunk-3",
    "jid": "TPHM,110,毒抗,1212,20210831,1",
    "text": "法院認定本件再犯期間應依裁判時法規與個案事實審查。",
    "sequence": 3,
    "judgment_date": "20210831",
    "title": "臺灣高等法院 110年度毒抗字第1212號",
    "source_url": "https://data.judicial.gov.tw/jdg/api/JDoc",
}


class RecordingProvider(BaseProviderAdapter):
    def __init__(self) -> None:
        config = ProviderConfig(
            name="openai",
            base_url="https://provider.example/v1",
            api_key="test-key",
            default_model="test-model",
            priority=0,
        )
        super().__init__(config)
        self.requests: list[ProviderRequest] = []

    async def complete(self, request: ProviderRequest) -> ProviderResponse:
        self.requests.append(request)
        return ProviderResponse(
            task_id=request.task_id,
            content="依檢索到的判決原文回答，個案適用仍須人工覆核。",
            model=self.model,
            provider_name=self.provider_name,
        )


class FailingProvider(RecordingProvider):
    async def complete(self, request: ProviderRequest) -> ProviderResponse:
        self.requests.append(request)
        raise RuntimeError("synthetic model failure")


def _engine() -> tuple[ZhiyanApplicationEngine, RecordingProvider]:
    provider = RecordingProvider()
    registry = ProviderRegistry(
        [provider.config],
        adapters={"openai": provider},
    )
    return ZhiyanApplicationEngine(provider_registry=registry), provider


def _engine_with(provider: RecordingProvider) -> ZhiyanApplicationEngine:
    return ZhiyanApplicationEngine(
        provider_registry=ProviderRegistry(
            [provider.config],
            adapters={"openai": provider},
        )
    )


def test_builder_preserves_exact_qdrant_excerpt_and_source_locator() -> None:
    context = build_judgment_research_context(
        "毒品再犯期間如何判斷？",
        [HIT],
        execution_id="answer-context",
        retrieved_at=STAMP,
    )

    assert context.known_facts == []
    assert context.missing_facts == []
    assert context.citations[0].exact_quote == HIT["text"]
    assert HIT["jid"] in str(context.citations[0].source_id)
    assert "TPHM%2C110%2C" in context.citations[0].locator
    assert "chunk=chunk-3" in context.citations[0].locator
    assert context.evidence[0].verification.value == "PARTIAL"
    assert context.evidence[0].level.value == "NEED_CHECK"
    assert context.evidence[0].effective_at == datetime(2021, 8, 31, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_source_backed_research_runs_all_gates_and_reaches_provider() -> None:
    context = build_judgment_research_context(
        "毒品再犯期間如何判斷？",
        [HIT],
        execution_id="answer-context",
        retrieved_at=STAMP,
    )
    engine, provider = _engine()

    evaluated, meta, content = await engine.execute(context)

    assert meta.decision is DeliveryDecision.DELIVER
    assert provider.requests
    assert HIT["text"] in provider.requests[0].instructions
    assert context.citations[0].locator in provider.requests[0].instructions
    assert evaluated.gate_results[2].gate_id is GateId.G_FACTS
    assert evaluated.gate_results[2].passed is True
    assert "人工覆核" in content


@pytest.mark.asyncio
async def test_missing_or_unlocatable_results_ask_without_calling_provider() -> None:
    context = build_judgment_research_context(
        "沒有來源的問題",
        [{**HIT, "source_url": ""}],
        execution_id="missing-source",
        retrieved_at=STAMP,
    )
    engine, provider = _engine()

    evaluated, meta, _content = await engine.execute(context)

    assert evaluated.citations == []
    assert meta.decision is DeliveryDecision.ASK
    assert provider.requests == []
    assert context.missing_facts == ["未找到同時具備原文、裁判日期與來源定位的判決切片"]


@pytest.mark.asyncio
async def test_model_failure_stops_delivery_but_retains_retrieved_citation() -> None:
    context = build_judgment_research_context(
        "毒品再犯期間如何判斷？",
        [HIT],
        execution_id="model-failure",
        retrieved_at=STAMP,
    )
    provider = FailingProvider()

    evaluated, meta, _content = await _engine_with(provider).execute(context)

    assert meta.decision is DeliveryDecision.STOP
    assert meta.tool_failures and meta.tool_failures[0].startswith("provider:")
    assert evaluated.citations[0].exact_quote == HIT["text"]


@pytest.mark.asyncio
async def test_high_risk_research_requires_human_review_and_keeps_citation() -> None:
    context = build_judgment_research_context(
        "羈押案件如何判斷？",
        [HIT],
        execution_id="human-review",
        retrieved_at=STAMP,
    ).model_copy(update={"risk_level": RiskLevel.HIGH})
    engine, provider = _engine()

    evaluated, meta, _content = await engine.execute(context)

    assert meta.decision is DeliveryDecision.HUMAN_REVIEW
    assert provider.requests == []
    assert evaluated.citations[0].locator == context.citations[0].locator


def test_builder_deduplicates_chunks_and_rejects_missing_date() -> None:
    context = build_judgment_research_context(
        "問題",
        [HIT, HIT, {**HIT, "id": "undated", "judgment_date": ""}],
        execution_id="dedupe",
        retrieved_at=STAMP,
    )
    assert len(context.citations) == 1
