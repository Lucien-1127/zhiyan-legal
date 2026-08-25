"""核心資料結構 — LegalClaim, ModelVerdict, CommitteeReport"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from zhiyan_legal.domain import Claim


# ── 列舉 ──

class ClaimType(str, Enum):
    """主張類型：法條存在性、判決存在性、事實陳述、法律解釋"""
    STATUTE_EXISTENCE = "statute_existence"
    PRECEDENT_EXISTENCE = "precedent_existence"
    FACT_STATEMENT = "fact_statement"
    LEGAL_INTERPRETATION = "legal_interpretation"


class ClaimStatus(str, Enum):
    """正規化後的條文狀態"""
    EXISTS = "exists"               # 條文存在且有效
    DELETED = "deleted"             # 已刪除/已廢止
    NONEXISTENT = "nonexistent"     # 不存在/查無
    AMENDED = "amended"             # 已修訂
    UNKNOWN = "unknown"             # 無法判斷（模型正常回應但無結論）
    ERROR = "error"                 # API 失敗（429/空回應/異常）
    SAFETY_UNKNOWN = "safety_unknown"  # 模型因安全機制拒絕回答


class Verdict(str, Enum):
    """單一模型的判定結果"""
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"


class ConsensusLabel(str, Enum):
    """合議庭標示"""
    CONSENSUS = "consensus"             # ✅ 共識 — 所有模型一致
    DISAGREEMENT = "disagreement"       # ⚠️ 分歧 — 模型間意見不同
    BLIND_SPOT = "blind_spot"           # ❌ 盲區 — 所有模型都錯
    UNIQUE_INSIGHT = "unique_insight"   # 🔍 獨特發現 — 僅單一模型提出


# ── 資料類別 ──

@dataclass
class LegalClaim:
    """標準化的法律主張，所有模型輸出都會正規化成此格式。"""
    # 核心辨識
    claim_id: str                           # 唯一識別碼 (auto-generated)
    article_ref: str                        # 正規化條號 (ex: "民法第987條", "釋字第812號")
    claim_type: ClaimType                   # 主張類型

    # 模型判定
    status: Optional[ClaimStatus] = None    # 條文狀態判定
    summary: str = ""                       # 簡短摘要 (30字內)
    confidence: float = 0.0                 # 0.0~1.0 (from model self-report or heuristic)

    # 來源
    model_name: str = ""                    # 來自哪個模型
    raw_snippet: str = ""                   # 原始引用文字 (供審計)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_canonical_claim(self) -> "Claim":
        """Adapt this committee claim to the canonical domain Claim.

        The committee schema has a richer, legacy status vocabulary.  The
        adapter deliberately maps it to the canonical four-state vocabulary;
        the original object remains available to callers that need the legacy
        audit fields such as ``raw_snippet``.
        """
        from zhiyan_legal.domain import (
            Claim,
            ClaimKind,
            ClaimMateriality,
            ClaimStatus as CanonicalClaimStatus,
        )

        kind_by_type = {
            ClaimType.STATUTE_EXISTENCE: ClaimKind.LAW,
            ClaimType.PRECEDENT_EXISTENCE: ClaimKind.LAW,
            ClaimType.FACT_STATEMENT: ClaimKind.FACT,
            ClaimType.LEGAL_INTERPRETATION: ClaimKind.INFERENCE,
        }
        status_by_legacy = {
            ClaimStatus.EXISTS: CanonicalClaimStatus.VERIFIED,
            ClaimStatus.DELETED: CanonicalClaimStatus.CONFLICT,
            ClaimStatus.NONEXISTENT: CanonicalClaimStatus.CONFLICT,
            ClaimStatus.AMENDED: CanonicalClaimStatus.STALE,
            ClaimStatus.UNKNOWN: CanonicalClaimStatus.UNVERIFIED,
            ClaimStatus.ERROR: CanonicalClaimStatus.UNVERIFIED,
            ClaimStatus.SAFETY_UNKNOWN: CanonicalClaimStatus.UNVERIFIED,
        }
        return Claim(
            claim_id=self.claim_id,
            text=self.summary or self.raw_snippet or self.article_ref,
            kind=kind_by_type[self.claim_type],
            materiality=ClaimMateriality.SUPPORTING,
            status=status_by_legacy[self.status or ClaimStatus.UNKNOWN],
        )

    @classmethod
    def from_canonical_claim(cls, claim: "Claim") -> "LegalClaim":
        """Build a legacy ``LegalClaim`` from a canonical domain Claim."""
        from zhiyan_legal.domain import ClaimKind, ClaimStatus as CanonicalClaimStatus

        type_by_kind = {
            ClaimKind.FACT: ClaimType.FACT_STATEMENT,
            ClaimKind.LAW: ClaimType.STATUTE_EXISTENCE,
            ClaimKind.INFERENCE: ClaimType.LEGAL_INTERPRETATION,
            ClaimKind.PROCEDURE: ClaimType.FACT_STATEMENT,
            ClaimKind.RISK: ClaimType.LEGAL_INTERPRETATION,
        }
        status_by_canonical = {
            CanonicalClaimStatus.UNVERIFIED: ClaimStatus.UNKNOWN,
            CanonicalClaimStatus.VERIFIED: ClaimStatus.EXISTS,
            CanonicalClaimStatus.CONFLICT: ClaimStatus.NONEXISTENT,
            CanonicalClaimStatus.STALE: ClaimStatus.AMENDED,
        }
        return cls(
            claim_id=str(claim.claim_id),
            article_ref=claim.text,
            claim_type=type_by_kind[claim.kind],
            status=status_by_canonical[claim.status],
            summary=claim.text,
        )


@dataclass
class ModelVerdict:
    """單一模型對單一查詢的判定結果。"""
    model_name: str
    query_id: str
    query_text: str
    category: str
    verdict: Verdict
    hallucination_score: float = 0.0        # 0=clean, 1=hallucinated
    claims: List[LegalClaim] = field(default_factory=list)
    raw_response: str = ""
    elapsed_s: float = 0.0
    error: Optional[str] = None


@dataclass
class ClaimCluster:
    """跨模型的同一主張群組。"""
    canonical_ref: str                      # 正規化條號
    claim_type: ClaimType
    models: List[str] = field(default_factory=list)     # 哪些模型提到此主張
    statuses: List[Optional[ClaimStatus]] = field(default_factory=list)
    label: ConsensusLabel = ConsensusLabel.CONSENSUS
    detail: str = ""


@dataclass
class Disagreement:
    """具體的分歧記錄。"""
    cluster_id: str
    canonical_ref: str
    description: str                        # 人類可讀的描述
    model_a: str
    position_a: str
    model_b: str
    position_b: str


@dataclass
class CommitteeReport:
    """合議庭對單一查詢的完整報告。"""
    query_id: str
    query_text: str
    category: str

    # 模型表現
    model_verdicts: List[ModelVerdict] = field(default_factory=list)

    # 合議庭分析
    clusters: List[ClaimCluster] = field(default_factory=list)
    disagreements: List[Disagreement] = field(default_factory=list)

    # 統計
    total_models: int = 0
    consensus_count: int = 0
    disagreement_count: int = 0
    blind_spot_count: int = 0
    unique_insight_count: int = 0

    def to_vnext(self, task_id: Optional[str] = None):
        """Adapt this legacy report to the canonical vNext report."""
        from datetime import datetime, timezone
        from zhiyan_legal.committee.evaluator import ConsensusEvaluator
        from zhiyan_legal.committee.models import CommitteeMemberVerdict
        from zhiyan_legal.providers import ProviderRole

        members = [
            CommitteeMemberVerdict(
                provider_name=verdict.model_name,
                model=verdict.model_name,
                role=ProviderRole.DRAFTER,
                claims=[claim.to_canonical_claim() for claim in verdict.claims],
                verdict=verdict.verdict.value,
                confidence=max(
                    (claim.confidence for claim in verdict.claims), default=1.0
                ),
                error=verdict.error,
            )
            for verdict in self.model_verdicts
        ]
        return ConsensusEvaluator().evaluate(
            task_id or self.query_id,
            members,
            evaluated_at=datetime.now(timezone.utc),
        )

    as_vnext = to_vnext

    def to_dict(self) -> dict:
        return {
            "query_id": self.query_id,
            "query_text": self.query_text[:80],
            "category": self.category,
            "total_models": self.total_models,
            "consensus": self.consensus_count,
            "disagreement": self.disagreement_count,
            "blind_spot": self.blind_spot_count,
            "unique_insight": self.unique_insight_count,
            "clusters": [asdict(c) for c in self.clusters],
            "disagreements": [asdict(d) for d in self.disagreements],
        }


@dataclass
class CommitteeSummary:
    """批次查詢的整體摘要。"""
    reports: List[CommitteeReport] = field(default_factory=list)

    @property
    def total_queries(self) -> int:
        return len(self.reports)

    @property
    def total_disagreements(self) -> int:
        return sum(r.disagreement_count for r in self.reports)

    @property
    def total_blind_spots(self) -> int:
        return sum(r.blind_spot_count for r in self.reports)

    def to_json(self, path: str) -> None:
        data = {
            "total_queries": self.total_queries,
            "total_disagreements": self.total_disagreements,
            "total_blind_spots": self.total_blind_spots,
            "reports": [r.to_dict() for r in self.reports],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
