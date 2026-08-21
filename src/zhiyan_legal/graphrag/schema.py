"""GraphRAG — 智研法律知識圖譜增強檢索

台灣法律體系高度結構化（民法總則→債編→物權編），
平面向量檢索無法理解條文間的體系關係。
GraphRAG 層加入 Knowledge Graph + Qdrant 雙軌檢索。

Entity types & Relationship types 定義。
"""
from __future__ import annotations
from enum import Enum, auto
from typing import List, Optional


class EntityType(str, Enum):
    """知識圖譜實體類型"""
    STATUTE = "Statute"                 # 法規（民法、刑法）
    PART = "Part"                       # 編（債編、物權編）
    CHAPTER = "Chapter"                 # 章（買賣、租賃）
    SECTION = "Section"                 # 節（物之瑕疵擔保）
    ARTICLE = "Article"                 # 條（§354）
    CONCEPT = "Concept"                 # 法律概念（正當防衛）
    INTERPRETATION = "Interpretation"   # 大法官解釋
    JUDGMENT = "Judgment"              # 最高法院判決
    DOCTRINE = "Doctrine"              # 學說見解


class RelationType(str, Enum):
    """知識圖譜關係類型"""
    IS_A = "is_a"                       # 上位概念（民法 is_a 法律）
    HAS_PART = "has_part"              # 組成（民法 has_part 債編）
    REFERENCES = "references"           # 引用（§354 references §347）
    SUPPLEMENTS = "supplements"         # 補充（§227 supplements §354）
    LEX_SPECIALIS = "lex_specialis"     # 特別法優於普通法
    EXCEPTION_TO = "exception_to"       # 例外規定
    CONFLICTS_WITH = "conflicts_with"   # 請求權競合
    INTERPRETED_BY = "interpreted_by"   # 大法官解釋
    SEE_ALSO = "see_also"              # 參照


class GraphEntity:
    """知識圖譜節點"""
    def __init__(self, eid: str, label: str, etype: EntityType,
                 metadata: Optional[dict] = None):
        self.id = eid
        self.label = label
        self.type = etype
        self.metadata = metadata or {}

    def to_dict(self) -> dict:
        return {
            "id": self.id, "label": self.label,
            "type": self.type.value, "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "GraphEntity":
        return cls(d["id"], d["label"], EntityType(d["type"]), d.get("metadata"))


class GraphRelation:
    """知識圖譜邊"""
    def __init__(self, source: str, target: str, rtype: RelationType,
                 metadata: Optional[dict] = None):
        self.source = source
        self.target = target
        self.type = rtype
        self.metadata = metadata or {}

    def to_dict(self) -> dict:
        return {
            "source": self.source, "target": self.target,
            "type": self.type.value, "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "GraphRelation":
        return cls(d["source"], d["target"], RelationType(d["type"]), d.get("metadata"))


# ── 快速建立實體/關係的輔助函式 ──

def article(eid: str, label: str, **kw) -> GraphEntity:
    return GraphEntity(f"art-{eid}", label, EntityType.ARTICLE, kw)

def concept(cid: str, label: str, **kw) -> GraphEntity:
    return GraphEntity(f"con-{cid}", label, EntityType.CONCEPT, kw)

def ref(source: str, target: str, **kw) -> GraphRelation:
    return GraphRelation(source, target, RelationType.REFERENCES, kw)

def part_of(source: str, target: str) -> GraphRelation:
    return GraphRelation(source, target, RelationType.HAS_PART)
