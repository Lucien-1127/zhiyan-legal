"""Contract tests for the Z1-03 duplicate-domain migration adapters."""

from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
from pathlib import Path

import pytest
from pydantic import ValidationError

from committee.core import ClaimStatus as LegacyClaimStatus
from committee.core import ClaimType, LegalClaim
from committee.prompt_optimization.quality_gate import GateResult, PromptGateResult
from src.zhiyan_legal.domain import (
    AnswerMeta,
    DecisionStrictness,
    DeliveryDecision,
    ExecutionContext,
    RiskLevel,
    SourceType,
    TaskMode,
)
from src.zhiyan_legal.schemas.judgment import (
    CaseType,
    ChunkType,
    CourtLevel,
    JudgmentChunk,
    JudgmentDocument,
    JudgmentLinks,
    JudgmentMeta,
)
from src.zhiyan_legal.sdk.models import QueryResponse, query_response_from_domain


def _judgment() -> JudgmentDocument:
    meta = JudgmentMeta(
        court="最高法院",
        court_level=CourtLevel.SUPREME,
        case_no="108年度台上字第1234號",
        case_type=CaseType.CIVIL,
        cause="損害賠償",
        judgment_date="2019-05-15",
        year=2019,
    )
    chunk = JudgmentChunk(
        chunk_id=f"{meta.doc_id}_facts_00",
        doc_id=meta.doc_id,
        chunk_type=ChunkType.FACTS,
        chunk_index=0,
        chunk_text="這是一段足夠長度的裁判事實文字。",
        source_field="facts",
    )
    return JudgmentDocument(meta=meta, links=JudgmentLinks(), chunks=[chunk])


def test_legacy_judgment_path_reexports_canonical_classes() -> None:
    legacy_path = Path(__file__).parents[2] / "zhiyan_legal/schemas/judgment.py"
    spec = importlib.util.spec_from_file_location("legacy_judgment", legacy_path)
    assert spec and spec.loader
    legacy_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(legacy_module)

    assert legacy_module.JudgmentDocument is JudgmentDocument
    assert legacy_module.JudgmentMeta is JudgmentMeta


def test_judgment_validators_and_evidence_adapter() -> None:
    document = _judgment()

    assert len(document.meta.doc_id) == 16
    assert document.chunks[0].char_count == len(document.chunks[0].chunk_text)
    evidence = document.to_canonical_evidence()

    assert evidence.source_id == document.meta.doc_id
    assert evidence.source_type is SourceType.JUDGMENT
    assert evidence.effective_at == datetime(2019, 5, 15, tzinfo=timezone.utc)

    with pytest.raises(ValidationError, match="ISO-8601"):
        JudgmentMeta(
            court="最高法院",
            court_level=CourtLevel.SUPREME,
            case_no="108年度台上字第1234號",
            case_type=CaseType.CIVIL,
            cause="損害賠償",
            judgment_date="2019/05/15",
            year=2019,
        )


def test_legal_claim_adapters_preserve_core_semantics() -> None:
    legacy = LegalClaim(
        claim_id="claim-1",
        article_ref="民法第184條",
        claim_type=ClaimType.STATUTE_EXISTENCE,
        status=LegacyClaimStatus.EXISTS,
        summary="民法第184條適用於本案",
    )

    canonical = legacy.to_canonical_claim()
    restored = LegalClaim.from_canonical_claim(canonical)

    assert canonical.claim_id == "claim-1"
    assert canonical.status.value == "VERIFIED"
    assert restored.claim_id == legacy.claim_id
    assert restored.article_ref == legacy.summary
    assert restored.status is LegacyClaimStatus.EXISTS


def test_prompt_gate_alias_keeps_legacy_name() -> None:
    assert PromptGateResult is GateResult
    result = PromptGateResult("G1", True, "ok")
    assert isinstance(result, GateResult)
    assert bool(result)


def test_sdk_response_adapter_maps_canonical_execution() -> None:
    context = ExecutionContext(execution_id="exec-1", user_goal="檢視契約")
    answer = AnswerMeta(
        execution_id="exec-1",
        decision=DeliveryDecision.HUMAN_REVIEW,
        strictness_level=DecisionStrictness.HUMAN_REVIEW,
        task_mode=TaskMode.CONTRACT_REVIEW,
        risk_level=RiskLevel.HIGH,
        conflicts=["資料來源衝突"],
        tool_failures=["retriever timeout"],
        human_review_required=True,
    )

    response = QueryResponse.from_execution_context(
        context,
        answer,
        content="請交由人工覆核。",
        model="test-model",
    )
    functional = query_response_from_domain(context, answer)

    assert response.content == "請交由人工覆核。"
    assert response.task == "QC"
    assert response.model == "test-model"
    assert "資料來源衝突" in response.warnings
    assert "retriever timeout" in response.warnings
    assert "human review required" in response.warnings
    assert functional.task == "QC"
