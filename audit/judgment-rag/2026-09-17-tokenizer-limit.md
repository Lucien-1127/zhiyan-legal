# 判決嵌入 tokenizer 上限修補驗收（2026-09-17）

## 問題與修補

- 舊版只依 `JUDGMENT_CHUNK_MAX_CHARS` 切片，未以模型 tokenizer 計算實際輸入；
  案由標題與段落前綴也未納入上限，因此模型可能靜默截斷判決後段。
- 索引前現在會讀取模型的 `max_seq_length`，以完整的
  `標題｜段落｜切片` 輸入計算 token，必要時在字元邊界再次切分。
- `LocalEmbeddingModel.encode` 增加最後一道上限檢查；過長查詢或漏網輸入會明確
  失敗，不再交給模型靜默截斷。
- token 上限與新版輸入模板納入索引指紋。既有 collection 不會被不同切片語意
  直接沿用，升級時須指定新的空 collection 並執行 `rebuild-index`。
- SQLite `index_config` 會補上 `embedding_max_tokens` 欄位；`status` 也會顯示該值。

## 可重跑驗證

```bash
PYTHONPATH=src python -m pytest -q \
  tests/test_judgment_tokenizer_limit.py \
  tests/test_judgment_index_fingerprint.py

ZHIYAN_API_KEY=sk-ci-placeholder PYTHONPATH=src python -m pytest tests/ \
  --ignore=tests/test_c54_validation.py \
  --ignore=tests/run_ablation_v8_committee.py \
  -m "not integration" -q

python -m compileall -q src backend tests
git diff --check
```

本次結果：

- 新增三個核心案例在前一提交 `bd58c4c`：3 failed，確認會把超限輸入送進模型，
  也沒有最後一道拒絕機制。
- 修補後 tokenizer 與索引指紋回歸：15 passed。
- 完整無金鑰回歸：349 passed、6 skipped、14 subtests passed。
- `compileall` 與 `git diff --check` 通過。

## 證據界線

- 新增 tokenizer 回歸使用可重現的合成 tokenizer、合成判決、真實暫存 SQLite 與
  本地 Qdrant，並檢查送入 embedder 的每一筆完整字串都未超限。
- 本次沒有下載或執行真實 `paraphrase-multilingual-MiniLM-L12-v2`，沒有連線司法院
  API、Qdrant Server 或正式部署主機，也沒有使用真實帳密。
- 完整測試與 GitHub CI 通過不等於法律內容品質、全量涵蓋或正式部署驗收。
