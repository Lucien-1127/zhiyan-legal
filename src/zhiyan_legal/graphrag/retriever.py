"""GraphRAG Retriever — 知識圖譜 + 向量檢索混合引擎

檢索流程：
1. Vector Search → 候選條文（Qdrant）
2. Graph Traversal → 體系上下文（Knowledge Graph）
3. HyDE 混合排名 → 最終結果

用法：
    retriever = GraphRAGRetriever(kg_path="data/knowledge_graph/civil_code.json")
    results = retriever.query("買賣標的物有瑕疵怎麼辦？")
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from sentence_transformers import SentenceTransformer

from .knowledge_graph import LegalKnowledgeGraph
from .qdrant_store import QdrantStore

logger = logging.getLogger("zhiyan.graphrag.retriever")


class GraphRAGRetriever:
    """GraphRAG 混合檢索器"""

    def __init__(
        self,
        kg_path: Optional[str] = None,
        qdrant_path: Optional[str] = None,
        embed_model: str = "all-MiniLM-L6-v2",
    ):
        # 知識圖譜
        self.kg = LegalKnowledgeGraph()
        if kg_path and Path(kg_path).exists():
            self.kg = LegalKnowledgeGraph.load_json(kg_path)
            logger.info("Loaded KG: %s (%d nodes, %d edges)",
                        kg_path, self.kg.graph.number_of_nodes(),
                        self.kg.graph.number_of_edges())

        # Qdrant 向量儲存
        self.qdrant = QdrantStore(path=qdrant_path) if qdrant_path else None

        # Embedding 模型
        logger.info("Loading embedding model: %s", embed_model)
        self.encoder = SentenceTransformer(embed_model)
        logger.info("Embedding model ready (dim=%d)", self.encoder.get_sentence_embedding_dimension())

    def query(self, text: str, top_k: int = 5,
              include_system_context: bool = True) -> Dict[str, Any]:
        """GraphRAG 查詢

        Args:
            text: 使用者問題
            top_k: 回傳候選條文數
            include_system_context: 是否包含體系上下文

        Returns:
            {
                "query": str,
                "candidates": [{
                    "article_id": str,
                    "title": str,
                    "text": str,
                    "score": float,
                    "system_context": {...} | None,
                }],
                "graph_stats": {"nodes": int, "edges": int},
            }
        """
        # Step 1: 向量檢索候選條文
        query_vec = self.encoder.encode(text).tolist()
        vector_results = self.qdrant.search(query_vec, top_k=top_k) if self.qdrant else []

        # Step 2: 知識圖譜體系上下文
        candidates = []
        for vr in vector_results:
            article_id = vr.get("article_id", "")
            candidate = {
                "article_id": article_id,
                "title": vr.get("title", ""),
                "text": vr.get("text", ""),
                "score": vr.get("score", 0.0),
                "system_context": None,
            }

            if include_system_context and article_id:
                eid = f"art-{article_id}"
                ctx = self.kg.get_system_context(eid)
                if ctx.get("entity"):
                    candidate["system_context"] = ctx

            candidates.append(candidate)

        return {
            "query": text,
            "candidates": candidates,
            "graph_stats": self.kg.stats,
        }

    def query_with_hyde(self, text: str, top_k: int = 5) -> Dict[str, Any]:
        """HyDE 增強查詢（Hypothetical Document Embedding）

        先用 LLM 生成假設性回答，再用該回答做向量檢索。
        可提升抽象問題的召回率。
        """
        # TODO: 用輕量 LLM 生成 hyde_doc
        # 暫時 fallback 到一般 query
        return self.query(text, top_k=top_k)

    def enrich_response(self, query_result: Dict[str, Any]) -> Dict[str, Any]:
        """將 GraphRAG 結果格式化成 LLM-friendly 結構

        包含：
        - 體系路徑（呈現上位/下位關係）
        - 競合條文提示
        - 例外規定提示
        """
        enriched = dict(query_result)
        enriched["system_paths"] = []

        for c in enriched.get("candidates", []):
            ctx = c.get("system_context")
            if not ctx:
                continue
            path = []
            for up in ctx.get("upstream", []):
                path.append(up.get("label", ""))
            if ctx.get("entity"):
                path.append(ctx["entity"].get("label", ""))
            for down in ctx.get("downstream", []):
                path.append(down.get("label", ""))
            enriched["system_paths"].append(" → ".join(path) if path else "")

        return enriched
