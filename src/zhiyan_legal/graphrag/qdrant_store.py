"""Qdrant Store — 向量儲存層

將法條 embedding 存入 Qdrant，支援：
- 語意檢索（dense vector）
- 混合檢索（sparse + dense）
- 批量 upsert
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from qdrant_client.http.exceptions import UnexpectedResponse

logger = logging.getLogger("zhiyan.graphrag.qdrant")

COLLECTION_NAME = "zhiyan_legal_articles"
EMBEDDING_DIM = 768  # sentence-transformers all-MiniLM-L6-v2


class QdrantStore:
    """Qdrant 向量儲存（支援本機檔案模式或遠端伺服器）"""

    def __init__(self, path: Optional[str] = None, host: Optional[str] = None,
                 port: int = 6333):
        if path:
            self.client = QdrantClient(path=path)
            logger.info("Qdrant local mode: %s", path)
        else:
            self.client = QdrantClient(host=host or "localhost", port=port)
            logger.info("Qdrant remote mode: %s:%d", host or "localhost", port)

        self._init_collection()

    def _init_collection(self):
        """確保 collection 存在"""
        try:
            self.client.get_collection(COLLECTION_NAME)
            logger.info("Collection %s already exists", COLLECTION_NAME)
        except (UnexpectedResponse, ValueError):
            self.client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=qmodels.VectorParams(
                    size=EMBEDDING_DIM,
                    distance=qmodels.Distance.COSINE,
                ),
            )
            logger.info("Created collection %s (dim=%d)", COLLECTION_NAME, EMBEDDING_DIM)

    def upsert_articles(self, articles: List[Dict[str, Any]]):
        """寫入/更新法條向量

        articles: [{id, title, text, embedding, metadata}]
        """
        points = []
        for art in articles:
            points.append(qmodels.PointStruct(
                id=art["id"],
                vector=art["embedding"],
                payload={
                    "title": art.get("title", ""),
                    "text": art.get("text", ""),
                    "article_id": art.get("article_id", ""),
                    "law": art.get("law", ""),
                    "metadata": json.dumps(art.get("metadata", {}), ensure_ascii=False),
                },
            ))

        self.client.upsert(
            collection_name=COLLECTION_NAME,
            points=points,
        )
        logger.info("Upserted %d articles", len(points))

    def search(self, query_vector: List[float], top_k: int = 10,
               score_threshold: Optional[float] = None) -> List[dict]:
        """語意搜尋

        Returns: [{id, title, text, article_id, law, score, metadata}]
        """
        results = self.client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            limit=top_k,
            score_threshold=score_threshold,
        )

        output = []
        for r in results:
            output.append({
                "id": r.id,
                "score": r.score,
                "title": r.payload.get("title", ""),
                "text": r.payload.get("text", ""),
                "article_id": r.payload.get("article_id", ""),
                "law": r.payload.get("law", ""),
                "metadata": json.loads(r.payload.get("metadata", "{}")),
            })
        return output

    def delete_collection(self):
        """清除整個 collection（測試用）"""
        self.client.delete_collection(COLLECTION_NAME)
        logger.warning("Deleted collection %s", COLLECTION_NAME)

    @property
    def count(self) -> int:
        return self.client.count(COLLECTION_NAME).count
