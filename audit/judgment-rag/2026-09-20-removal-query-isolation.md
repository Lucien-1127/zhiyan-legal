# 2026-09-20｜撤下待清理向量的查詢隔離

## 摘要

- Repository：`Lucien-1127/zhiyan-legal`；PR #14。
- 基線：`4385f4a3473dde545bf0cc8ef2e25b2bfd795405`。
- 修復 `removal_pending` 期間 Qdrant 舊點仍可被搜尋回傳的問題。
- SQLite manifest 為查詢生命週期的權威來源；搜尋結果必須同時符合 `status='active'`、全文非空及目前 `content_hash`。
- 搜尋會擴大候選集合後再過濾，避免少量待清理舊點占滿前幾名；最多檢查 1024 個候選。正確性優先：若待清理舊點過多，結果可以少於 `top_k`，但不會回傳撤下或過期版本。

## 驗證

新增兩項回歸：

1. Qdrant 刪除失敗、manifest 已為 `removal_pending` 時，即使向量庫仍回傳舊點，RAG 搜尋結果也必須為空。
2. 同一 JID 同時出現舊 hash、目前 hash及 manifest 不存在的 JID 時，只回傳目前 active hash。

未修補基線：

```text
2 failed, 5 deselected
```

修補後相關模組：

```text
7 passed in 0.09s
```

另執行 `python -m compileall -q src tests`，通過。

## 證據邊界

- 測試使用真實暫存 SQLite、模擬 embedding／vector store 與合成判決。
- 本次暫存工作區先前 repository clone 已被清理，因此推送前無法在本地重跑完整 repository；推送後以 GitHub CI 的完整 Python 版本矩陣作為補充驗證。
- 本次未呼叫真實司法院 API、真實 embedding、Qdrant Server 或正式部署主機。
- 此修補只隔離搜尋可見性；`removal_pending` 仍須由後續同步重試實際刪除 Qdrant 舊點。
