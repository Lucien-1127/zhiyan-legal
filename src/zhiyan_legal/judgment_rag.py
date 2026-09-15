"""司法院判決書全量／增量同步與本地向量檢索。

這個模組把「官方 JID → JDoc → 版本化全文 → 語意切片 → Qdrant」
串成一條可重跑、可恢復、可刪除已下架資料的管線。

設計原則：
* 同一 JID 是同一筆判決的穩定主鍵；內容 hash 改變才重切片、重向量化。
* JFULLTYPE=file 時保留官方 PDF 連結與可用的文字欄位；若沒有可索引文字，
  狀態會是 pending_text，不會把空內容送入向量庫。
* 官方回傳「查無資料／已移除」時，保留稽核紀錄並從向量庫移除該判決。
* API 憑證只從環境變數讀取，不寫入資料庫、Excel、log 或 Git。

需要的選用依賴：
    pip install -e '.[rag]'
"""
from __future__ import annotations

import asyncio
from io import BytesIO
import hashlib
import json
import logging
import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence
from uuid import uuid5, NAMESPACE_URL

logger = logging.getLogger("zhiyan_legal.judgment_rag")

OFFICIAL_API_BASE = "https://data.judicial.gov.tw/jdg/api"
DEFAULT_COLLECTION = "zhiyan_legal_judgments"
DEFAULT_QDRANT_PATH = "data/qdrant"
DEFAULT_MANIFEST_PATH = "data/judgments/manifest.sqlite3"
DEFAULT_EMBED_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

_REMOVED_MARKERS = ("查無資料", "已從系統移除", "不再公開", "未公開")
_SECTION_RULES: tuple[tuple[str, str], ...] = (
    ("主文", "holding"),
    ("事實", "facts"),
    ("理由", "reasoning"),
    ("爭點", "issues"),
)


class JudgmentRagError(RuntimeError):
    """判決 RAG 流程的可預期錯誤。"""


@dataclass(frozen=True)
class JudgmentRecord:
    jid: str
    year: str
    case_word: str
    case_number: str
    judgment_date: str
    title: str
    full_type: str
    content: str
    pdf_url: str = ""
    source_url: str = ""
    retrieved_at: str = ""

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class JudgmentChunk:
    chunk_id: str
    jid: str
    sequence: int
    section: str
    text: str
    char_count: int
    content_hash: str


class OfficialJudicialClient:
    """司法院官方裁判書 API client。

    Token 有效時間由官方服務決定；client 只在本次程序記憶體中保存 token。
    """

    def __init__(
        self,
        username: str,
        password: str,
        *,
        base_url: str = OFFICIAL_API_BASE,
        timeout: float = 60.0,
    ) -> None:
        if not username or not password:
            raise JudgmentRagError(
                "缺少司法院 API 憑證。請設定 JUDICIAL_API_USER 與 "
                "JUDICIAL_API_PASSWORD，不要把帳密貼到程式碼或 Excel。"
            )
        self.username = username
        self.password = password
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._token: str | None = None

    async def _post(self, path: str, payload: dict[str, Any]) -> Any:
        try:
            import httpx
        except ImportError as exc:
            raise JudgmentRagError("需要 httpx：請安裝專案依賴") from exc
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/{path.lstrip('/')}",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            try:
                return response.json()
            except ValueError as exc:
                raise JudgmentRagError(f"司法院 API 回傳非 JSON：{path}") from exc

    async def authenticate(self) -> str:
        payload = await self._post(
            "Auth", {"user": self.username, "password": self.password}
        )
        token = str(payload.get("Token", "")).strip() if isinstance(payload, dict) else ""
        if not token:
            raise JudgmentRagError("司法院 API 驗證失敗，請確認帳號密碼與開放 API 權限")
        self._token = token
        return token

    async def _authorized_post(self, path: str, payload: dict[str, Any]) -> Any:
        if not self._token:
            await self.authenticate()
        result = await self._post(path, {"token": self._token, **payload})
        if isinstance(result, dict) and "驗證失敗" in str(result.get("error", "")):
            await self.authenticate()
            result = await self._post(path, {"token": self._token, **payload})
        return result

    async def list_changes(self) -> list[dict[str, Any]]:
        result = await self._authorized_post("JList", {})
        if not isinstance(result, list):
            raise JudgmentRagError("JList 回傳格式不可驗證")
        return result

    async def get_judgment(self, jid: str) -> dict[str, Any]:
        result = await self._authorized_post("JDoc", {"j": jid})
        if not isinstance(result, dict):
            raise JudgmentRagError(f"JDoc 回傳格式不可驗證：{jid}")
        await self._hydrate_file_content(result)
        return result

    async def _hydrate_file_content(self, payload: dict[str, Any]) -> None:
        """若 JDoc 只有 PDF 連結，嘗試抽取可選取文字；掃描 PDF 仍會留待人工處理。"""
        full = payload.get("JFULLX")
        if not isinstance(full, dict):
            return
        if _text(full.get("JFULLCONTENT")):
            return
        if _text(full.get("JFULLTYPE")).lower() != "file":
            return
        pdf_url = _text(full.get("JFULLPDF"))
        if not pdf_url:
            return
        try:
            import httpx

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(pdf_url)
                response.raise_for_status()
            full["JFULLCONTENT"] = extract_pdf_text(response.content)
        except Exception as exc:
            logger.warning("無法抽取 PDF 全文：%s", exc)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(value: Any) -> str:
    return str(value or "").replace("\x00", "").strip()


def _is_removed(payload: dict[str, Any]) -> bool:
    if str(payload.get("error", "")).strip():
        return any(marker in str(payload.get("error")) for marker in _REMOVED_MARKERS)
    return False


def parse_jdoc(payload: dict[str, Any], *, jid_hint: str = "") -> JudgmentRecord | None:
    """將官方 JDoc JSON 正規化成穩定主檔。"""
    if _is_removed(payload):
        return None
    if _text(payload.get("error")):
        # Do not persist an API failure as an empty judgment or echo its payload.
        raise JudgmentRagError("JDoc 回傳 API 錯誤（非撤下）；未更新判決資料")
    full = payload.get("JFULLX") or {}
    if not isinstance(full, dict):
        full = {}
    jid = _text(payload.get("JID")) or jid_hint
    content = _text(full.get("JFULLCONTENT"))
    if not jid:
        raise JudgmentRagError("JDoc 缺少 JID")
    attachments = payload.get("ATTACHMENTS") or []
    attachment_url = ""
    if isinstance(attachments, list):
        for item in attachments:
            if isinstance(item, dict) and _text(item.get("URL")):
                attachment_url = _text(item.get("URL"))
                break
    return JudgmentRecord(
        jid=jid,
        year=_text(payload.get("JYEAR")),
        case_word=_text(payload.get("JCASE")),
        case_number=_text(payload.get("JNO")),
        judgment_date=_text(payload.get("JDATE")),
        title=_text(payload.get("JTITLE")),
        full_type=_text(full.get("JFULLTYPE")) or "unknown",
        content=content,
        pdf_url=_text(full.get("JFULLPDF")) or attachment_url,
        source_url=OFFICIAL_API_BASE + "/JDoc",
        retrieved_at=_now_iso(),
    )


def _normalise_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_pdf_text(pdf_bytes: bytes) -> str:
    """從可選取文字的 PDF 抽取全文；掃描影像 PDF 回傳空字串。"""
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise JudgmentRagError("file 型判決需要 pypdf：請安裝專案依賴") from exc
    reader = PdfReader(BytesIO(pdf_bytes))
    pages = [page.extract_text() or "" for page in reader.pages]
    return _normalise_text("\n\n".join(pages))


def _detect_section(text: str) -> str:
    compact = text.strip().replace(" ", "")
    for marker, section in _SECTION_RULES:
        if compact.startswith(marker) or f"\n{marker}" in compact[:80]:
            return section
    return "full_text"


def chunk_judgment(
    record: JudgmentRecord,
    *,
    max_chars: int = 800,
    overlap: int = 80,
) -> list[JudgmentChunk]:
    """依段落與字數切成可嵌入的語意單元。"""
    if max_chars < 100:
        raise ValueError("max_chars 不應小於 100")
    if overlap < 0 or overlap >= max_chars:
        raise ValueError("overlap 必須大於等於 0 且小於 max_chars")
    text = _normalise_text(record.content)
    if not text:
        return []

    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    units: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) <= max_chars:
            candidate = f"{current}\n{paragraph}".strip() if current else paragraph
            if len(candidate) <= max_chars:
                current = candidate
            else:
                if current:
                    units.append(current)
                current = paragraph
            continue
        if current:
            units.append(current)
            current = ""
        start = 0
        while start < len(paragraph):
            end = min(start + max_chars, len(paragraph))
            units.append(paragraph[start:end])
            if end >= len(paragraph):
                break
            start = end - overlap
    if current:
        units.append(current)

    chunks: list[JudgmentChunk] = []
    for sequence, text_unit in enumerate(units, start=1):
        chunk_id = str(uuid5(NAMESPACE_URL, f"{record.jid}:{record.content_hash}:{sequence}"))
        chunks.append(
            JudgmentChunk(
                chunk_id=chunk_id,
                jid=record.jid,
                sequence=sequence,
                section=_detect_section(text_unit),
                text=text_unit,
                char_count=len(text_unit),
                content_hash=record.content_hash,
            )
        )
    return chunks


class JudgmentManifest:
    """SQLite manifest：全文版本、切片狀態、失敗與移除稽核。"""

    def __init__(self, path: str = DEFAULT_MANIFEST_PATH) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS judgments (
                jid TEXT PRIMARY KEY,
                year TEXT NOT NULL DEFAULT '',
                case_word TEXT NOT NULL DEFAULT '',
                case_number TEXT NOT NULL DEFAULT '',
                judgment_date TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL DEFAULT '',
                full_type TEXT NOT NULL DEFAULT '',
                content TEXT NOT NULL DEFAULT '',
                content_hash TEXT NOT NULL DEFAULT '',
                pdf_url TEXT NOT NULL DEFAULT '',
                source_url TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'active',
                last_retrieved_at TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT '',
                removed_at TEXT NOT NULL DEFAULT '',
                error TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id TEXT PRIMARY KEY,
                jid TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                section TEXT NOT NULL,
                text TEXT NOT NULL,
                char_count INTEGER NOT NULL,
                content_hash TEXT NOT NULL,
                indexed INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(jid) REFERENCES judgments(jid)
            );
            CREATE INDEX IF NOT EXISTS idx_chunks_jid ON chunks(jid);
            CREATE INDEX IF NOT EXISTS idx_judgments_status ON judgments(status);
            CREATE TABLE IF NOT EXISTS sync_runs (
                run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT NOT NULL,
                fetched INTEGER NOT NULL DEFAULT 0,
                changed INTEGER NOT NULL DEFAULT 0,
                removed INTEGER NOT NULL DEFAULT 0,
                failed INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        self.conn.commit()

    def get_hash(self, jid: str) -> str:
        row = self.conn.execute("SELECT content_hash FROM judgments WHERE jid = ?", (jid,)).fetchone()
        return str(row[0]) if row else ""

    def upsert_record(self, record: JudgmentRecord, chunks: Sequence[JudgmentChunk]) -> bool:
        previous = self.conn.execute(
            """
            SELECT content_hash, status,
                   EXISTS(SELECT 1 FROM chunks WHERE chunks.jid = judgments.jid) AS has_chunks
            FROM judgments WHERE jid = ?
            """,
            (record.jid,),
        ).fetchone()
        changed = (
            previous is None
            or str(previous["content_hash"]) != record.content_hash
            or str(previous["status"]) != "active"
            or (bool(chunks) and not bool(previous["has_chunks"]))
        )
        now = _now_iso()
        self.conn.execute(
            """
            INSERT INTO judgments
              (jid, year, case_word, case_number, judgment_date, title, full_type,
               content, content_hash, pdf_url, source_url, status, last_retrieved_at,
               updated_at, removed_at, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, '', '')
            ON CONFLICT(jid) DO UPDATE SET
              year=excluded.year, case_word=excluded.case_word,
              case_number=excluded.case_number, judgment_date=excluded.judgment_date,
              title=excluded.title, full_type=excluded.full_type, content=excluded.content,
              content_hash=excluded.content_hash, pdf_url=excluded.pdf_url,
              source_url=excluded.source_url, status='active',
              last_retrieved_at=excluded.last_retrieved_at, updated_at=excluded.updated_at,
              removed_at='', error=''
            """,
            (record.jid, record.year, record.case_word, record.case_number,
             record.judgment_date, record.title, record.full_type, record.content,
             record.content_hash, record.pdf_url, record.source_url,
             record.retrieved_at or now, now),
        )
        if changed:
            self.conn.execute("DELETE FROM chunks WHERE jid = ?", (record.jid,))
            self.conn.executemany(
                """
                INSERT INTO chunks
                  (chunk_id, jid, sequence, section, text, char_count, content_hash, indexed)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                """,
                [(c.chunk_id, c.jid, c.sequence, c.section, c.text, c.char_count, c.content_hash) for c in chunks],
            )
        self.conn.commit()
        return changed

    def pending_chunks(self, jid: str) -> list[JudgmentChunk]:
        rows = self.conn.execute(
            """
            SELECT chunk_id, jid, sequence, section, text, char_count, content_hash
            FROM chunks WHERE jid = ? AND indexed = 0 ORDER BY sequence
            """,
            (jid,),
        ).fetchall()
        return [JudgmentChunk(**dict(row)) for row in rows]

    def _write_removal_tombstone(self, jid: str, status: str, error: str) -> None:
        now = _now_iso()
        self.conn.execute(
            """
            INSERT INTO judgments
              (jid, status, last_retrieved_at, updated_at, removed_at, error)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(jid) DO UPDATE SET
              year='', case_word='', case_number='', judgment_date='', title='',
              full_type='', content='', content_hash='', pdf_url='', source_url='',
              status=excluded.status, last_retrieved_at=excluded.last_retrieved_at,
              updated_at=excluded.updated_at,
              removed_at=CASE
                WHEN judgments.removed_at='' THEN excluded.removed_at
                ELSE judgments.removed_at
              END,
              error=excluded.error
            """,
            (jid, status, now, now, now, error),
        )
        self.conn.execute("DELETE FROM chunks WHERE jid = ?", (jid,))
        self.conn.commit()

    def mark_removal_pending(
        self,
        jid: str,
        error: str,
        *,
        cleanup_error: str = "",
    ) -> None:
        detail = error
        if cleanup_error:
            detail = f"{error}; vector cleanup pending ({cleanup_error})"
        self._write_removal_tombstone(jid, "removal_pending", detail)

    def mark_removed(self, jid: str, error: str = "officially removed") -> None:
        self._write_removal_tombstone(jid, "removed", error)

    def mark_pending_text(self, jid: str, error: str) -> None:
        self.conn.execute(
            "UPDATE judgments SET status='pending_text', updated_at=?, error=? WHERE jid=?",
            (_now_iso(), error, jid),
        )
        self.conn.commit()

    def set_indexed(self, chunk_ids: Iterable[str]) -> None:
        ids = list(chunk_ids)
        if not ids:
            return
        self.conn.executemany("UPDATE chunks SET indexed=1 WHERE chunk_id=?", [(item,) for item in ids])
        self.conn.commit()

    def reset_indexed(self, jid: str) -> None:
        self.conn.execute("UPDATE chunks SET indexed=0 WHERE jid=?", (jid,))
        self.conn.commit()

    def stats(self) -> dict[str, int]:
        rows = self.conn.execute("SELECT status, COUNT(*) AS count FROM judgments GROUP BY status").fetchall()
        result = {str(row[0]): int(row[1]) for row in rows}
        result["chunks"] = int(self.conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0])
        result["indexed_chunks"] = int(self.conn.execute("SELECT COUNT(*) FROM chunks WHERE indexed=1").fetchone()[0])
        return result

    def close(self) -> None:
        self.conn.close()


class LocalEmbeddingModel:
    """懶載入的本地多語嵌入模型。"""

    def __init__(self, model_name: str = DEFAULT_EMBED_MODEL) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise JudgmentRagError(
                "需要 sentence-transformers：請執行 pip install -e '.[rag]'"
            ) from exc
        self.model = SentenceTransformer(model_name)
        self.model_name = model_name
        self.dimension = int(self.model.get_sentence_embedding_dimension())

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        values = self.model.encode(list(texts), normalize_embeddings=True, show_progress_bar=False)
        return values.tolist()


class JudgmentVectorStore:
    """Qdrant 本地或遠端 collection 的判決儲存。"""

    def __init__(
        self,
        *,
        path: str | None = DEFAULT_QDRANT_PATH,
        host: str | None = None,
        port: int = 6333,
        collection: str = DEFAULT_COLLECTION,
        dimension: int = 384,
    ) -> None:
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.http import models as qmodels
        except ImportError as exc:
            raise JudgmentRagError(
                "需要 qdrant-client：請執行 pip install -e '.[rag]'"
            ) from exc
        self._qmodels = qmodels
        self.collection = collection
        self.client = QdrantClient(path=path) if path else QdrantClient(host=host or "localhost", port=port)
        try:
            self.client.get_collection(collection)
        except Exception:
            self.client.create_collection(
                collection_name=collection,
                vectors_config=qmodels.VectorParams(size=dimension, distance=qmodels.Distance.COSINE),
            )

    def upsert(self, chunks: Sequence[JudgmentChunk], records: dict[str, JudgmentRecord], vectors: Sequence[Sequence[float]]) -> None:
        points = []
        for chunk, vector in zip(chunks, vectors):
            record = records[chunk.jid]
            points.append(
                self._qmodels.PointStruct(
                    id=chunk.chunk_id,
                    vector=list(vector),
                    payload={
                        "jid": record.jid,
                        "text": chunk.text,
                        "section": chunk.section,
                        "sequence": chunk.sequence,
                        "char_count": chunk.char_count,
                        "content_hash": chunk.content_hash,
                        "year": record.year,
                        "case_word": record.case_word,
                        "case_number": record.case_number,
                        "judgment_date": record.judgment_date,
                        "title": record.title,
                        "full_type": record.full_type,
                        "pdf_url": record.pdf_url,
                        "source_url": record.source_url,
                    },
                )
            )
        if points:
            self.client.upsert(collection_name=self.collection, points=points, wait=True)

    def delete_judgment(self, jid: str) -> None:
        self.client.delete(
            collection_name=self.collection,
            points_selector=self._qmodels.FilterSelector(
                filter=self._qmodels.Filter(
                    must=[self._qmodels.FieldCondition(key="jid", match=self._qmodels.MatchValue(value=jid))]
                )
            ),
            wait=True,
        )

    def search(self, vector: Sequence[float], top_k: int = 8, *, jid: str = "", year: str = "") -> list[dict[str, Any]]:
        must = []
        if jid:
            must.append(self._qmodels.FieldCondition(key="jid", match=self._qmodels.MatchValue(value=jid)))
        if year:
            must.append(self._qmodels.FieldCondition(key="year", match=self._qmodels.MatchValue(value=year)))
        query_filter = self._qmodels.Filter(must=must) if must else None
        if hasattr(self.client, "query_points"):
            results = self.client.query_points(
                collection_name=self.collection,
                query=list(vector),
                query_filter=query_filter,
                limit=top_k,
                with_payload=True,
            ).points
        else:
            results = self.client.search(
                collection_name=self.collection,
                query_vector=list(vector),
                query_filter=query_filter,
                limit=top_k,
            )
        output = []
        for item in results:
            payload = dict(item.payload or {})
            payload.update({"id": str(item.id), "score": float(item.score)})
            output.append(payload)
        return output

    def count(self) -> int:
        return int(self.client.count(collection_name=self.collection, exact=True).count)

    def close(self) -> None:
        """Release Qdrant connections and the embedded storage directory lock."""
        self.client.close()


class JudgmentRagIndex:
    """同步、建立索引、查詢與狀態的主要 facade。"""

    def __init__(
        self,
        *,
        manifest_path: str = DEFAULT_MANIFEST_PATH,
        qdrant_path: str | None = DEFAULT_QDRANT_PATH,
        qdrant_host: str | None = None,
        qdrant_port: int = 6333,
        collection: str = DEFAULT_COLLECTION,
        embed_model: str = DEFAULT_EMBED_MODEL,
        max_chars: int = 800,
        overlap: int = 80,
        batch_size: int = 32,
    ) -> None:
        self.manifest = JudgmentManifest(manifest_path)
        self.embedder = LocalEmbeddingModel(embed_model)
        self.store = JudgmentVectorStore(
            path=qdrant_path,
            host=qdrant_host,
            port=qdrant_port,
            collection=collection,
            dimension=self.embedder.dimension,
        )
        self.max_chars = max_chars
        self.overlap = overlap
        self.batch_size = batch_size

    def close(self) -> None:
        try:
            self.store.close()
        finally:
            self.manifest.close()

    def index_record(self, record: JudgmentRecord) -> dict[str, Any]:
        if not record.content:
            self.manifest.upsert_record(record, [])
            self.manifest.mark_pending_text(record.jid, "JFULLCONTENT 空白；需要下載 PDF 後抽取文字")
            return {"jid": record.jid, "status": "pending_text", "changed": False, "chunks": 0}
        chunks = chunk_judgment(record, max_chars=self.max_chars, overlap=self.overlap)
        changed = self.manifest.upsert_record(record, chunks)
        pending = self.manifest.pending_chunks(record.jid)
        if pending:
            # Remove every older or partially-written version before rebuilding.
            # A failed rebuild stays retryable because all manifest chunks are reset.
            self.store.delete_judgment(record.jid)
            self.manifest.reset_indexed(record.jid)
            pending = self.manifest.pending_chunks(record.jid)
            records = {record.jid: record}
            for start in range(0, len(pending), self.batch_size):
                batch = pending[start:start + self.batch_size]
                vectors = self.embedder.encode([f"{record.title}｜{c.section}｜{c.text}" for c in batch])
                if len(vectors) != len(batch):
                    raise JudgmentRagError("嵌入模型回傳的向量數與待索引切片數不一致")
                self.store.upsert(batch, records, vectors)
                self.manifest.set_indexed([c.chunk_id for c in batch])
        return {"jid": record.jid, "status": "indexed", "changed": changed, "chunks": len(chunks)}

    def remove_judgment(self, jid: str, error: str = "officially removed") -> None:
        """Scrub local plaintext immediately, then make vector deletion retryable."""
        self.manifest.mark_removal_pending(jid, error)
        try:
            self.store.delete_judgment(jid)
        except Exception as exc:
            self.manifest.mark_removal_pending(
                jid,
                error,
                cleanup_error=type(exc).__name__,
            )
            raise
        self.manifest.mark_removed(jid, error)

    async def sync_jids(self, client: OfficialJudicialClient, jids: Sequence[str]) -> dict[str, int]:
        stats = {"fetched": 0, "changed": 0, "removed": 0, "failed": 0}
        for jid in dict.fromkeys(_text(item) for item in jids if _text(item)):
            try:
                payload = await client.get_judgment(jid)
                stats["fetched"] += 1
                record = parse_jdoc(payload, jid_hint=jid)
                if record is None:
                    self.remove_judgment(
                        jid,
                        str(payload.get("error", "officially removed")),
                    )
                    stats["removed"] += 1
                    continue
                result = self.index_record(record)
                stats["changed"] += int(bool(result["changed"]))
            except Exception as exc:
                logger.exception("judgment sync failed: %s", jid)
                stats["failed"] += 1
                existing = self.manifest.conn.execute(
                    "SELECT status FROM judgments WHERE jid=?", (jid,),
                ).fetchone()
                if existing and str(existing["status"]) not in {"removed", "removal_pending"}:
                    self.manifest.conn.execute(
                        "UPDATE judgments SET error=?, updated_at=? WHERE jid=?",
                        (f"{type(exc).__name__}: {exc}", _now_iso(), jid),
                    )
                    self.manifest.conn.commit()
        return stats

    async def sync_changes(self, client: OfficialJudicialClient) -> dict[str, int]:
        change_days = await client.list_changes()
        jids: list[str] = []
        for day in change_days:
            if isinstance(day, dict):
                values = day.get("list", [])
                if isinstance(values, list):
                    jids.extend(_text(item) for item in values)
        return await self.sync_jids(client, jids)

    def import_jsonl(self, path: str) -> dict[str, int]:
        """匯入由官方 JDoc 回應組成的 JSONL，適合歷史批次 bootstrap。"""
        stats = {"fetched": 0, "changed": 0, "removed": 0, "failed": 0}
        with open(path, "r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                    if not isinstance(payload, dict):
                        raise ValueError("每列必須是 JSON object")
                    jid_hint = _text(payload.get("JID"))
                    record = parse_jdoc(payload, jid_hint=jid_hint)
                    if record is None:
                        if jid_hint:
                            self.remove_judgment(
                                jid_hint,
                                str(payload.get("error", "officially removed")),
                            )
                            stats["removed"] += 1
                        continue
                    stats["fetched"] += 1
                    result = self.index_record(record)
                    stats["changed"] += int(bool(result["changed"]))
                except Exception as exc:
                    logger.exception("JSONL line %d failed", line_no)
                    stats["failed"] += 1
        return stats

    def search(self, query: str, top_k: int = 8, *, jid: str = "", year: str = "") -> list[dict[str, Any]]:
        vector = self.embedder.encode([query])[0]
        return self.store.search(vector, top_k=top_k, jid=jid, year=year)

    def status(self) -> dict[str, Any]:
        result = self.manifest.stats()
        result["vector_points"] = self.store.count()
        result["collection"] = self.store.collection
        result["embedding_model"] = self.embedder.model_name
        result["embedding_dimension"] = self.embedder.dimension
        return result


def client_from_env() -> OfficialJudicialClient:
    return OfficialJudicialClient(
        username=os.getenv("JUDICIAL_API_USER", ""),
        password=os.getenv("JUDICIAL_API_PASSWORD", ""),
        base_url=os.getenv("JUDICIAL_API_BASE_URL", OFFICIAL_API_BASE),
        timeout=float(os.getenv("JUDICIAL_API_TIMEOUT", "60")),
    )


def index_from_env() -> JudgmentRagIndex:
    return JudgmentRagIndex(
        manifest_path=os.getenv("JUDGMENT_MANIFEST_PATH", DEFAULT_MANIFEST_PATH),
        qdrant_path=os.getenv("JUDGMENT_QDRANT_PATH", DEFAULT_QDRANT_PATH) or None,
        qdrant_host=os.getenv("JUDGMENT_QDRANT_HOST", "") or None,
        qdrant_port=int(os.getenv("JUDGMENT_QDRANT_PORT", "6333")),
        collection=os.getenv("JUDGMENT_QDRANT_COLLECTION", DEFAULT_COLLECTION),
        embed_model=os.getenv("JUDGMENT_EMBED_MODEL", DEFAULT_EMBED_MODEL),
        max_chars=int(os.getenv("JUDGMENT_CHUNK_MAX_CHARS", "800")),
        overlap=int(os.getenv("JUDGMENT_CHUNK_OVERLAP", "80")),
        batch_size=int(os.getenv("JUDGMENT_EMBED_BATCH_SIZE", "32")),
    )


__all__ = [
    "JudgmentRagError",
    "JudgmentRecord",
    "JudgmentChunk",
    "OfficialJudicialClient",
    "JudgmentManifest",
    "JudgmentRagIndex",
    "chunk_judgment",
    "extract_pdf_text",
    "parse_jdoc",
    "client_from_env",
    "index_from_env",
]


if __name__ == "__main__":
    raise SystemExit("請使用 zhiyan-judgment-rag CLI，而不是直接執行此模組。")
