"""Source URL propagation regressions for judgment sync and vector metadata."""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from zhiyan_legal import judgment_rag as rag


JID = "SYNTHETIC-SOURCE,115,測試,1,20260918,1"


def payload() -> dict:
    return {
        "JID": JID,
        "JYEAR": "115",
        "JCASE": "測試",
        "JNO": "1",
        "JDATE": "20260918",
        "JTITLE": "合成判決：來源定位",
        "JFULLX": {
            "JFULLTYPE": "text",
            "JFULLCONTENT": "主文\n\n本資料只用於來源網址測試。",
        },
    }


def open_index(tmp_path: Path):
    embedder = Mock(dimension=3, model_name="synthetic", model_revision="rev-1")
    embedder.encode.side_effect = lambda texts: [[1.0, 0.0, 0.0] for _ in texts]
    store = Mock(collection="source_url_test")
    store.count.return_value = 0
    with patch.object(rag, "LocalEmbeddingModel", return_value=embedder), \
            patch.object(rag, "JudgmentVectorStore", return_value=store):
        index = rag.JudgmentRagIndex(
            manifest_path=str(tmp_path / "manifest.sqlite3"),
            collection="source_url_test",
        )
    return index, embedder, store


def test_parse_jdoc_uses_explicit_source_base_without_double_slash():
    record = rag.parse_jdoc(
        payload(),
        source_base_url="https://judicial-proxy.example/jdg/api/",
    )
    assert record is not None
    assert record.source_url == "https://judicial-proxy.example/jdg/api/JDoc"


def test_sync_persists_configured_api_base_in_sqlite_and_vector_payload(tmp_path):
    index, _embedder, store = open_index(tmp_path)
    client = Mock(base_url="https://judicial-proxy.example/jdg/api/")
    client.get_judgment = AsyncMock(return_value=payload())
    try:
        result = asyncio.run(index.sync_jids(client, [JID]))
        assert result == {"fetched": 1, "changed": 1, "removed": 0, "failed": 0}
        row = index.manifest.conn.execute(
            "SELECT source_url FROM judgments WHERE jid=?", (JID,),
        ).fetchone()
        assert row["source_url"] == "https://judicial-proxy.example/jdg/api/JDoc"
        indexed_record = store.upsert.call_args.args[1][JID]
        assert indexed_record.source_url == row["source_url"]
    finally:
        index.close()


def test_source_change_republishes_unchanged_content_metadata(tmp_path):
    index, embedder, store = open_index(tmp_path)
    client = Mock(base_url="https://old-proxy.example/jdg/api")
    client.get_judgment = AsyncMock(return_value=payload())
    try:
        assert asyncio.run(index.sync_jids(client, [JID]))["changed"] == 1
        store.reset_mock()
        embedder.reset_mock()

        client.base_url = "https://new-proxy.example/jdg/api"
        result = asyncio.run(index.sync_jids(client, [JID]))

        assert result["changed"] == 1
        store.delete_judgment.assert_called_once_with(JID)
        store.upsert.assert_called_once()
        indexed_record = store.upsert.call_args.args[1][JID]
        assert indexed_record.source_url == "https://new-proxy.example/jdg/api/JDoc"
    finally:
        index.close()
