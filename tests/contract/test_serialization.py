import json
from datetime import datetime, timezone

from zhiyan_legal.domain import (
    Claim,
    ClaimKind,
    Citation,
    Evidence,
    EvidenceLevel,
    ExecutionContext,
    GateId,
    GateResult,
    SourceType,
    VerificationStatus,
)


STAMP = datetime(2026, 8, 25, 20, 30, 0, tzinfo=timezone.utc)


def make_context() -> ExecutionContext:
    claim = Claim(claim_id="c-1", text="可驗證事實", kind=ClaimKind.FACT)
    evidence = Evidence(
        source_id="s-1",
        source_type=SourceType.OFFICIAL,
        title="官方資料",
        locator="https://example.test/source/1",
        retrieved_at=STAMP,
        effective_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        supports_claims=[claim.claim_id],
        verification=VerificationStatus.VERIFIED,
        level=EvidenceLevel.VERIFIED,
    )
    citation = Citation(
        citation_id="cite-1",
        claim_id=claim.claim_id,
        source_id=evidence.source_id,
        locator="https://example.test/source/1#p1",
        exact_quote="可驗證事實",
        evidence_level=EvidenceLevel.VERIFIED,
        verified_at=STAMP,
    )
    gate_result = GateResult(
        gate_id=GateId.G_SOURCE,
        passed=True,
        reason="source present",
        target_decision="DELIVER",
        evaluated_at=STAMP,
    )
    return ExecutionContext(
        execution_id="exec-1",
        user_goal="serialise",
        claims=[claim],
        evidence=[evidence],
        citations=[citation],
        gate_results=[gate_result],
    )


def test_model_dump_and_json_round_trip_preserve_types() -> None:
    context = make_context()
    dumped = context.model_dump()
    assert isinstance(dumped["status"].value, str)
    assert isinstance(dumped["evidence"][0]["retrieved_at"], datetime)

    json_payload = json.dumps(context.model_dump(mode="json"))
    restored = ExecutionContext.model_validate_json(json_payload)
    assert restored == context
    assert restored.status.value == "INTAKE"
    assert restored.evidence[0].source_type is SourceType.OFFICIAL
    assert restored.gate_results[0].target_decision.value == "DELIVER"
    assert restored.evidence[0].retrieved_at.tzinfo is not None


def test_model_dump_json_uses_iso8601_and_round_trips_timezone() -> None:
    context = make_context()
    payload = context.model_dump_json()
    assert "2026-08-25T20:30:00Z" in payload

    restored = ExecutionContext.model_validate_json(payload)
    assert restored.evidence[0].retrieved_at == STAMP
    assert restored.citations[0].verified_at == STAMP
