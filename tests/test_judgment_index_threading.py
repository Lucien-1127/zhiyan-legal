"""Cross-thread safety regressions for the judgment index facade."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock
import time
from unittest.mock import Mock, patch

from zhiyan_legal import judgment_rag as rag


def _open_index(tmp_path):
    embedder = Mock(
        dimension=3,
        model_name="synthetic",
        model_revision="rev-1",
        max_sequence_length=128,
    )
    embedder.encode.side_effect = lambda texts: [[1.0, 0.0, 0.0] for _ in texts]
    store = Mock(collection="threading_test")
    store.count.return_value = 0
    with patch.object(rag, "LocalEmbeddingModel", return_value=embedder), \
            patch.object(rag, "JudgmentVectorStore", return_value=store):
        index = rag.JudgmentRagIndex(
            manifest_path=str(tmp_path / "manifest.sqlite3"),
            collection="threading_test",
        )
    return index


def test_status_can_use_manifest_from_a_different_worker_thread(tmp_path):
    index = _open_index(tmp_path)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            result = pool.submit(index.status).result()
        assert result["collection"] == "threading_test"
    finally:
        index.close()


def test_index_serializes_shared_sqlite_and_qdrant_operations(tmp_path):
    index = _open_index(tmp_path)
    active = 0
    maximum = 0
    state_lock = Lock()
    start = Barrier(4)

    def slow_stats():
        nonlocal active, maximum
        with state_lock:
            active += 1
            maximum = max(maximum, active)
        try:
            time.sleep(0.05)
            return {"active": 0}
        finally:
            with state_lock:
                active -= 1

    index.manifest.stats = slow_stats

    def status_after_barrier():
        start.wait()
        return index.status()

    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _item: status_after_barrier(), range(4)))
        assert len(results) == 4
        assert maximum == 1
    finally:
        index.close()
