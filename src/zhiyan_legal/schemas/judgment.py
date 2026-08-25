# src/zhiyan_legal/schemas/judgment.py
# Schema v1.0 — 鎖版 2026-06-29
"""Canonical structured schema for Taiwanese court judgments."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import hashlib
import re

from pydantic import BaseModel, Field, field_validator, model_validator

from ..domain import Evidence, EvidenceLevel, SourceType, VerificationStatus


_ISO_DATE_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?$"
)


class CourtLevel(str, Enum):
    SUPREME = "supreme"
    HIGH = "high"
    DISTRICT = "district"


class CaseType(str, Enum):
    CIVIL = "民事"
    CRIMINAL = "刑事"
    ADMINISTRATIVE = "行政"
    FAMILY = "家事"
    JUVENILE = "少年"


class Holding(str, Enum):
    PLAINTIFF_WIN = "原告勝"
    DEFENDANT_WIN = "被告勝"
    PARTIAL_WIN = "部分勝訴"
    REMAND = "發回更審"
    DISMISSED = "駁回上訴"
    SETTLED = "調解成立"
    UNKNOWN = "不明"


class ChunkType(str, Enum):
    FACTS = "facts"
    REASONING = "reasoning"
    HOLDING_TEXT = "holding_text"
    ISSUES = "issues"


class JudgmentMeta(BaseModel):
    """Identification metadata, used for filtering and de-duplication."""

    court: str = Field(description="法院全名，如『最高法院民事庭』")
    court_level: CourtLevel
    case_no: str = Field(description="如『108年度台上字第1234號』")
    case_type: CaseType
    cause: str = Field(description="原始案由字串，保留 fidelity")
    cause_normalized: str | None = Field(default=None)
    judgment_date: str = Field(description="ISO 8601，如『2019-05-15』")
    year: int
    doc_id: str = Field(
        default="",
        description="court + case_no + judgment_date 的 SHA256 前16碼",
        exclude=True,
        validate_default=True,
    )

    @field_validator("judgment_date")
    @classmethod
    def validate_judgment_date(cls, value: str) -> str:
        """Keep the legacy ISO-8601 shape check in the canonical schema."""
        if not _ISO_DATE_RE.fullmatch(value):
            raise ValueError("judgment_date must be an ISO-8601 date or datetime")
        return value

    @field_validator("doc_id", mode="before")
    @classmethod
    def compute_doc_id(cls, value: str | None, info) -> str:
        if value:
            return value
        data = info.data
        raw = f"{data.get('court', '')}{data.get('case_no', '')}{data.get('judgment_date', '')}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


class JudgmentLinks(BaseModel):
    """Links to statutes, interpretations, and cited judgments."""

    cited_statutes: list[str] = Field(default_factory=list)
    cited_interpretations: list[str] = Field(default_factory=list)
    cited_cases: list[str] = Field(default_factory=list)
    holding: Holding = Field(default=Holding.UNKNOWN)


class JudgmentChunk(BaseModel):
    """One independently embeddable chunk of a judgment."""

    chunk_id: str = Field(description="格式：{doc_id}_{chunk_type.value}_{chunk_index:02d}")
    doc_id: str = Field(description="關聯回 JudgmentMeta.doc_id")
    chunk_type: ChunkType
    chunk_index: int = Field(ge=0)
    chunk_text: str = Field(min_length=10)
    source_field: str = Field(description="來源 JSON 欄位名，如 facts / reason / mainText")
    char_count: int = Field(
        default=0,
        ge=0,
        description="字符數，用於 chunk 大小監控",
        validate_default=True,
    )

    @field_validator("char_count", mode="before")
    @classmethod
    def auto_char_count(cls, value: int | None, info) -> int:
        if value:
            return value
        return len(info.data.get("chunk_text", ""))


class JudgmentDocument(BaseModel):
    """A complete judgment document and its canonical Evidence adapter."""

    meta: JudgmentMeta
    links: JudgmentLinks
    chunks: list[JudgmentChunk] = Field(min_length=1)

    @model_validator(mode="after")
    def check_chunk_refs(self) -> "JudgmentDocument":
        for chunk in self.chunks:
            if chunk.doc_id != self.meta.doc_id:
                raise ValueError(
                    f"Chunk doc_id mismatch: {chunk.chunk_id} "
                    f"has doc_id={chunk.doc_id}, expected {self.meta.doc_id}"
                )
        return self

    def to_canonical_evidence(
        self,
        *,
        retrieved_at: datetime | None = None,
        supports_claims: list[str] | None = None,
        verification: VerificationStatus = VerificationStatus.UNVERIFIED,
        level: EvidenceLevel = EvidenceLevel.NEED_CHECK,
    ) -> Evidence:
        """Convert this judgment into the canonical immutable Evidence model.

        A judgment has no retrieval timestamp in the legacy schema, so the
        judgment date is used as a deterministic fallback.  Callers that
        know the actual retrieval time can provide ``retrieved_at``.
        """
        judgment_at = _as_utc_datetime(self.meta.judgment_date)
        return Evidence(
            source_id=self.meta.doc_id,
            source_type=SourceType.JUDGMENT,
            title=f"{self.meta.court} {self.meta.case_no}",
            locator=self.meta.doc_id,
            retrieved_at=retrieved_at or judgment_at,
            effective_at=judgment_at,
            supports_claims=list(supports_claims or []),
            verification=verification,
            level=level,
        )


def _as_utc_datetime(value: str) -> datetime:
    """Parse the validated judgment date into a timezone-aware datetime."""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


__all__ = [
    "CourtLevel",
    "CaseType",
    "Holding",
    "ChunkType",
    "JudgmentMeta",
    "JudgmentLinks",
    "JudgmentChunk",
    "JudgmentDocument",
]
