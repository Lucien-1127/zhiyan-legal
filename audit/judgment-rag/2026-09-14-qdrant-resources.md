# 2026-09-14｜Qdrant 關閉修補與真實本地儲存驗證

## 摘要

- Repository：Lucien-1127/zhiyan-legal；原 PR #14。
- 本次基線：`5c2f8a35055c754b98d7f927c63ce56c7aa03ca9`，由工具重新核對。
- 修復 `JudgmentRagIndex.close()` 僅關閉 SQLite、未釋放 Qdrant 目錄鎖的問題。
- 新增 `JudgmentVectorStore.close()`，索引以 `try/finally` 關閉兩個元件；Qdrant 關閉失敗也會關閉 SQLite，並保留錯誤。
- 沿用已提交的更新／重跑策略，沒有重製前次補丁。

## 證據與驗證結果

環境：Python 3.12.14、qdrant-client 1.19.0、真實暫存 SQLite 與 Qdrant 本地磁碟儲存。
判決均為合成文字與 SYNTHETIC 識別碼，向量固定為 `[1.0, 0.0, 0.0]`。
未下載嵌入模型、未呼叫司法院 API、未使用 Qdrant Server。

安裝：

```bash
python -m pip install -e '.[test,committee]' 'qdrant-client>=1.10.0'
```

新增測試對未修補基線：

```text
4 failed, 2 passed in 0.95s
```

- 兩項資源生命週期測試失敗：Qdrant close 沒有被呼叫；注入 close 錯誤也未傳回。
- 兩項重新開啟測試失敗：`Storage folder ... is already accessed by another instance of Qdrant client`。
- 版本更新／保留其他 JID 與刪除失敗後重跑兩項在基線已通過，佐證前次修補有效。

修補後：

```bash
PYTHONPATH=src python -m pytest tests/test_judgment_resources.py tests/test_judgment_qdrant_integration.py -q --tb=short
```

```text
6 passed in 0.80s
```

六項驗證包含：

1. 正常 close 同時關閉兩個元件。
2. Qdrant close 拋錯仍關閉真實 SQLite 並傳回錯誤。
3. 更新長判決為短判決後，scroll 與 search 僅有新版本；其他 JID 不受影響；相同內容不重刪。
4. 在 Qdrant client 刪除呼叫邊界注入失敗：新向量不寫入、舊向量保留、重跑完整替換。
5. 第二批向量實際寫入後注入回覆遺失：磁碟有 4 點而 manifest 仍有 pending；關閉再重開後，重跑得到完整新版本。
6. 重複 close 後能重新開啟同一磁碟目錄，原有索引仍可查詢。

完整無金鑰回歸：

```bash
ZHIYAN_API_KEY=sk-ci-placeholder PYTHONPATH=src python -m pytest tests/ --tb=short \
  --ignore=tests/test_c54_validation.py \
  --ignore=tests/run_ablation_v8_committee.py -m 'not integration' -q
```

```text
328 passed, 6 skipped, 14 subtests passed in 3.88s
```

上述固定 placeholder 不是實際 API 金鑰。`git diff --check` 通過。
既有 CI 沒有安裝 qdrant-client，因此新增真實 Qdrant 模組在該環境會跳過；
Qdrant 驗證證據為本次實際本地執行，不可把一般 CI 綠燈當成已跑此模組。

## 阻塞與未完成事項

- Qdrant 採本地儲存模式；未驗收遠端 Server、網路中斷、跨程序崩潰或正式主機。
- 故障在 client 呼叫邊界注入，實際寫入／刪除／scroll／search 使用 Qdrant。
- 未驗證真實 embedding 的 tokenizer 上限、法律檢索品質或司法院 Auth/JList/JDoc。
- 更新期間可能暫無或只有部分新切片；API 多執行緒、事件迴圈阻塞、初始化失敗清理仍待處理。
- SQLite 撤下全文殘留、索引指紋與來源定位亦未在本次修補。
- 未合併、未部署，未安裝主機增量同步；階段一整體尚未通過。

## 下一步與完成標準

在本提交上處理撤下全文清除或索引指紋等剩餘一致性問題；保持單一原任務。
Qdrant Server／真實模型／少量官方判決驗收須在已確認可連線且具持久儲存的主機執行。

## 相關任務

- [唯一原任務](https://app.notion.com/p/3d5718ac0bbf817d8d02c11c9f9ba59d)
- [PR #14](https://github.com/Lucien-1127/zhiyan-legal/pull/14)
- [資源關閉審查](https://github.com/Lucien-1127/zhiyan-legal/pull/14#discussion_r3967581960)
