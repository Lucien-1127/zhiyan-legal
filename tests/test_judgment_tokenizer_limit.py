"""Regressions for tokenizer-aware judgment embedding inputs."""
from __future__ import annotations

import sqlite3
from unittest.mock import patch

import pytest

pytest.importorskip("qdrant_client")

from zhiyan_legal import judgment_rag as rag


class TokenAwareEmbedder:
    dimension = 3
    model_name = "synthetic-tokenizer"
    model_revision = "rev-1"

    def __init__(self, max_tokens: int = 32) -> None:
        self.max_sequence_length = max_tokens
        self.inputs: list[str] = []

    @staticmethod
    def count_tokens(text: str) -> int:
        # Deterministic stand-in: two special tokens plus one token per char.
        return len(text) + 2

    def encode(self, texts):
        values = list(texts)
        assert all(self.count_tokens(text) <= self.max_sequence_length for text in values)
        self.inputs.extend(values)
        return [[1.0, 0.0, 0.0] for _ in values]


def record() -> rag.JudgmentRecord:
    return rag.JudgmentRecord(
        jid="SYNTHETIC-TOKEN-LIMIT-A",
        year="115",
        case_word="測試",
        case_number="1",
        judgment_date="20260917",
        title="合成案",
        full_type="text",
        content="理由\n\n" + "這是完整判決內容。" * 30,
    )


def open_index(tmp_path, embedder: TokenAwareEmbedder):
    with patch.object(rag, "LocalEmbeddingModel", return_value=embedder):
        return rag.JudgmentRagIndex(
            manifest_path=str(tmp_path / "manifest.sqlite3"),
            qdrant_path=str(tmp_path / "qdrant"),
            collection="token_limit_v1",
            embed_model=embedder.model_name,
            embed_model_revision=embedder.model_revision,
            max_chars=800,
            overlap=8,
            batch_size=4,
        )


def test_index_splits_using_exact_prefixed_embedding_input(tmp_path):
    embedder = TokenAwareEmbedder(max_tokens=32)
    index = open_index(tmp_path, embedder)
    try:
        result = index.index_record(record())
        assert result["chunks"] > 1
        assert embedder.inputs
        assert all(text.startswith("合成案｜") for text in embedder.inputs)
        assert all(embedder.count_tokens(text) <= 32 for text in embedder.inputs)
        assert index.status()["embedding_max_tokens"] == 32
        assert index.manifest.pending_chunks(record().jid) == []
    finally:
        index.close()


def test_prefix_that_leaves_no_text_budget_fails_before_manifest_write(tmp_path):
    embedder = TokenAwareEmbedder(max_tokens=8)
    index = open_index(tmp_path, embedder)
    try:
        with pytest.raises(rag.JudgmentRagError, match="前綴已占滿"):
            index.index_record(record())
        assert index.manifest.get_hash(record().jid) == ""
        assert index.store.count() == 0
    finally:
        index.close()


def test_local_embedder_rejects_oversized_input_before_model_encode():
    class Tokenizer:
        def __call__(self, text, **_kwargs):
            return {"input_ids": list(range(len(text) + 2))}

    class Model:
        tokenizer = Tokenizer()

        def encode(self, *_args, **_kwargs):
            raise AssertionError("oversized input must not reach model.encode")

    embedder = object.__new__(rag.LocalEmbeddingModel)
    embedder.model = Model()
    embedder.max_sequence_length = 5

    with pytest.raises(rag.JudgmentRagError, match="token 上限"):
        embedder.encode(["過長輸入"])


def test_existing_index_config_schema_gains_token_limit_column(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE index_config (
            singleton INTEGER PRIMARY KEY,
            fingerprint TEXT NOT NULL,
            collection TEXT NOT NULL,
            embedding_model TEXT NOT NULL,
            embedding_model_revision TEXT NOT NULL DEFAULT '',
            embedding_dimension INTEGER NOT NULL,
            chunk_max_chars INTEGER NOT NULL,
            chunk_overlap INTEGER NOT NULL,
            input_template_version TEXT NOT NULL,
            fingerprint_version INTEGER NOT NULL,
            state TEXT NOT NULL DEFAULT 'ready',
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()

    manifest = rag.JudgmentManifest(str(path))
    try:
        columns = {
            row[1] for row in manifest.conn.execute("PRAGMA table_info(index_config)")
        }
        assert "embedding_max_tokens" in columns
    finally:
        manifest.close()
