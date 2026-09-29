"""API failure regressions: real SQLite, fake API/embedding/vector store."""
from __future__ import annotations

import asyncio
import io
import json
import logging
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import AsyncMock, Mock, patch

from zhiyan_legal import judgment_rag as rag


JID = "TEST,110,訴,123,20210831,1"
API_ERROR = "服務暫停 synthetic-response-marker"


def payload(jid: str = JID) -> dict:
    return {
        "JID": jid, "JYEAR": "110", "JCASE": "訴", "JNO": "123",
        "JDATE": "20210831", "JTITLE": "測試用判決（非真實資料）",
        "JFULLX": {"JFULLTYPE": "text", "JFULLCONTENT": "主文\n\n測試全文。"},
    }


class JudgmentApiErrorsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.embedder = Mock(dimension=2)
        self.embedder.encode.side_effect = lambda texts: [[1.0, 0.0] for _ in texts]
        self.store = Mock()
        with patch.object(rag, "LocalEmbeddingModel", return_value=self.embedder), \
                patch.object(rag, "JudgmentVectorStore", return_value=self.store):
            self.index = rag.JudgmentRagIndex(
                manifest_path=str(Path(self.temp.name) / "manifest.sqlite3"),
            )
        self.addCleanup(self.index.close)
        # Capture expected failures, without suppressing production error handling.
        self.logs = io.StringIO()
        handler = logging.StreamHandler(self.logs)
        old_propagate = rag.logger.propagate
        rag.logger.propagate = False
        rag.logger.addHandler(handler)
        self.addCleanup(setattr, rag.logger, "propagate", old_propagate)
        self.addCleanup(rag.logger.removeHandler, handler)

    def seed(self) -> None:
        self.index.index_record(rag.parse_jdoc(payload()))
        self.store.reset_mock()
        self.embedder.reset_mock()

    def row(self) -> dict | None:
        row = self.index.manifest.conn.execute(
            "SELECT * FROM judgments WHERE jid=?", (JID,),
        ).fetchone()
        return dict(row) if row else None

    def chunks(self) -> list:
        return [tuple(row) for row in self.index.manifest.conn.execute(
            "SELECT * FROM chunks WHERE jid=? ORDER BY sequence", (JID,),
        )]

    def sync(self, response: dict) -> dict:
        client = Mock()
        client.get_judgment = AsyncMock(return_value=response)
        return asyncio.run(self.index.sync_jids(client, [JID]))

    def assert_no_index_mutation(self) -> None:
        self.embedder.encode.assert_not_called()
        self.store.upsert.assert_not_called()
        self.store.delete_judgment.assert_not_called()

    def test_non_removal_errors_raise_even_with_valid_document_fields(self) -> None:
        for error in ("驗證失敗", "超出流量限制", API_ERROR, 503):
            for response in ({"error": error}, {**payload(), "error": error}):
                with self.subTest(error=error, has_document="JID" in response):
                    with self.assertRaises(rag.JudgmentRagError) as caught:
                        rag.parse_jdoc(response, jid_hint=JID)
                    self.assertNotIn(str(error), str(caught.exception))

    def test_successful_payloads_with_empty_error_remain_supported(self) -> None:
        for error in (None, "", "  "):
            with self.subTest(error=error):
                record = rag.parse_jdoc({**payload(), "error": error})
                self.assertEqual(record.content, "主文\n\n測試全文。")
        self.assertEqual(rag.parse_jdoc(payload()).jid, JID)

    def test_known_removal_responses_remain_removed(self) -> None:
        for error in ("查無資料，本裁判可能已從系統移除", "不再公開", "未公開"):
            with self.subTest(error=error):
                self.assertIsNone(rag.parse_jdoc({"error": error}, jid_hint=JID))

    def test_existing_judgment_and_index_survive_error(self) -> None:
        self.seed()
        before, chunks = self.row(), self.chunks()
        stats = self.sync({"error": API_ERROR})
        self.assertEqual(stats, {"fetched": 1, "changed": 0, "removed": 0, "failed": 1})
        after = self.row()
        for key, value in before.items():
            if key not in ("error", "updated_at"):
                self.assertEqual(after[key], value, key)
        self.assertIn("JudgmentRagError", after["error"])
        self.assertEqual(self.chunks(), chunks)
        self.assert_no_index_mutation()
        self.assertNotIn(API_ERROR, after["error"])
        self.assertNotIn(API_ERROR, self.logs.getvalue())

    def test_new_jid_error_does_not_create_empty_pending_record(self) -> None:
        self.assertEqual(self.sync({"error": API_ERROR})["failed"], 1)
        self.assertIsNone(self.row())
        self.assertEqual(self.chunks(), [])
        self.assert_no_index_mutation()

    def test_removed_judgment_is_not_reactivated_by_api_error(self) -> None:
        self.seed()
        self.index.manifest.mark_removed(JID)
        before = self.row()
        self.assertEqual(self.sync({"error": API_ERROR})["failed"], 1)
        after = self.row()
        for key in ("status", "removed_at", "content", "content_hash"):
            self.assertEqual(after[key], before[key], key)
        self.assertEqual(after["status"], "removed")
        self.assertEqual(self.chunks(), [])
        self.assert_no_index_mutation()

    def test_valid_retry_after_api_error_preserves_existing_index(self) -> None:
        self.seed()
        before = self.chunks()
        self.assertEqual(self.sync({"error": API_ERROR})["failed"], 1)
        self.assertEqual(self.sync(payload()),
                         {"fetched": 1, "changed": 0, "removed": 0, "failed": 0})
        self.assertEqual(self.row()["status"], "active")
        self.assertEqual(self.row()["error"], "")
        self.assertEqual(self.chunks(), before)
        self.assert_no_index_mutation()

    def test_jsonl_error_preserves_record_and_continues_to_valid_line(self) -> None:
        self.seed()
        before, chunks = self.row(), self.chunks()
        path = Path(self.temp.name) / "errors.jsonl"
        # Test-generated synthetic fixtures only; never actual judicial documents.
        path.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in (
            {"JID": JID, "error": API_ERROR}, payload("TEST-NEXT"),
        )) + "\n", encoding="utf-8")
        self.assertEqual(self.index.import_jsonl(str(path)),
                         {"fetched": 1, "changed": 1, "removed": 0, "failed": 1})
        self.assertEqual(self.row(), before)
        self.assertEqual(self.chunks(), chunks)
        self.store.upsert.assert_called_once()
        indexed_records = self.store.upsert.call_args.args[1]
        self.assertEqual(set(indexed_records), {"TEST-NEXT"})
        self.store.delete_judgment.assert_called_once_with("TEST-NEXT")
        self.assertNotIn(API_ERROR, self.logs.getvalue())

    def test_official_removal_still_deletes_vector_points(self) -> None:
        self.seed()
        self.assertEqual(self.sync({"error": "查無資料，本裁判可能已從系統移除"}),
                         {"fetched": 1, "changed": 0, "removed": 1, "failed": 0})
        self.assertEqual(self.row()["status"], "removed")
        self.assertEqual(self.chunks(), [])
        self.store.delete_judgment.assert_called_once_with(JID)
        self.embedder.encode.assert_not_called()
        self.store.upsert.assert_not_called()


if __name__ == "__main__":
    unittest.main()
