"""Real on-disk Qdrant + SQLite, synthetic judgments and fixed test vectors.

Run explicitly with qdrant-client installed; no model download or API credentials.
Injected failures exercise client-call boundaries, not a remote server outage.
"""
from dataclasses import replace
import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

pytest.importorskip("qdrant_client")

from zhiyan_legal import judgment_rag as rag
from zhiyan_legal.judgment_answer import build_judgment_research_context


def record(text="合成測試內容。", jid="SYNTHETIC-JUDGMENT-A"):
    return rag.JudgmentRecord(
        jid=jid, year="115", case_word="測試", case_number="0",
        judgment_date="20260914", title="合成判決：非真實法律資料",
        full_type="text", content=text,
        source_url="https://data.judicial.gov.tw/jdg/api/JDoc",
    )


@pytest.fixture
def open_index(tmp_path):
    indexes = []

    def create():
        embedder = Mock(dimension=3)
        embedder.encode.side_effect = lambda texts: [[1.0, 0.0, 0.0] for _ in texts]
        with patch.object(rag, "LocalEmbeddingModel", return_value=embedder):
            index = rag.JudgmentRagIndex(
                manifest_path=str(tmp_path / "manifest.sqlite3"),
                qdrant_path=str(tmp_path / "qdrant"),
                collection="synthetic_judgments", max_chars=100, overlap=10,
                batch_size=2,
            )
        indexes.append(index)
        return index

    yield create
    # Direct client cleanup also prevents a baseline failure from leaking its lock.
    for index in reversed(indexes):
        try:
            index.store.client.close()
        finally:
            index.manifest.close()


def assert_complete(index, expected):
    chunks = rag.chunk_judgment(expected, max_chars=100, overlap=10)
    # Check all stored payloads, not only the nearest search result.
    points, cursor = index.store.client.scroll(
        collection_name=index.store.collection, limit=1000, with_payload=True,
    )
    assert cursor is None
    own = [p for p in points if p.payload["jid"] == expected.jid]
    assert {str(p.id) for p in own} == {c.chunk_id for c in chunks}
    assert {p.payload["content_hash"] for p in own} == {expected.content_hash}
    assert {p.payload["text"] for p in own} == {c.text for c in chunks}
    hits = index.store.search([1.0, 0.0, 0.0], top_k=1000, jid=expected.jid)
    assert {h["id"] for h in hits} == {c.chunk_id for c in chunks}
    assert index.manifest.pending_chunks(expected.jid) == []


def test_update_removes_old_version_but_preserves_other_jid(open_index):
    index = open_index()
    old = record("舊版合成段落。" * 40)
    other = record(jid="SYNTHETIC-JUDGMENT-B")
    index.index_record(old)
    index.index_record(other)
    new = replace(old, content="新版更短的合成判決。")
    index.index_record(new)
    assert_complete(index, new)
    assert_complete(index, other)
    with patch.object(index.store, "delete_judgment", wraps=index.store.delete_judgment) as delete:
        assert index.index_record(new)["changed"] is False
        delete.assert_not_called()


def test_failed_delete_leaves_old_points_and_retry_rebuilds(open_index):
    index = open_index()
    old = record("舊版合成段落。" * 40)
    new = replace(old, content="新的合成判決全文。")
    index.index_record(old)
    with patch.object(index.store.client, "delete", side_effect=RuntimeError("synthetic delete failure")), \
            patch.object(index.store.client, "upsert", wraps=index.store.client.upsert) as upsert:
        with pytest.raises(RuntimeError, match="synthetic delete failure"):
            index.index_record(new)
        upsert.assert_not_called()
    hits = index.store.search([1.0, 0.0, 0.0], top_k=1000, jid=old.jid)
    assert {h["content_hash"] for h in hits} == {old.content_hash}
    assert index.manifest.pending_chunks(new.jid)
    index.index_record(new)
    assert_complete(index, new)


def test_partial_write_then_error_recovers_after_reopen(open_index):
    index = open_index()
    old = record()
    new = replace(old, content="新版合成長段落。" * 100)
    index.index_record(old)
    original_upsert = index.store.client.upsert
    calls = 0

    def apply_then_fail(**kwargs):
        nonlocal calls
        calls += 1
        result = original_upsert(**kwargs)
        if calls == 2:
            # Data was applied, but its acknowledgment never reached the manifest.
            raise RuntimeError("synthetic lost acknowledgment")
        return result

    with patch.object(index.store.client, "upsert", side_effect=apply_then_fail):
        with pytest.raises(RuntimeError, match="synthetic lost acknowledgment"):
            index.index_record(new)
    assert index.store.count() == 4
    assert index.manifest.pending_chunks(new.jid)
    index.close()
    resumed = open_index()
    resumed.index_record(new)
    assert_complete(resumed, new)


def test_close_releases_directory_and_persists_searchable_index(open_index):
    index = open_index()
    expected = record()
    index.index_record(expected)
    index.close()
    index.close()
    reopened = open_index()
    assert_complete(reopened, expected)


def test_real_local_qdrant_hit_enters_canonical_answer_context(open_index):
    index = open_index()
    expected = record("可核對的合成判決原文。")
    index.index_record(expected)

    hits = index.search("合成判決", top_k=3)
    context = build_judgment_research_context(
        "合成判決",
        hits,
        execution_id="local-qdrant-answer",
    )

    assert hits and hits[0]["jid"] == expected.jid
    assert context.citations[0].exact_quote == hits[0]["text"]
    assert context.evidence[0].title == expected.title
    assert expected.jid in context.citations[0].locator


def test_official_removal_failure_scrubs_sqlite_then_real_qdrant_retry(open_index):
    index = open_index()
    expected = record("撤下前的合成全文。")
    index.index_record(expected)
    client = Mock()
    client.get_judgment = AsyncMock(
        return_value={"error": "查無資料，本裁判可能已從系統移除"}
    )
    with patch.object(
        index.store.client, "delete",
        side_effect=RuntimeError("synthetic delete failure"),
    ):
        failed = asyncio.run(index.sync_jids(client, [expected.jid]))
    assert failed["failed"] == 1
    assert failed["removed"] == 0
    tombstone = dict(index.manifest.conn.execute(
        "SELECT * FROM judgments WHERE jid=?", (expected.jid,),
    ).fetchone())
    assert tombstone["status"] == "removal_pending"
    assert tombstone["content"] == ""
    assert tombstone["content_hash"] == ""
    assert index.store.search(
        [1.0, 0.0, 0.0], top_k=10, jid=expected.jid,
    )

    removed = asyncio.run(index.sync_jids(client, [expected.jid]))
    assert removed == {"fetched": 1, "changed": 0, "removed": 1, "failed": 0}
    assert index.store.search(
        [1.0, 0.0, 0.0], top_k=10, jid=expected.jid,
    ) == []
    final = dict(index.manifest.conn.execute(
        "SELECT * FROM judgments WHERE jid=?", (expected.jid,),
    ).fetchone())
    assert final["status"] == "removed"
    assert final["content"] == ""
