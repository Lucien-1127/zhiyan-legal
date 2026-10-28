# FastAPI 判決端點與 SQLite 執行緒生命週期驗收（2026-09-19）

## 問題與修補

- `/api/judgments/status` 與 `/api/judgments/search` 原為 `async def`，但內部執行
  同步 SQLite、Qdrant 與 embedding 工作，會占住 ASGI event loop。
- 兩個判決端點已改為同步 handler，交由 FastAPI 的 worker thread pool 執行。
- 延遲載入的判決索引新增單例鎖；多個首波請求不會重複載入 embedding 模型或
  同時開啟相同 Qdrant 本地目錄。
- SQLite manifest 改為允許跨 worker thread 使用，並以 re-entrant lock 序列化每個
  manifest 操作；索引 facade 另以鎖保護 SQLite、Qdrant、embedding 與 `close()` 的
  共用生命週期。
- 應用程式關閉時會先從全域狀態卸下索引並標記 closing，再釋放 Qdrant 與 SQLite；
  關閉期間的新請求不得重新建立索引。

## 可重跑驗證

```bash
PYTHONPATH=src:. python -m pytest -q \
  tests/test_judgment_api_threading.py \
  tests/test_judgment_index_threading.py \
  tests/test_judgment_resources.py \
  tests/interfaces/test_interfaces.py

ZHIYAN_API_KEY=sk-ci-placeholder PYTHONPATH=src:. python -m pytest tests/ -q \
  --ignore=tests/test_c54_validation.py \
  --ignore=tests/run_ablation_v8_committee.py \
  -m "not integration"

PYTHONPATH=src:. python -m compileall -q \
  backend src tests/test_judgment_api_threading.py \
  tests/test_judgment_index_threading.py

git diff --check
```

本次五個新回歸案例在前一提交 `4376dfa` 全部失敗：兩個端點仍是 coroutine、
八個併發首請求會建立八個索引、SQLite 跨執行緒拋出 `ProgrammingError`、共用操作
可同時進入，以及 shutdown 期間仍能重建索引。修補後局部回歸 12 passed；CI 同等
完整測試範圍 362 passed、5 skipped、14 subtests passed；`compileall` 與
`git diff --check` 通過。

另執行未列入 CI 的 `tests/test_c54_validation.py` 時仍有 5 個既有失敗；在未套用
本修補的 `4376dfa` 也同樣 5 個失敗，因此不屬於本次判決向量庫變更。

## 證據界線

- 測試使用真實暫存 SQLite、模擬 embedding 與 vector store，並以真實 Python
  worker threads 製造初始化與共用資源競態。
- 本次沒有呼叫真實司法院 API、真實嵌入模型、Qdrant Server 或正式部署主機。
- 通過執行緒與生命週期回歸不等於完成部署驗收；正式主機仍須驗證持久 Qdrant、
  SQLite、模型載入、少量真實判決與關閉重啟。
