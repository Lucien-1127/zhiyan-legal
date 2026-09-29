"""Judgment citations must survive the canonical answer/HTTP boundary."""
from __future__ import annotations

from datetime import datetime, timezone

from backend.main import ChatRequest, _chat_citations, _chat_payload, _chat_status_code
from zhiyan_legal.domain import (
    AnswerMeta,
    Citation,
    DecisionStrictness,
    DeliveryDecision,
    Evidence,
    EvidenceLevel,
    ExecutionContext,
    RiskLevel,
    SourceType,
    TaskMode,
    VerificationStatus,
)


STAMP = datetime(2026, 9, 25, tzinfo=timezone.utc)


def _meta(
    decision: DeliveryDecision = DeliveryDecision.DELIVER,
    *,
    tool_failures: list[str] | None = None,
) -> AnswerMeta:
    return AnswerMeta(
        execution_id="judgment-answer-test",
        decision=decision,
        strictness_level=decision.strictness,
        task_mode=TaskMode.RESEARCH,
        risk_level=RiskLevel.MEDIUM,
        tool_failures=list(tool_failures or []),
        human_review_required=decision is DeliveryDecision.HUMAN_REVIEW,
    )


def _context() -> ExecutionContext:
    evidence = Evidence(
        source_id="TPHM,110,毒抗,1212,20210831,1",
        source_type=SourceType.JUDGMENT,
        title="臺灣高等法院 110年度毒抗字第1212號",
        locator="https://data.judicial.gov.tw/jdg/api/JDoc#chunk-3",
        retrieved_at=STAMP,
        effective_at=datetime(2021, 8, 31, tzinfo=timezone.utc),
        supports_claims=["claim-1"],
        verification=VerificationStatus.VERIFIED,
        level=EvidenceLevel.VERIFIED,
    )
    citation = Citation(
        citation_id="citation-1",
        claim_id="claim-1",
        source_id=evidence.source_id,
        locator=evidence.locator,
        exact_quote="再犯期間為三年",
        evidence_level=EvidenceLevel.VERIFIED,
        verified_at=STAMP,
    )
    return ExecutionContext(
        execution_id="judgment-answer-test",
        user_goal="毒品案件再犯期間如何計算？",
        evidence=[evidence],
        citations=[citation],
    )


def test_chat_payload_returns_verifiable_judgment_citation() -> None:
    context = _context()
    payload = _chat_payload(
        ChatRequest(message="毒品判決中的再犯期間？", task="RESEARCH"),
        context,
        _meta(),
        "依判決原文，期間為三年。",
        "request-1",
    )

    assert payload["citations"] == [
        {
            "citation_id": "citation-1",
            "source_id": "TPHM,110,毒抗,1212,20210831,1",
            "source_type": "JUDGMENT",
            "title": "臺灣高等法院 110年度毒抗字第1212號",
            "locator": "https://data.judicial.gov.tw/jdg/api/JDoc#chunk-3",
            "exact_quote": "再犯期間為三年",
            "evidence_level": "VERIFIED",
            "verification": "VERIFIED",
            "effective_at": "2021-08-31T00:00:00+00:00",
            "verified_at": "2026-09-25T00:00:00+00:00",
        }
    ]


def test_chat_payload_without_sources_never_fabricates_citations() -> None:
    context = ExecutionContext(
        execution_id="no-source",
        user_goal="沒有檢索結果",
    )

    assert _chat_citations(context) == []
    payload = _chat_payload(
        ChatRequest(message="沒有來源時怎麼辦？", task="RESEARCH"),
        context,
        _meta(DeliveryDecision.ASK),
        "請補充可核對資料。",
        "request-2",
    )
    assert payload["citations"] == []
    assert payload["decision"] == "ASK"


def test_chat_payload_keeps_citations_when_human_review_is_required() -> None:
    payload = _chat_payload(
        ChatRequest(message="高風險案件判決", task="RESEARCH"),
        _context(),
        _meta(DeliveryDecision.HUMAN_REVIEW),
        "需由法律專業人員人工覆核。",
        "request-3",
    )

    assert payload["decision"] == "HUMAN_REVIEW"
    assert payload["answer_meta"]["human_review_required"] is True
    assert payload["citations"][0]["exact_quote"] == "再犯期間為三年"


def test_provider_failure_stops_delivery_but_keeps_audit_citations() -> None:
    meta = _meta(
        DeliveryDecision.STOP,
        tool_failures=["provider: model unavailable"],
    )
    payload = _chat_payload(
        ChatRequest(message="高風險案件判決", task="RESEARCH"),
        _context(),
        meta,
        "模型失敗，停止交付。",
        "request-4",
    )

    assert _chat_status_code(meta) == 502
    assert payload["decision"] == "STOP"
    assert payload["error"] == "provider: model unavailable"
    assert payload["citations"][0]["locator"].endswith("#chunk-3")
