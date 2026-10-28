"""Threading regressions for the lazy FastAPI judgment index."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import inspect
from threading import Barrier, Lock
import time
from unittest.mock import Mock

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("slowapi")

from backend import main as backend_main
from zhiyan_legal import judgment_rag as rag


def test_judgment_routes_are_sync_for_fastapi_threadpool():
    assert not inspect.iscoroutinefunction(backend_main.get_judgment_status)
    assert not inspect.iscoroutinefunction(backend_main.search_local_judgments)


def test_lazy_index_initializes_once_across_worker_threads(monkeypatch):
    sentinel = object()
    calls = 0
    calls_lock = Lock()
    start = Barrier(8)

    def factory():
        nonlocal calls
        with calls_lock:
            calls += 1
        # Widen the race window so the unfixed implementation deterministically
        # constructs more than one expensive embedding/Qdrant singleton.
        time.sleep(0.05)
        return sentinel

    monkeypatch.setattr(rag, "index_from_env", factory)
    previous = backend_main._judgment_index
    backend_main._judgment_index = None
    if hasattr(backend_main, "_judgment_index_closing"):
        backend_main._judgment_index_closing = False

    def get_after_barrier():
        start.wait()
        return backend_main.get_judgment_index()

    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _item: get_after_barrier(), range(8)))
        assert results == [sentinel] * 8
        assert calls == 1
    finally:
        backend_main._judgment_index = previous


def test_lazy_index_rejects_initialization_during_shutdown(monkeypatch):
    monkeypatch.setattr(rag, "index_from_env", Mock())
    previous = backend_main._judgment_index
    backend_main._judgment_index = None
    backend_main._judgment_index_closing = True
    try:
        with pytest.raises(RuntimeError, match="正在關閉"):
            backend_main.get_judgment_index()
        rag.index_from_env.assert_not_called()
    finally:
        backend_main._judgment_index = previous
        backend_main._judgment_index_closing = False
