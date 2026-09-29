"""Index recovery regressions using real SQLite and fake vector components."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, call, patch

from zhiyan_legal import judgment_rag as rag


JID = "TEST,110,訴,123,20210831,1"


def record(content: str = "主文\n\n" + "甲" * 240) -> rag.JudgmentRecord:
    return rag.JudgmentRecord(
        jid=JID,
        year="110",
        case_word="訴",
        case_number="123",
        judgment_date="20210831",
        title="測試用判決（非真實資料）",
        full_type="text",
        content=content,
        source_url="https://example.invalid/JDoc",
        retrieved_at="2026-09-11T00:00:00+00:00",
    )


class JudgmentIndexRecoveryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.embedder = Mock(dimension=2, model_name="synthetic")
        self.embedder.encode.side_effect = self.vectors
        self.store = Mock(collection="synthetic")
        with patch.object(rag, "LocalEmbeddingModel", return_value=self.embedder), \
                patch.object(rag, "JudgmentVectorStore", return_value=self.store):
            self.index = rag.JudgmentRagIndex(
                manifest_path=str(Path(self.temp.name) / "manifest.sqlite3"),
                max_chars=100,
                overlap=10,
                batch_size=1,
            )
        self.addCleanup(self.index.close)

    @staticmethod
    def vectors(texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]

    def counts(self) -> tuple[int, int]:
        row = self.index.manifest.conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(indexed), 0) FROM chunks WHERE jid=?",
            (JID,),
        ).fetchone()
        return int(row[0]), int(row[1])

    def status(self) -> str:
        return str(self.index.manifest.conn.execute(
            "SELECT status FROM judgments WHERE jid=?", (JID,),
        ).fetchone()[0])

    def test_embedding_failure_is_retryable(self) -> None:
        self.embedder.encode.side_effect = RuntimeError("synthetic embedding failure")
        with self.assertRaisesRegex(RuntimeError, "synthetic embedding failure"):
            self.index.index_record(record())
        total, indexed = self.counts()
        self.assertGreater(total, 0)
        self.assertEqual(indexed, 0)

        self.embedder.encode.side_effect = self.vectors
        result = self.index.index_record(record())
        self.assertFalse(result["changed"])
        self.assertEqual(result["status"], "indexed")
        self.assertEqual(self.counts(), (total, total))
        self.assertEqual(self.store.upsert.call_count, total)

    def test_partial_vector_failure_restarts_whole_judgment(self) -> None:
        self.store.upsert.side_effect = [None, RuntimeError("synthetic qdrant failure")]
        with self.assertRaisesRegex(RuntimeError, "synthetic qdrant failure"):
            self.index.index_record(record())
        total, indexed = self.counts()
        self.assertGreater(total, 1)
        self.assertEqual(indexed, 1)
        confirmed_id = self.store.upsert.call_args_list[0].args[0][0].chunk_id

        self.store.upsert.side_effect = None
        calls_before_retry = len(self.store.upsert.call_args_list)
        result = self.index.index_record(record())
        retried_ids = [
            call.args[0][0].chunk_id
            for call in self.store.upsert.call_args_list[calls_before_retry:]
        ]
        self.assertFalse(result["changed"])
        self.assertIn(confirmed_id, retried_ids)
        self.assertEqual(len(retried_ids), total)
        self.assertEqual(self.counts(), (total, total))
        self.assertEqual(self.store.delete_judgment.call_count, 2)

    def test_removed_same_hash_is_rebuilt_and_reindexed(self) -> None:
        first = self.index.index_record(record())
        total = first["chunks"]
        self.index.manifest.mark_removed(JID)
        self.assertEqual(self.counts(), (0, 0))
        self.embedder.reset_mock()
        self.store.reset_mock()
        self.embedder.encode.side_effect = self.vectors

        restored = self.index.index_record(record())
        self.assertTrue(restored["changed"])
        self.assertEqual(restored["status"], "indexed")
        self.assertEqual(self.status(), "active")
        self.assertEqual(self.counts(), (total, total))
        self.assertEqual(self.store.upsert.call_count, total)

    def test_legacy_active_row_without_chunks_is_repaired(self) -> None:
        first = self.index.index_record(record())
        total = first["chunks"]
        self.index.manifest.conn.execute("DELETE FROM chunks WHERE jid=?", (JID,))
        self.index.manifest.conn.commit()
        self.assertEqual(self.status(), "active")
        self.assertEqual(self.counts(), (0, 0))
        self.embedder.reset_mock()
        self.store.reset_mock()
        self.embedder.encode.side_effect = self.vectors

        repaired = self.index.index_record(record())
        self.assertTrue(repaired["changed"])
        self.assertEqual(repaired["status"], "indexed")
        self.assertEqual(self.counts(), (total, total))
        self.assertEqual(self.store.upsert.call_count, total)

    def test_fully_indexed_unchanged_record_is_not_reembedded(self) -> None:
        self.index.index_record(record())
        before = self.counts()
        self.embedder.reset_mock()
        self.store.reset_mock()
        result = self.index.index_record(record())
        self.assertFalse(result["changed"])
        self.assertEqual(self.counts(), before)
        self.embedder.encode.assert_not_called()
        self.store.upsert.assert_not_called()
        self.store.delete_judgment.assert_not_called()

    def test_changed_content_is_deleted_before_first_new_upsert(self) -> None:
        self.index.index_record(record("主文\n\n舊版本"))
        self.store.reset_mock()
        updated = record("主文\n\n" + "新版本" * 45)
        result = self.index.index_record(updated)
        self.assertTrue(result["changed"])
        self.assertEqual(self.store.mock_calls[0], call.delete_judgment(JID))
        self.assertEqual(self.store.delete_judgment.call_count, 1)
        self.assertGreater(self.store.upsert.call_count, 0)
        for upsert_call in self.store.upsert.call_args_list:
            chunks = upsert_call.args[0]
            self.assertTrue(all(chunk.content_hash == updated.content_hash for chunk in chunks))

    def test_delete_failure_does_not_write_new_vectors_and_is_retryable(self) -> None:
        self.index.index_record(record("主文\n\n舊版本"))
        self.store.reset_mock()
        updated = record("理由\n\n" + "新內容" * 45)
        self.store.delete_judgment.side_effect = RuntimeError("synthetic delete failure")
        with self.assertRaisesRegex(RuntimeError, "synthetic delete failure"):
            self.index.index_record(updated)
        total, indexed = self.counts()
        self.assertGreater(total, 0)
        self.assertEqual(indexed, 0)
        self.store.upsert.assert_not_called()

        self.store.delete_judgment.side_effect = None
        result = self.index.index_record(updated)
        self.assertFalse(result["changed"])
        self.assertEqual(self.counts(), (total, total))
        self.assertGreater(self.store.upsert.call_count, 0)

    def test_wrong_vector_count_stays_pending_for_retry(self) -> None:
        self.embedder.encode.side_effect = lambda texts: []
        with self.assertRaises(rag.JudgmentRagError):
            self.index.index_record(record("理由\n\n" + "乙" * 120))
        total, indexed = self.counts()
        self.assertGreater(total, 0)
        self.assertEqual(indexed, 0)
        self.store.upsert.assert_not_called()

        self.embedder.encode.side_effect = self.vectors
        result = self.index.index_record(record("理由\n\n" + "乙" * 120))
        self.assertFalse(result["changed"])
        self.assertEqual(self.counts(), (total, total))


if __name__ == "__main__":
    unittest.main()
