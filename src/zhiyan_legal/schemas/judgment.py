# src/zhiyan_legal/schemas/judgment.py
# Schema v1.0 — 鎖版 2026-06-29
# 從 zhiyan_legal/schemas/judgment.py 搬入（舊位置已廢棄）
"""
裁判書結構化 Schema。
[A] 識別層  — 不進向量庫，純粹 metadata 過濾與去重
[B] 法律連結層 — 三層交叉查詢的橋樑（條文、釋字、他案）
[C] 向量內容層 — 三種 chunk，各自獨立 embedding（PoC 階段）
"""

from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field, field_validator, model_validator
import hashlib


# ── 列舉型別 ───────────────────────────────────────────

class CourtLevel(str, Enum):
    SUPREME  = "supreme"   # 最高法院
    HIGH     = "high"      # 高等法院
    DISTRICT = "district"  # 地方法院


class CaseType(str, Enum):
    CIVIL          = "民事"
    CRIMINAL       = "刑事"
    ADMINISTRATIVE = "行政"
    FAMILY         = "家事"
    JUVENILE       = "少年"


class Holding(str, Enum):
    PLAINTIFF_WIN  = "原告勝"
    DEFENDANT_WIN  = "被告勝"
    PARTIAL_WIN    = "部分勝訴"
    REMAND         = "發回更審"
    DISMISSED      = "駁回上訴"
    SETTLED        = "調解成立"
    UNKNOWN        = "不明"


class ChunkType(str, Enum):
    FACTS        = "facts"
    REASONING    = "reasoning"
    HOLDING_TEXT = "holding_text"
    ISSUES       = "issues"  # PoC 預留


# ── [A] 識別層 ─────────────────────────────────────────

class JudgmentMeta(BaseModel):
    court:            str = Field(description="法院全名，如『最高法院民事庭』")
    court_level:      CourtLevel
    case_no:          str = Field(description="如『108年度台上字第1234號』")
    case_type:        CaseType
    cause:            str = Field(description="原始案由字串")
    cause_normalized: str | None = Field(default=None)
    judgment_date:    str = Field(description="ISO 8601，如『2019-05-15』")
    year:             int
    doc_id: str = Field(description="court+case_no+judgment_date 的 SHA256 前16碼", exclude=True)

    @field_validator("doc_id", mode="before")
    @classmethod
    def compute_doc_id(cls, v: str | None, info) -> str:
        if v:
            return v
        data = info.data
        raw = f"{data.get('court', '')}{data.get('case_no', '')}{data.get('judgment_date', '')}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ── [B] 法律連結層 ─────────────────────────────────────

class JudgmentLinks(BaseModel):
    cited_statutes:        list[str] = Field(default_factory=list)
    cited_interpretations: list[str] = Field(default_factory=list)
    cited_cases:           list[str] = Field(default_factory=list)
    holding: Holding = Field(default=Holding.UNKNOWN)


# ── [C] 向量內容層 ─────────────────────────────────────

class JudgmentChunk(BaseModel):
    chunk_id:     str = Field(description="格式：{doc_id}_{chunk_type.value}_{chunk_index:02d}")
    doc_id:       str
    chunk_type:   ChunkType
    chunk_index:  int = Field(ge=0)
    chunk_text:   str = Field(min_length=10)
    source_field: str
    char_count:   int = Field(ge=0)

    @field_validator("char_count", mode="before")
    @classmethod
    def auto_char_count(cls, v: int | None, info) -> int:
        if v:
            return v
        return len(info.data.get("chunk_text", ""))


# ── 頂層聚合模型 ───────────────────────────────────────

class JudgmentDocument(BaseModel):
    meta:   JudgmentMeta
    links:  JudgmentLinks
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
