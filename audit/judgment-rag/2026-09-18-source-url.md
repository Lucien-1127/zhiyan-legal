# 判決來源 URL 定位修補驗收（2026-09-18）

## 問題與修補

- 舊版 `parse_jdoc()` 固定把 `source_url` 寫成司法院正式 JDoc 端點，忽略實際
  `JUDICIAL_API_BASE_URL`。透過受控 proxy 或測試端點同步時，SQLite 與 Qdrant
  metadata 會標示錯誤來源。
- `sync_jids()` 現在會把 client 實際 `base_url` 傳入 parser，並正規化尾端斜線後
  組成 `/JDoc` 來源。
- 同一 JID 若全文 hash 不變、只有來源端點改變，現在也會重新發布切片與 Qdrant
  payload，避免 SQLite 已更新但向量搜尋仍回傳舊網址。
- JSONL 匯入沒有執行期 API client，仍使用司法院正式 JDoc 端點作為預設來源。

## 可重跑驗證

```bash
PYTHONPATH=src python -m pytest -q \
  tests/test_judgment_source_url.py \
  tests/test_judgment_rag.py \
  tests/test_judgment_api_errors.py

ZHIYAN_API_KEY=sk-ci-placeholder PYTHONPATH=src python -m pytest tests/ \
  --ignore=tests/test_c54_validation.py \
  --ignore=tests/run_ablation_v8_committee.py \
  -m "not integration" -q

python -m compileall -q src backend tests
git diff --check
```

新增三個核心案例在前一提交 `58340d2` 全部失敗：parser 不接受來源 base、同步仍
寫入硬編碼正式網址、來源變更不會重新發布 Qdrant metadata。修補後來源定位相關
測試 18 passed、14 subtests passed；完整無金鑰回歸 352 passed、6 skipped、
14 subtests passed。`compileall` 與 `git diff --check` 通過。

## 證據界線

- 測試使用合成 JDoc、真實暫存 SQLite、模擬 embedding 與 vector store；驗證的是
  來源值傳遞、持久化與重新發布呼叫。
- 本次沒有呼叫真實司法院 API、proxy、真實嵌入模型、Qdrant Server 或正式部署主機。
- API 端點 URL 代表資料取得來源；回答層仍須搭配 JID、法院、日期、案號與原文，
  並由人工核對實際裁判內容及適用性。
