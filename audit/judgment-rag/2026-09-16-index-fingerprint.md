# 2026-09-16｜索引指紋與新集合重建

## 摘要

- Repository：Lucien-1127/zhiyan-legal；沿用 PR #14。
- 本次基線：`eb9f121a3cebde8f23da96039333f318f03f570e`，由 GitHub 重新核對。
- SQLite 新增單一 active 索引設定，指紋包含 collection、模型、模型 revision、實際向量維度、切片上限／重疊、嵌入輸入模板與指紋版本。
- 同一 collection 的語意設定改變時拒絕啟動；切換新的空 collection 時，必須明確執行 `rebuild-index`。
- 重建期間標記 `rebuild_pending` 並拒絕查詢部分索引；成功後才改為 `ready`。
- 非空目標 collection 或無 manifest 可核對的孤兒向量拒絕採用。

## 證據與驗證結果

環境：Python 3.12.14、qdrant-client 1.19.0。判決與三維向量均為合成測試資料；
SQLite 與 Qdrant 使用真實暫存磁碟，未下載真實嵌入模型、未呼叫司法院 API 或遠端 Qdrant Server。

原版執行最初七項指紋回歸：

```text
7 failed in 1.13s
```

失敗原因為原版沒有 `embed_model_revision`、索引指紋、設定衝突拒絕或 `rebuild-index`。
後續另增加一項 pre-fingerprint manifest 對空 collection 的安全重建案例。

修補後相關驗證：

```text
45 passed, 14 subtests passed in 1.50s
```

涵蓋索引指紋、真實本地 Qdrant、索引中斷重跑、撤下清除、一般 API 錯誤與資源關閉。

完整無金鑰回歸：

```text
344 passed, 6 skipped, 14 subtests passed in 4.61s
```

`python -m compileall -q src tests backend`、`git diff --check` 與 CLI `--help` 均通過；
CLI 已列出 `rebuild-index`。

## 阻塞與未完成事項

- 模型 revision 只有在設定 `JUDGMENT_EMBED_MODEL_REVISION` 時才會固定；空值仍代表使用上游預設 revision。
- pre-fingerprint manifest 與已存在向量的首次升級採一次性設定；程式無法從舊向量反推出實際模型 revision，正式部署前仍應用新的空 collection 重建驗收。
- 未驗收真實 sentence-transformers 模型、Qdrant Server、網路／跨程序故障或司法院 API。
- tokenizer 實際輸入上限、來源定位、FastAPI 阻塞／SQLite 執行緒及延遲初始化競爭仍待修復。
- PR 未合併、未部署；階段一整體仍未通過。

## 下一步與完成標準

接續 tokenizer 上限：以模型 tokenizer 的實際輸入限制計算「案由／段落前綴＋正文」，不得讓預設模型在 128 token 後靜默截斷。完成後再處理來源定位與 FastAPI／初始化生命週期。

## 相關任務

- [唯一原任務](https://app.notion.com/p/3d5718ac0bbf817d8d02c11c9f9ba59d)
- [PR #14](https://github.com/Lucien-1127/zhiyan-legal/pull/14)
