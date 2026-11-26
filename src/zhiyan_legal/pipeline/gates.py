"""The nine deterministic, fail-closed quality gates.

No gate in this module performs retrieval, network access, environment
inspection, or model calls.  Inputs which cannot be established from the
execution context are treated as unverified rather than guessed.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, time, timezone
import re
from typing import Any, ClassVar, Iterable

from ..domain import (
    ClaimMateriality,
    ClaimStatus,
    DeliveryDecision,
    ExecutionContext,
    GateId,
    GateResult,
    Jurisdiction,
    ProcedureStage,
    RiskLevel,
    TaskMode,
    VerificationStatus,
)
from ..domain.support import PRIMARY_SOURCE_TYPES, assess_support, matches_citation
from ..domain.temporal import TemporalVerifier
from .base import BaseGate


def _result(
    gate_id: GateId,
    passed: bool,
    reason: str,
    failure_decision: DeliveryDecision,
) -> GateResult:
    return GateResult(
        gate_id=gate_id,
        passed=passed,
        reason=reason,
        target_decision=DeliveryDecision.DELIVER if passed else failure_decision,
        evaluated_at=datetime.now(timezone.utc),
    )


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(getattr(value, "value", value)).strip()


def _combined_text(context: ExecutionContext) -> str:
    return " ".join(
        [
            context.user_goal,
            *context.known_facts,
            *context.missing_facts,
        ]
    ).lower()


class SafetyGate(BaseGate):
    gate_id: ClassVar[GateId] = GateId.G_SAFETY

    # These terms are intentionally conservative.  They identify a request
    # for harmful or illegal instructions; the gate never tries to infer a
    # safe alternative from an external source.
    _HIGH_RISK_TERMS: ClassVar[tuple[str, ...]] = (
        "自殺",
        "自殘",
        "自傷",
        "殺人方法",
        "殺人教學",
        "暴力犯罪指導",
        "製造炸彈",
        "製作炸彈",
        "下毒方法",
        "毒品製作",
        "違法操作",
        "非法入侵",
        "駭客入侵",
        "how to commit suicide",
        "how to kill",
        "self-harm",
        "suicide method",
        "make a bomb",
        "commit a violent crime",
        "illegal instructions",
    )

    def evaluate(self, context: ExecutionContext) -> GateResult:
        goal = _combined_text(context)
        matched = next((term for term in self._HIGH_RISK_TERMS if term.casefold() in goal), None)
        if context.task_mode is TaskMode.SAFETY or matched:
            detail = "TaskMode.SAFETY" if context.task_mode is TaskMode.SAFETY else f"命中高危詞：{matched}"
            return _result(self.gate_id, False, f"安全防護觸發（{detail}）", DeliveryDecision.STOP)
        return _result(self.gate_id, True, "未發現立即人身或違法操作風險", DeliveryDecision.STOP)


class JurisdictionGate(BaseGate):
    gate_id: ClassVar[GateId] = GateId.G_JURISDICTION

    def evaluate(self, context: ExecutionContext) -> GateResult:
        if context.jurisdiction is Jurisdiction.TW:
            return _result(self.gate_id, True, "法域確認為臺灣", DeliveryDecision.ASK)
        return _result(
            self.gate_id,
            False,
            "法域未確認為臺灣，需先釐清適用法域",
            DeliveryDecision.ASK,
        )


class FactsGate(BaseGate):
    gate_id: ClassVar[GateId] = GateId.G_FACTS

    def evaluate(self, context: ExecutionContext) -> GateResult:
        missing = [item.strip() for item in context.missing_facts if item.strip()]
        facts = [item.strip() for item in context.known_facts if item.strip()]
        # The canonical context represents the five W/result elements as a
        # flat list.  A non-empty explicit missing list always wins; otherwise
        # five populated elements are the minimum available representation.
        if missing:
            return _result(
                self.gate_id,
                False,
                f"缺少重要事實要素：{', '.join(missing)}",
                DeliveryDecision.ASK,
            )
        # A source-backed RESEARCH request asks what the retrieved authorities
        # say; it is not yet an application of law to a user's five-W facts.
        # Requiring invented case facts here would corrupt the audit trail.
        if context.task_mode is TaskMode.RESEARCH and context.evidence and context.citations:
            return _result(
                self.gate_id,
                True,
                "研究檢索已有可核對來源；個案適用仍須另行補充事實",
                DeliveryDecision.ASK,
            )
        if len(facts) < 5:
            return _result(
                self.gate_id,
                False,
                "重要事實不足，至少需要行為人、時間、地點、行為及結果五要素",
                DeliveryDecision.ASK,
            )
        return _result(self.gate_id, True, "核心事實已具備五要素", DeliveryDecision.ASK)


class SourceGate(BaseGate):
    gate_id: ClassVar[GateId] = GateId.G_SOURCE

    def evaluate(self, context: ExecutionContext) -> GateResult:
        core_claims = [
            claim for claim in context.claims if claim.materiality is ClaimMateriality.CORE
        ]
        unsupported: list[str] = []
        for claim in core_claims:
            has_primary = any(
                evidence.source_type in PRIMARY_SOURCE_TYPES
                and bool(evidence.locator.strip())
                and claim.claim_id in evidence.supports_claims
                for evidence in context.evidence
            )
            if not has_primary:
                unsupported.append(_text(claim.claim_id))

        if unsupported:
            return _result(
                self.gate_id,
                False,
                f"核心命題缺乏一手來源定位：{', '.join(unsupported)}",
                DeliveryDecision.STOP,
            )
        return _result(self.gate_id, True, "所有核心命題均有一手來源定位", DeliveryDecision.STOP)


def applicable_dates(context: ExecutionContext) -> list[datetime]:
    if context.applicable_at is not None:
        return [context.applicable_at]
    dates = _dates_in(context.known_facts)
    return [datetime.combine(day, time.min) for day in sorted(set(dates))] or [datetime.now(timezone.utc)]


def claim_support_statuses(context: ExecutionContext) -> dict[str, VerificationStatus]:
    claims = {claim.claim_id: claim for claim in context.claims}
    sources = {item.source_id: item for item in context.evidence}
    citation_ids = Counter(item.citation_id for item in context.citations)
    statuses = {claim_id: VerificationStatus.UNVERIFIED for claim_id in claims}
    if len(claims) != len(context.claims) or len(sources) != len(context.evidence):
        return statuses
    dates = applicable_dates(context)
    for citation in context.citations:
        claim = claims.get(citation.claim_id)
        source = sources.get(citation.source_id)
        if claim is None or source is None or citation_ids[citation.citation_id] != 1:
            continue
        checks = [assess_support(claim, citation, source, context.jurisdiction, day) for day in dates]
        if VerificationStatus.CONFLICT in checks:
            statuses[claim.claim_id] = VerificationStatus.CONFLICT
        elif statuses[claim.claim_id] is not VerificationStatus.CONFLICT:
            if all(status is VerificationStatus.VERIFIED for status in checks):
                statuses[claim.claim_id] = VerificationStatus.VERIFIED
            elif VerificationStatus.STALE in checks and statuses[claim.claim_id] is not VerificationStatus.VERIFIED:
                statuses[claim.claim_id] = VerificationStatus.STALE
    return statuses


class SupportGate(BaseGate):
    gate_id: ClassVar[GateId] = GateId.G_SUPPORT

    def evaluate(self, context: ExecutionContext) -> GateResult:
        claims = {claim.claim_id: claim for claim in context.claims}
        sources = {item.source_id: item for item in context.evidence}
        if (
            len(claims) != len(context.claims)
            or len(sources) != len(context.evidence)
            or len({item.citation_id for item in context.citations}) != len(context.citations)
        ):
            return _result(self.gate_id, False, "命題、來源或引註的識別碼重複", DeliveryDecision.STOP)
        for citation in context.citations:
            claim = claims.get(citation.claim_id)
            source = sources.get(citation.source_id)
            if claim is None or source is None or source.withdrawn or not matches_citation(claim, citation, source):
                return _result(self.gate_id, False, "引註與命題、來源定位或原文不一致", DeliveryDecision.STOP)

        statuses = claim_support_statuses(context)
        core = [claim for claim in context.claims if claim.materiality is ClaimMateriality.CORE]
        missing = [claim.claim_id for claim in core if statuses[claim.claim_id] is VerificationStatus.UNVERIFIED]
        if missing:
            return _result(self.gate_id, False, f"核心命題缺少已驗證引註：{', '.join(missing)}", DeliveryDecision.STOP)
        if any(status in {VerificationStatus.CONFLICT, VerificationStatus.STALE} for status in statuses.values()):
            return _result(self.gate_id, False, "引用的法源有衝突或不適用於案件時點", DeliveryDecision.HUMAN_REVIEW)
        if not core and context.task_mode is TaskMode.RESEARCH and not context.citations:
            return _result(self.gate_id, False, "研究查無具備原文與來源定位的資料", DeliveryDecision.STOP)
        return _result(self.gate_id, True, "已核對引註與對應原文", DeliveryDecision.STOP)


def _dates_in(values: Iterable[str]) -> list[date]:
    found: list[date] = []
    for value in values:
        for match in re.findall(r"(?<!\d)(\d{4})[-/]([01]?\d)[-/]([0-3]?\d)(?!\d)", value):
            try:
                found.append(date(int(match[0]), int(match[1]), int(match[2])))
            except ValueError:
                continue
    return found


class TemporalGate(BaseGate):
    gate_id: ClassVar[GateId] = GateId.G_TEMPORAL

    def evaluate(self, context: ExecutionContext) -> GateResult:
        if any(claim.status is ClaimStatus.STALE for claim in context.claims):
            return _result(self.gate_id, False, "命題標記為過期，適用時點需人工確認", DeliveryDecision.HUMAN_REVIEW)

        verifier = TemporalVerifier()
        dates = applicable_dates(context)
        for evidence in context.evidence:
            if evidence.withdrawn:
                return _result(self.gate_id, False, "判決來源已撤下", DeliveryDecision.STOP)
            if evidence.source_type not in PRIMARY_SOURCE_TYPES:
                continue
            if any(verifier.verify(evidence, day) is not VerificationStatus.VERIFIED for day in dates):
                return _result(self.gate_id, False, "法源缺少適用時點、已過期或存在衝突", DeliveryDecision.HUMAN_REVIEW)

        return _result(self.gate_id, True, "未發現適用時點衝突或過期來源", DeliveryDecision.HUMAN_REVIEW)


class ConflictGate(BaseGate):
    gate_id: ClassVar[GateId] = GateId.G_CONFLICT
    _CONFLICT_TERMS: ClassVar[tuple[str, ...]] = (
        "衝突",
        "矛盾",
        "分歧",
        "不一致",
        "conflict",
        "contradict",
        "dissent",
    )

    def evaluate(self, context: ExecutionContext) -> GateResult:
        if any(claim.status is ClaimStatus.CONFLICT for claim in context.claims):
            return _result(self.gate_id, False, "命題標記為來源衝突", DeliveryDecision.HUMAN_REVIEW)
        if any(evidence.verification is VerificationStatus.CONFLICT for evidence in context.evidence):
            return _result(self.gate_id, False, "Evidence 標記為來源衝突", DeliveryDecision.HUMAN_REVIEW)
        dynamic_conflicts = getattr(context, "conflicts", None)
        if dynamic_conflicts:
            return _result(self.gate_id, False, "存在未揭露的來源衝突", DeliveryDecision.HUMAN_REVIEW)
        if any(term in _combined_text(context) for term in self._CONFLICT_TERMS):
            return _result(self.gate_id, False, "文字內容指出權威見解或來源可能矛盾", DeliveryDecision.HUMAN_REVIEW)
        return _result(self.gate_id, True, "未發現未揭露的權威來源衝突", DeliveryDecision.HUMAN_REVIEW)


class HighImpactGate(BaseGate):
    gate_id: ClassVar[GateId] = GateId.G_HIGH_IMPACT
    _HIGH_IMPACT_TERMS: ClassVar[tuple[str, ...]] = (
        "重大刑案",
        "七年以上",
        "七年有期徒刑",
        "死刑",
        "人身自由",
        "羈押",
        "拘留",
        "逮捕",
        "強制執行",
        "查封",
        "拍賣",
        "高額財產",
        "不可逆",
        "seven years",
        "death penalty",
        "deprivation of liberty",
        "forced execution",
    )

    def evaluate(self, context: ExecutionContext) -> GateResult:
        if context.risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL}:
            return _result(self.gate_id, False, "風險等級為高／重大，需人工覆核", DeliveryDecision.HUMAN_REVIEW)
        if context.procedure_stage is ProcedureStage.ENFORCEMENT:
            return _result(self.gate_id, False, "案件涉及強制執行程序，需人工覆核", DeliveryDecision.HUMAN_REVIEW)
        matched = next((term for term in self._HIGH_IMPACT_TERMS if term.casefold() in _combined_text(context)), None)
        if matched:
            return _result(self.gate_id, False, f"命中高影響案件指標：{matched}", DeliveryDecision.HUMAN_REVIEW)
        return _result(self.gate_id, True, "未發現重大刑案、人身自由或重大財產處分指標", DeliveryDecision.HUMAN_REVIEW)


def _payload_value(payload: Any, keys: tuple[str, ...]) -> Any:
    if isinstance(payload, dict):
        for key in keys:
            if key in payload:
                return payload[key]
    for key in keys:
        if hasattr(payload, key):
            return getattr(payload, key)
    return None


class OutputGate(BaseGate):
    gate_id: ClassVar[GateId] = GateId.G_OUTPUT
    _REQUIRED_FIELDS: ClassVar[dict[str, tuple[str, ...]]] = {
        "資訊狀態": ("information_status", "status", "資訊狀態", "verification_status"),
        "法條依據": ("legal_basis", "legal_basis_references", "法條依據", "citations"),
        "限制揭露": ("limitations", "limitation", "限制揭露", "disclaimer"),
        "禁止聲明": ("prohibited_statement", "prohibited_claims", "禁止聲明", "safety_disclaimer"),
    }
    _CERTAINTY_TERMS: ClassVar[tuple[str, ...]] = (
        "保證",
        "一定會",
        "必然",
        "guaranteed",
        "definitely",
        "will win",
    )

    def evaluate(self, context: ExecutionContext) -> GateResult:
        # ExecutionContext intentionally has no transport/output field.  An
        # adapter may attach one with model_copy(update={"output": ...}); in
        # its absence this gate is not applicable yet.
        payload = next(
            (getattr(context, name, None) for name in ("output", "response", "draft_output") if hasattr(context, name)),
            None,
        )
        if payload is None:
            return _result(self.gate_id, True, "尚未提供對外草稿，輸出結構待交付層驗證", DeliveryDecision.SAFE)

        rendered = _text(payload)
        certainty_found = any(
            term.casefold() in rendered.casefold()
            and f"不{term}".casefold() not in rendered.casefold()
            for term in self._CERTAINTY_TERMS
        )
        if certainty_found:
            return _result(self.gate_id, False, "對外草稿包含未驗證的確定性保證", DeliveryDecision.SAFE)

        missing = [
            label
            for label, keys in self._REQUIRED_FIELDS.items()
            if not _text(_payload_value(payload, keys))
        ]
        if missing:
            return _result(self.gate_id, False, f"輸出結構缺少：{', '.join(missing)}", DeliveryDecision.SAFE)
        return _result(self.gate_id, True, "輸出包含資訊狀態、法條依據、限制揭露與禁止聲明", DeliveryDecision.SAFE)


# Explicit aliases make the gate names convenient both in Python style and
# when tests/documentation use the literal G* naming convention.
GSafetyGate = SafetyGate
GJurisdictionGate = JurisdictionGate
GFactsGate = FactsGate
GSourceGate = SourceGate
GSupportGate = SupportGate
GTemporalGate = TemporalGate
GConflictGate = ConflictGate
GHighImpactGate = HighImpactGate
GOutputGate = OutputGate
G_SAFETY = SafetyGate
G_JURISDICTION = JurisdictionGate
G_FACTS = FactsGate
G_SOURCE = SourceGate
G_SUPPORT = SupportGate
G_TEMPORAL = TemporalGate
G_CONFLICT = ConflictGate
G_HIGH_IMPACT = HighImpactGate
G_OUTPUT = OutputGate


__all__ = [
    "SafetyGate", "JurisdictionGate", "FactsGate", "SourceGate", "SupportGate",
    "TemporalGate", "ConflictGate", "HighImpactGate", "OutputGate",
    "GSafetyGate", "GJurisdictionGate", "GFactsGate", "GSourceGate",
    "GSupportGate", "GTemporalGate", "GConflictGate", "GHighImpactGate",
    "GOutputGate",
    "G_SAFETY", "G_JURISDICTION", "G_FACTS", "G_SOURCE", "G_SUPPORT",
    "G_TEMPORAL", "G_CONFLICT", "G_HIGH_IMPACT", "G_OUTPUT",
]
