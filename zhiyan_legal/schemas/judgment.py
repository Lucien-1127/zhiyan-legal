# zhiyan_legal/schemas/judgment.py
# Schema v1.0 — 鎖版 2026-06-29
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
import re


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
    PARTIAL_WIN    = "部分勝訴"  # PoC 之後用 LLM 判斷
    REMAND         = "發回更審"
    DISMISSED      = "駁回上訴"
    SETTLED        = "調解成立"
    UNKNOWN        = "不明"


class ChunkType(str, Enum):
    FACTS        = "facts"        # 事實（原告主張的事實情境）
    REASONING    = "reasoning"    # 理由（法院法律適用與推理過程）
    HOLDING_TEXT = "holding_text"  # 主文（勝敗結論）
    # PoC 不使用，預留
    ISSUES       = "issues"


# ── [A] 識別層 ─────────────────────────────────────────

class JudgmentMeta(BaseModel):
    """不进向量库，走 metadata filter。"""

    court:           str = Field(description="法院全名，如『最高法院民事庭』")
    court_level:     CourtLevel
    case_no:         str = Field(description="如『108年度台上字第1234號』")
    case_type:       CaseType
    cause:           str = Field(description="原始案由字串，保留 fidelity")
    cause_normalized: str | None = Field(
        default=None,
        description="LLM 事後標準化，PoC 階段為 None"
    )
    judgment_date:   str = Field(description="ISO 8601，如『2019-05-15』")
    year:            int

    doc_id: str = Field(
        description="court + case_no + judgment_date 的 SHA256 前16碼",
        exclude=True,  # 不序列化，但供內部使用
    )

    @field_validator("doc_id", mode="before")
    @classmethod
    def compute_doc_id(cls, v: str | None, info) -> str:
        if v:
            return v
        data = info.data
        raw = (
            f"{data.get('court', '')}"
            f"{data.get('case_no', '')}"
            f"{data.get('judgment_date', '')}"
        )
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ── [B] 法律連結層 ─────────────────────────────────────

class JudgmentLinks(BaseModel):
    """三層交叉查詢的橋樑。"""

    cited_statutes:         list[str] = Field(
        default_factory=list,
        description="條號層正規化，如『民法第184條』。項號截斷（PoC 策略）。"
    )
    cited_interpretations:  list[str] = Field(
        default_factory=list,
        description="釋字或憲判字，如『釋字第768號』『憲判字第1號』"
    )
    cited_cases:            list[str] = Field(
        default_factory=list,
        description="引用他案案號。PoC 階段為空 list。"
    )
    holding: Holding = Field(
        default=Holding.UNKNOWN,
        description="從 mainText 規則推斷（PoC），LLM 判斷（PoC之後）"
    )


# ── [C] 向量內容層 ─────────────────────────────────────

class JudgmentChunk(BaseModel):
    """一份裁判書拆成多個 chunk，各自獨立 embedding。"""

    chunk_id:    str = Field(
        description="格式：{doc_id}_{chunk_type.value}_{chunk_index:02d}"
    )
    doc_id:      str = Field(description="關聯回 JudgmentMeta.doc_id")
    chunk_type:  ChunkType
    chunk_index: int = Field(ge=0)
    chunk_text:  str = Field(min_length=10)
    source_field: str = Field(description="來源 JSON 欄位名，如 facts / reason / mainText")
    char_count:  int = Field(ge=0, description="字符數，用於 chunk 大小監控")

    @field_validator("char_count", mode="before")
    @classmethod
    def auto_char_count(cls, v: int | None, info) -> int:
        if v:
            return v
        return len(info.data.get("chunk_text", ""))


# ── 頂層聚合模型 ───────────────────────────────────────

class JudgmentDocument(BaseModel):
    """
    一份裁判書的完整結構。
    使用時：
        doc = parse_raw_judgment(raw_json)
        # 存取 metadata
        doc.meta.court        # → '最高法院'
        doc.meta.case_no      # → '108年度台上字第1234號'
        # 存取法律連結
        doc.links.cited_statutes  # → ['民法第184條', '民法第187條']
        # 存取 chunk（各自可獨立 embedding）
        for chunk in doc.chunks:
            embed(chunk.chunk_text)
    """

    meta:   JudgmentMeta
    links:  JudgmentLinks
    chunks: list[JudgmentChunk] = Field(min_length=1)

    @model_validator(mode="after")
    def check_chunk_refs(self) -> JudgmentDocument:
        """確保所有 chunk 的 doc_id 與 meta.doc_id 一致。"""
        for chunk in self.chunks:
            if chunk.doc_id != self.meta.doc_id:
                raise ValueError(
                    f"Chunk doc_id mismatch: {chunk.chunk_id} "
                    f"has doc_id={chunk.doc_id}, "
                    f"expected {self.meta.doc_id}"
                )
        return self

# ⚠️  此檔案已廢棄，請改用 src/zhiyan_legal/schemas/judgment.py
# Deprecated since v3.9.4 — will be removed in v4.0
from zhiyan_legal.schemas.judgment import *  # noqa: F401, F403
