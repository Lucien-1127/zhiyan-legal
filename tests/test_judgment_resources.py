"""Resource ownership regressions; SQLite is real, vector storage is mocked."""
import sqlite3
from unittest.mock import Mock, patch

import pytest

from zhiyan_legal import judgment_rag as rag


@pytest.mark.parametrize("fail_close", [False, True])
def test_index_close_releases_both_resources(tmp_path, fail_close):
    store = Mock()
    if fail_close:
        store.close.side_effect = RuntimeError("synthetic close failure")
    with patch.object(rag, "LocalEmbeddingModel", return_value=Mock(dimension=3)), \
            patch.object(rag, "JudgmentVectorStore", return_value=store):
        index = rag.JudgmentRagIndex(manifest_path=str(tmp_path / "manifest.sqlite3"))
    try:
        if fail_close:
            with pytest.raises(RuntimeError, match="synthetic close failure"):
                index.close()
        else:
            index.close()
        store.close.assert_called_once_with()
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            index.manifest.conn.execute("SELECT 1")
    finally:
        index.manifest.close()
