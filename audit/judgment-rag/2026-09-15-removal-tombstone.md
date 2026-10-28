# 2026-09-15｜撤下全文清除與向量刪除重跑

## 摘要

- Repository：Lucien-1127/zhiyan-legal；沿用 PR #14。
- 本次基線：`54274750b5993060e309e8c75e92a4eb681656dc`，由 GitHub 重新核對。
- 官方明確回覆撤下時，SQLite 立即清空全文、內容 hash、案件 metadata、PDF／來源連結與切片。
- 不存在的 JID 也建立最小 tombstone，只保留 JID、狀態、時間與原因。
- Qdrant 刪除失敗標記 `removal_pending`，不計為成功移除；API 或 JSONL 下次遇到相同撤下資料會重試。
- 向量刪除成功後改為 `removed`；重新公開會由既有狀態修復流程完整重建。

## 證據與驗證結果

環境：Python 3.12.14、qdrant-client 1.19.0。判決、JID、錯誤與三維向量均為合成測試資料。
SQLite 與 Qdrant 使用真實暫存磁碟；未下載嵌入模型、未呼叫司法院 API 或遠端 Qdrant Server。

新增測試在未修補基線：

```text
5 failed, 4 passed in 1.05s
```

失敗證明：舊程式保留案件 metadata／全文，未知 JID 無墓碑，Qdrant 刪除失敗後仍標成
`removed`，無法區分待清理狀態。

修補後相關驗證：

```bash
PYTHONPATH=src python -m pytest \
  tests/test_judgment_removal.py \
  tests/test_judgment_qdrant_integration.py \
  tests/test_judgment_api_errors.py \
  tests/test_judgment_index_recovery.py \
  tests/test_judgment_rag.py -q --tb=short
```

```text
33 passed, 14 subtests passed in 0.99s
```

驗證涵蓋：

1. 既有判決撤下後敏感欄位與切片全部清空，保留最小稽核。
2. 未曾收錄的撤下 JID 也建立 tombstone。
3. 模擬向量刪除失敗時狀態為 `removal_pending`、成功數為 0，重跑成功才成為 `removed`。
4. `removal_pending` 收到有效同內容後會恢復並重新向量化。
5. JSONL 撤下資料同樣能在刪除失敗後重跑。
6. 真實本地 Qdrant 中，第一次刪除失敗時舊向量仍可觀察；第二次同步成功後搜尋為空。

完整無金鑰回歸命令：

```bash
ZHIYAN_API_KEY=sk-ci-placeholder PYTHONPATH=src python -m pytest tests/ --tb=short \
  --ignore=tests/test_c54_validation.py \
  --ignore=tests/run_ablation_v8_committee.py -m 'not integration' -q
```

```text
334 passed, 6 skipped, 14 subtests passed in 4.06s
```

`sk-ci-placeholder` 是固定測試字串，不是金鑰。`git diff --check` 與 compileall 均通過。

## 阻塞與未完成事項

- 向量失敗情境在 client 呼叫邊界注入；真實寫入與查詢使用本地 Qdrant，未驗收網路／Server 故障。
- `removal_pending` 期間 Qdrant 舊點可能仍可被搜尋，直到重試成功；正式服務須在回答層依 tombstone 過濾，或以 Server 交易／集合切換策略處理。
- live SQLite／Qdrant 清除不會修改歷史備份、匯出檔與前端快取；部署規則已加入操作文件，但正式主機尚未驗收。
- 索引指紋、tokenizer 上限、來源定位、API 阻塞／執行緒與初始化失敗清理仍待完成。
- 未使用真實嵌入或司法院帳密，未合併或部署，階段一整體仍未通過。

## 下一步與完成標準

從本提交接續索引指紋：模型、維度、切片上限／重疊與 collection 變更時不得跳過重建或混寫。
之後處理 tokenizer、來源定位及 API／初始化生命週期。正式 Qdrant Server、真實模型與少量官方判決
仍須在具持久儲存且安全載入 secrets 的主機驗收。

## 相關任務

- [唯一原任務](https://app.notion.com/p/3d5718ac0bbf817d8d02c11c9f9ba59d)
- [PR #14](https://github.com/Lucien-1127/zhiyan-legal/pull/14)
