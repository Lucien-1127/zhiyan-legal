"""Exercise the HTTP boundary, including FastAPI response serialization."""

from datetime import datetime, timezone

import httpx
import pytest

from backend import main as backend_main
from zhiyan_legal.domain import (
    AnswerMeta,
    Citation,
    DeliveryDecision,
    Evidence,
    EvidenceLevel,
    ExecutionContext,
    RiskLevel,
    SourceType,
    TaskMode,
    VerificationStatus,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "decision,status,failures",
    [
        (DeliveryDecision.DELIVER, 200, []),
        (DeliveryDecision.ASK, 400, []),
        (DeliveryDecision.SAFE, 403, []),
        (DeliveryDecision.HUMAN_REVIEW, 403, []),
        (DeliveryDecision.STOP, 422, []),
        (DeliveryDecision.STOP, 502, ["provider: unavailable"]),
    ],
)
@pytest.mark.parametrize("with_citations", [False, True])
async def test_chat_http_preserves_decision_content_and_canonical_citations(
    monkeypatch, decision, status, failures, with_citations
):
    citations = [
        Citation(
            citation_id=f"citation-{index}",
            claim_id="claim-1",
            source_id=f"source-{index}",
            locator=f"測試來源第 {index} 段",
            exact_quote=f"測試原文 {index}：<文字> & 引用。",
            evidence_level=EvidenceLevel.VERIFIED,
            verified_at=datetime(2026, 10, 6, tzinfo=timezone.utc),
        )
        for index in (1, 2)
    ] if with_citations else []
    evidence = [
        Evidence(
            source_id=f"source-{index}",
            source_type=SourceType.JUDGMENT,
            title=f"測試判決 {index}",
            locator=f"測試來源第 {index} 段",
            retrieved_at=datetime(2026, 10, 6, tzinfo=timezone.utc),
            supports_claims=["claim-1"],
            verification=VerificationStatus.VERIFIED,
            level=EvidenceLevel.VERIFIED,
        )
        for index in (1, 2)
    ] if with_citations else []
    context = ExecutionContext(
        execution_id="chat-contract",
        user_goal="法律問題",
        evidence=evidence,
        citations=citations,
    )
    meta = AnswerMeta(
        execution_id=context.execution_id,
        decision=decision,
        strictness_level=decision.strictness,
        task_mode=TaskMode.QC,
        risk_level=RiskLevel.MEDIUM,
        tool_failures=failures,
    )
    content = "請保留完整回應\n以及下一步說明。"

    class StubEngine:
        async def query_async(self, message, **kwargs):
            assert message == context.user_goal
            return context, meta, content

    monkeypatch.setattr(backend_main, "get_engine", lambda: StubEngine())
    monkeypatch.setattr(backend_main.limiter, "enabled", False)
    transport = httpx.ASGITransport(app=backend_main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/chat",
            json={"message": context.user_goal},
            headers={"X-Request-ID": "contract-request"},
        )

    assert response.status_code == status
    payload = response.json()
    assert payload["content"] == content
    assert payload["decision"] == decision.value
    assert payload["answer_meta"] == meta.model_dump(mode="json")
    assert payload["request_id"] == response.headers["X-Request-ID"] == "contract-request"
    expected_citations = [
        {
            "citation_id": f"citation-{index}",
            "source_id": f"source-{index}",
            "source_type": "JUDGMENT",
            "title": f"測試判決 {index}",
            "locator": f"測試來源第 {index} 段",
            "exact_quote": f"測試原文 {index}：<文字> & 引用。",
            "evidence_level": "VERIFIED",
            "verification": "VERIFIED",
            "effective_at": None,
            "verified_at": "2026-10-06T00:00:00+00:00",
        }
        for index in (1, 2)
    ] if with_citations else []
    assert payload["citations"] == expected_citations
    assert payload["error"] == ("; ".join(failures) or None)
