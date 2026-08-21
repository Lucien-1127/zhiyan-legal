"""GraphRAG — 智研法律知識圖譜增強檢索

台灣法律體系高度結構化，平面向量檢索無法理解條文間的體系關係。
GraphRAG 層加入 Knowledge Graph + Qdrant 雙軌檢索：

1. Vector Search → 候選條文
2. Graph Traversal → 體系上下文
3. HyDE 混合排名 → 最終結果
"""
from .schema import (
    EntityType, GraphEntity, GraphRelation, RelationType,
    article, concept, ref, part_of,
)
from .knowledge_graph import LegalKnowledgeGraph
from .qdrant_store import QdrantStore
from .retriever import GraphRAGRetriever
