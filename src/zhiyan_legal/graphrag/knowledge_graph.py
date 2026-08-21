"""Knowledge Graph — NetworkX 實現的台灣法律知識圖譜

提供：
- 節點/邊的新增與查詢
- 體系關係遍歷（上位/下位/引用/競合）
- 圖序列化（JSON）
- GraphML 匯出（可視化用）
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import networkx as nx

from .schema import (
    EntityType, GraphEntity, GraphRelation, RelationType,
)


class LegalKnowledgeGraph:
    """台灣法律知識圖譜 — NetworkX 底層"""

    def __init__(self):
        self.graph = nx.MultiDiGraph()

    # ── 節點操作 ──

    def add_entity(self, entity: GraphEntity) -> str:
        """加入節點，回傳 entity.id"""
        self.graph.add_node(
            entity.id,
            label=entity.label,
            type=entity.type.value,
            metadata=entity.metadata,
        )
        return entity.id

    def get_entity(self, eid: str) -> Optional[GraphEntity]:
        if eid not in self.graph:
            return None
        d = self.graph.nodes[eid]
        return GraphEntity(
            eid, d["label"], EntityType(d["type"]), d.get("metadata")
        )

    def search_entity(self, keyword: str, limit: int = 10) -> List[GraphEntity]:
        """依 label 模糊搜尋節點"""
        results = []
        for nid, d in self.graph.nodes(data=True):
            if keyword in d.get("label", ""):
                results.append(GraphEntity(
                    nid, d["label"], EntityType(d["type"]), d.get("metadata")
                ))
            if len(results) >= limit:
                break
        return results

    def count_entities(self, etype: Optional[EntityType] = None) -> int:
        if etype is None:
            return self.graph.number_of_nodes()
        return sum(1 for _, d in self.graph.nodes(data=True)
                   if d.get("type") == etype.value)

    # ── 邊操作 ──

    def add_relation(self, relation: GraphRelation) -> Tuple[str, str]:
        self.graph.add_edge(
            relation.source, relation.target,
            type=relation.type.value,
            metadata=relation.metadata,
        )
        return (relation.source, relation.target)

    def get_relations(self, eid: str,
                      rtype: Optional[RelationType] = None) -> List[GraphRelation]:
        results = []
        for _, tgt, d in self.graph.out_edges(eid, data=True):
            if rtype is None or d.get("type") == rtype.value:
                results.append(GraphRelation(eid, tgt, RelationType(d["type"]), d.get("metadata")))
        for src, _, d in self.graph.in_edges(eid, data=True):
            if rtype is None or d.get("type") == rtype.value:
                # 避免重複
                if not any(r.source == src for r in results):
                    results.append(GraphRelation(src, eid, RelationType(d["type"]), d.get("metadata")))
        return results

    # ── 體系查詢 ──

    def get_upstream(self, eid: str) -> List[GraphEntity]:
        """取得上位概念（is_a / has_part 方向的上層）"""
        parents = []
        for src, _, d in self.graph.in_edges(eid, data=True):
            if d.get("type") in (RelationType.IS_A.value, RelationType.HAS_PART.value):
                ent = self.get_entity(src)
                if ent:
                    parents.append(ent)
        return parents

    def get_downstream(self, eid: str) -> List[GraphEntity]:
        """取得下位概念"""
        children = []
        for _, tgt, d in self.graph.out_edges(eid, data=True):
            if d.get("type") in (RelationType.IS_A.value, RelationType.HAS_PART.value):
                ent = self.get_entity(tgt)
                if ent:
                    children.append(ent)
        return children

    def get_references(self, eid: str) -> List[GraphEntity]:
        """取得所有引用/參照的條文"""
        refs = []
        for _, tgt, d in self.graph.out_edges(eid, data=True):
            if d.get("type") in (RelationType.REFERENCES.value,
                                  RelationType.SEE_ALSO.value):
                ent = self.get_entity(tgt)
                if ent:
                    refs.append(ent)
        return refs

    def get_system_context(self, eid: str, depth: int = 2) -> dict:
        """取得條文的完整體系上下文（用於 GraphRAG 輸出）

        Args:
            eid: 實體 ID
            depth: 向上/向下遍歷層數

        Returns:
            {
                "entity": {...},
                "upstream": [...],     # 上位體系
                "downstream": [...],   # 下位體系
                "references": [...],   # 引用條文
                "supplements": [...],  # 補充規定
                "exceptions": [...],   # 例外規定
            }
        """
        entity = self.get_entity(eid)
        if not entity:
            return {"entity": None}

        result = {"entity": entity.to_dict()}

        # 體系上下位
        upstream, downstream = [], []
        visited: Set[str] = set()
        self._traverse_up(eid, depth, upstream, visited)
        self._traverse_down(eid, depth, downstream, visited)
        result["upstream"] = [e.to_dict() for e in upstream]
        result["downstream"] = [e.to_dict() for e in downstream]

        # 關係
        refs, supps, excs = [], [], []
        for _, tgt, d in self.graph.out_edges(eid, data=True):
            t = d.get("type")
            ent = self.get_entity(tgt)
            if not ent:
                continue
            if t in (RelationType.REFERENCES.value, RelationType.SEE_ALSO.value):
                refs.append(ent.to_dict())
            elif t == RelationType.SUPPLEMENTS.value:
                supps.append(ent.to_dict())
            elif t == RelationType.EXCEPTION_TO.value:
                excs.append(ent.to_dict())

        result["references"] = refs
        result["supplements"] = supps
        result["exceptions"] = excs

        return result

    def _traverse_up(self, eid: str, depth: int, results: list,
                     visited: set):
        if depth <= 0 or eid in visited:
            return
        visited.add(eid)
        for src, _, d in self.graph.in_edges(eid, data=True):
            if d.get("type") in (RelationType.IS_A.value, RelationType.HAS_PART.value):
                ent = self.get_entity(src)
                if ent:
                    results.append(ent)
                    self._traverse_up(src, depth - 1, results, visited)

    def _traverse_down(self, eid: str, depth: int, results: list,
                       visited: set):
        if depth <= 0 or eid in visited:
            return
        visited.add(eid)
        for _, tgt, d in self.graph.out_edges(eid, data=True):
            if d.get("type") in (RelationType.IS_A.value, RelationType.HAS_PART.value):
                ent = self.get_entity(tgt)
                if ent:
                    results.append(ent)
                    self._traverse_down(tgt, depth - 1, results, visited)

    # ── 序列化 ──

    def to_json(self) -> dict:
        nodes = []
        for nid, d in self.graph.nodes(data=True):
            nodes.append({
                "id": nid, "label": d.get("label", ""),
                "type": d.get("type", ""), "metadata": d.get("metadata", {}),
            })
        edges = []
        for src, tgt, d in self.graph.edges(data=True):
            edges.append({
                "source": src, "target": tgt,
                "type": d.get("type", ""),
                "metadata": d.get("metadata", {}),
            })
        return {"nodes": nodes, "edges": edges}

    def save_json(self, path: str):
        Path(path).write_text(
            json.dumps(self.to_json(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def load_json(cls, path: str) -> "LegalKnowledgeGraph":
        kg = cls()
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        for nd in data.get("nodes", []):
            ent = GraphEntity(nd["id"], nd["label"],
                              EntityType(nd["type"]), nd.get("metadata"))
            kg.add_entity(ent)
        for ed in data.get("edges", []):
            rel = GraphRelation(ed["source"], ed["target"],
                                RelationType(ed["type"]), ed.get("metadata"))
            kg.add_relation(rel)
        return kg

    @property
    def stats(self) -> dict:
        return {
            "nodes": self.graph.number_of_nodes(),
            "edges": self.graph.number_of_edges(),
            "articles": self.count_entities(EntityType.ARTICLE),
            "concepts": self.count_entities(EntityType.CONCEPT),
        }
