"""Index fingerprint and explicit collection rebuild regressions."""
from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

pytest.importorskip("qdrant_client")

from zhiyan_legal import judgment_rag as rag


def record(jid: str = "SYNTHETIC-FINGERPRINT-A") -> rag.JudgmentRecord:
    return rag.JudgmentRecord(
        jid=jid,
        year="115",
        case_word="測試",
        case_number="0",
        judgment_date="20260916",
        title="合成判決：索引指紋測試",
        full_type="text",
        content="主文\n\n合成內容。\n\n理由\n\n索引設定必須一致。",
    )


def open_index(tmp_path, *, collection="fingerprint_v1", model="model-a",
               revision="rev-a", dimension=3, max_chars=100, overlap=10,
               allow_rebuild=False):
    embedder = Mock(
        dimension=dimension,
        model_name=model,
        model_revision=revision,
    )
    embedder.encode.side_effect = lambda texts: [
        [1.0] + [0.0] * (dimension - 1) for _ in texts
    ]
    with patch.object(rag, "LocalEmbeddingModel", return_value=embedder):
        return rag.JudgmentRagIndex(
            manifest_path=str(tmp_path / "manifest.sqlite3"),
            qdrant_path=str(tmp_path / "qdrant"),
            collection=collection,
            embed_model=model,
            embed_model_revision=revision,
            max_chars=max_chars,
            overlap=overlap,
            batch_size=2,
            allow_rebuild=allow_rebuild,
        )


def test_initial_fingerprint_is_stable_and_visible_in_status(tmp_path):
    first = open_index(tmp_path)
    try:
        first.index_record(record())
        status = first.status()
        assert status["index_state"] == "ready"
        assert status["index_fingerprint"]
        assert status["embedding_model_revision"] == "rev-a"
        fingerprint = status["index_fingerprint"]
    finally:
        first.close()

    reopened = open_index(tmp_path)
    try:
        assert reopened.status()["index_fingerprint"] == fingerprint
        assert reopened.manifest.pending_chunks(record().jid) == []
    finally:
        reopened.close()


@pytest.mark.parametrize(
    ("overrides", "label"),
    [
        ({"model": "model-b"}, "embedding_model"),
        ({"revision": "rev-b"}, "embedding_model_revision"),
        ({"dimension": 4}, "embedding_dimension"),
        ({"max_chars": 80}, "chunk_max_chars"),
        ({"overlap": 5}, "chunk_overlap"),
    ],
)
def test_changed_semantics_rejected_in_same_collection(tmp_path, overrides, label):
    first = open_index(tmp_path)
    try:
        first.index_record(record())
    finally:
        first.close()

    with pytest.raises(rag.JudgmentRagError) as caught:
        open_index(tmp_path, **overrides)
    message = str(caught.value)
    assert label in message
    assert "新的 Qdrant collection" in message

    # A failed open must release embedded Qdrant and leave the prior index usable.
    reopened = open_index(tmp_path)
    try:
        assert reopened.store.count() > 0
        assert reopened.status()["index_state"] == "ready"
    finally:
        reopened.close()


def test_new_collection_requires_explicit_rebuild_and_reindexes_manifest(tmp_path):
    first = open_index(tmp_path)
    expected = record()
    try:
        first.index_record(expected)
        old_fingerprint = first.status()["index_fingerprint"]
    finally:
        first.close()

    with pytest.raises(rag.JudgmentRagError, match="rebuild-index"):
        open_index(
            tmp_path,
            collection="fingerprint_v2",
            model="model-b",
            revision="rev-b",
        )

    rebuilding = open_index(
        tmp_path,
        collection="fingerprint_v2",
        model="model-b",
        revision="rev-b",
        allow_rebuild=True,
    )
    try:
        assert rebuilding.status()["index_state"] == "rebuild_pending"
        assert rebuilding.manifest.pending_chunks(expected.jid) == []
        result = rebuilding.rebuild_index()
        assert result["judgments"] == 1
        assert result["chunks"] > 0
        status = rebuilding.status()
        assert status["index_state"] == "ready"
        assert status["index_fingerprint"] != old_fingerprint
        assert status["collection"] == "fingerprint_v2"
        assert rebuilding.store.count() == result["chunks"]
        assert rebuilding.manifest.pending_chunks(expected.jid) == []
    finally:
        rebuilding.close()


def test_nonempty_target_collection_is_not_adopted_for_rebuild(tmp_path):
    first = open_index(tmp_path)
    try:
        first.index_record(record())
    finally:
        first.close()

    seeded = open_index(
        tmp_path,
        collection="fingerprint_v2",
        model="model-b",
        revision="rev-b",
        allow_rebuild=True,
    )
    try:
        seeded.rebuild_index()
    finally:
        seeded.close()

    # Move the manifest to v3 while the old v2 collection remains populated.
    back = open_index(
        tmp_path,
        collection="fingerprint_v3",
        allow_rebuild=True,
    )
    try:
        back.rebuild_index()
    finally:
        back.close()

    with pytest.raises(rag.JudgmentRagError, match="不是空集合"):
        open_index(
            tmp_path,
            collection="fingerprint_v2",
            model="model-b",
            revision="rev-b",
            allow_rebuild=True,
        )


def test_legacy_manifest_with_empty_collection_requires_rebuild(tmp_path):
    manifest = rag.JudgmentManifest(str(tmp_path / "manifest.sqlite3"))
    expected = record()
    chunks = rag.chunk_judgment(expected, max_chars=100, overlap=10)
    try:
        manifest.upsert_record(expected, chunks)
        manifest.set_indexed([chunk.chunk_id for chunk in chunks])
        assert manifest.get_index_config() is None
    finally:
        manifest.close()

    with pytest.raises(rag.JudgmentRagError, match="rebuild-index"):
        open_index(tmp_path)

    rebuilding = open_index(tmp_path, allow_rebuild=True)
    try:
        assert rebuilding.status()["index_state"] == "rebuild_pending"
        result = rebuilding.rebuild_index()
        assert result["judgments"] == 1
        assert rebuilding.status()["index_state"] == "ready"
    finally:
        rebuilding.close()


def test_interrupted_collection_rebuild_is_retryable_after_reopen(tmp_path):
    first = open_index(tmp_path)
    try:
        first.index_record(record())
    finally:
        first.close()

    rebuilding = open_index(
        tmp_path,
        collection="fingerprint_v2",
        allow_rebuild=True,
    )
    try:
        rebuilding.embedder.encode.side_effect = RuntimeError("synthetic rebuild failure")
        with pytest.raises(RuntimeError, match="synthetic rebuild failure"):
            rebuilding.rebuild_index()
        assert rebuilding.status()["index_state"] == "rebuild_pending"
    finally:
        rebuilding.close()

    resumed = open_index(
        tmp_path,
        collection="fingerprint_v2",
        allow_rebuild=True,
    )
    try:
        assert resumed.status()["index_state"] == "rebuild_pending"
        result = resumed.rebuild_index()
        assert result["judgments"] == 1
        assert resumed.status()["index_state"] == "ready"
    finally:
        resumed.close()
