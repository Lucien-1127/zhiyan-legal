"""Removal tombstone regressions with real SQLite and mocked vector storage."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from zhiyan_legal import judgment_rag as rag


JID = "SYNTHETIC-REMOVED-JUDGMENT"
REMOVAL = "查無資料，本裁判可能已從系統移除"


def payload() -> dict:
    return {
        "JID": JID, "JYEAR": "115", "JCASE": "測試", "JNO": "0",
        "JDATE": "20260915", "JTITLE": "合成判決：非真實法律資料",
        "JFULLX": {
            "JFULLTYPE": "text", "JFULLCONTENT": "主文\n\n合成全文。",
            "JFULLPDF": "https://example.invalid/synthetic.pdf",
        },
    }


def make_index(tmp_path: Path):
    embedder = Mock(dimension=3, model_name="synthetic")
    embedder.encode.side_effect = lambda texts: [[1.0, 0.0, 0.0] for _ in texts]
    store = Mock(collection="synthetic")
    with patch.object(rag, "LocalEmbeddingModel", return_value=embedder), \
            patch.object(rag, "JudgmentVectorStore", return_value=store):
        index = rag.JudgmentRagIndex(manifest_path=str(tmp_path / "manifest.sqlite3"))
    return index, store


def row(index) -> dict:
    result = index.manifest.conn.execute(
        "SELECT * FROM judgments WHERE jid=?", (JID,),
    ).fetchone()
    assert result is not None
    return dict(result)


def sync(index, response: dict) -> dict:
    client = Mock()
    client.get_judgment = AsyncMock(return_value=response)
    return asyncio.run(index.sync_jids(client, [JID]))


def assert_scrubbed(index, expected_status: str) -> None:
    result = row(index)
    assert result["jid"] == JID
    assert result["status"] == expected_status
    assert result["removed_at"]
    assert result["updated_at"]
    assert REMOVAL in result["error"]
    for key in (
        "year", "case_word", "case_number", "judgment_date", "title",
        "full_type", "content", "content_hash", "pdf_url", "source_url",
    ):
        assert result[key] == "", key
    assert index.manifest.conn.execute(
        "SELECT COUNT(*) FROM chunks WHERE jid=?", (JID,),
    ).fetchone()[0] == 0


def test_mark_removed_scrubs_fulltext_metadata_and_keeps_audit(tmp_path):
    index, _ = make_index(tmp_path)
    try:
        index.index_record(rag.parse_jdoc(payload()))
        index.manifest.mark_removed(JID, REMOVAL)
        assert_scrubbed(index, "removed")
    finally:
        index.close()


def test_unknown_removed_jid_creates_audit_tombstone(tmp_path):
    index, _ = make_index(tmp_path)
    try:
        index.manifest.mark_removed(JID, REMOVAL)
        assert_scrubbed(index, "removed")
    finally:
        index.close()


def test_vector_delete_failure_is_pending_and_retryable(tmp_path):
    index, store = make_index(tmp_path)
    try:
        index.index_record(rag.parse_jdoc(payload()))
        store.reset_mock()
        store.delete_judgment.side_effect = RuntimeError("synthetic delete failure")
        assert sync(index, {"error": REMOVAL}) == {
            "fetched": 1, "changed": 0, "removed": 0, "failed": 1,
        }
        assert_scrubbed(index, "removal_pending")
        assert "RuntimeError" in row(index)["error"]
        store.upsert.assert_not_called()

        store.delete_judgment.side_effect = None
        assert sync(index, {"error": REMOVAL}) == {
            "fetched": 1, "changed": 0, "removed": 1, "failed": 0,
        }
        assert_scrubbed(index, "removed")
        assert store.delete_judgment.call_count == 2
    finally:
        index.close()


def test_valid_payload_restores_pending_removal_and_reindexes(tmp_path):
    index, store = make_index(tmp_path)
    try:
        index.index_record(rag.parse_jdoc(payload()))
        store.reset_mock()
        store.delete_judgment.side_effect = RuntimeError("synthetic delete failure")
        assert sync(index, {"error": REMOVAL})["failed"] == 1
        assert_scrubbed(index, "removal_pending")

        store.delete_judgment.side_effect = None
        assert sync(index, payload()) == {
            "fetched": 1, "changed": 1, "removed": 0, "failed": 0,
        }
        restored = row(index)
        assert restored["status"] == "active"
        assert restored["content"] == "主文\n\n合成全文。"
        assert restored["content_hash"]
        assert restored["removed_at"] == ""
        assert store.upsert.called
    finally:
        index.close()


def test_jsonl_unknown_removal_creates_tombstone_and_retries(tmp_path):
    index, store = make_index(tmp_path)
    source = tmp_path / "synthetic-removal.jsonl"
    source.write_text(
        json.dumps({"JID": JID, "error": REMOVAL}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    try:
        store.delete_judgment.side_effect = RuntimeError("synthetic delete failure")
        assert index.import_jsonl(str(source)) == {
            "fetched": 0, "changed": 0, "removed": 0, "failed": 1,
        }
        assert_scrubbed(index, "removal_pending")

        store.delete_judgment.side_effect = None
        assert index.import_jsonl(str(source)) == {
            "fetched": 0, "changed": 0, "removed": 1, "failed": 0,
        }
        assert_scrubbed(index, "removed")
    finally:
        index.close()
