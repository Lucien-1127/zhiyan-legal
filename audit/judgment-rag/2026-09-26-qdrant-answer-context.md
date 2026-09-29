# Qdrant 判決檢索接入回答主鏈驗收

日期：2026-09-26

## 本次範圍

- 將 `JudgmentRagIndex.search()` 已經 manifest 有效版本檢查的結果，轉成 canonical
  `Claim`、`Evidence`、`Citation`。
- 讓 `/api/chat` 以 `task=RESEARCH`、`use_judgments=true` 明確啟用判決檢索。
- 以 thread pool 執行嵌入與 Qdrant 查詢，避免阻塞 FastAPI event loop。
- 無結果／缺原文／缺來源／缺裁判日期時 fail closed：回 `ASK` 且不呼叫模型。

## 信任邊界

- `exact_quote` 使用 Qdrant payload 中的完整切片原文；locator 包含來源端點、JID、
  Qdrant chunk id 與 sequence。
- 語意命中不代表判決適用於個案，因此 Evidence 固定為 `PARTIAL`，引註層級為
  `NEED_CHECK`，命題僅是 supporting／unverified 的「檢索原文」。
- RESEARCH 問題不捏造行為人、時間、地點、行為及結果五要素；已有可核對來源時可
  進入回答，若要套用個案仍須另補事實並人工覆核。

## 可重跑驗證

```bash
python -m pip install -e '.[api,committee,test]' 'qdrant-client>=1.10.0'
python -m pytest -q \
  tests/test_judgment_qdrant_integration.py \
  tests/test_judgment_answer_context.py \
  tests/interfaces/test_chat_judgment_retrieval.py

ZHIYAN_API_KEY=sk-ci-placeholder \
  python -m pytest tests/ --tb=short -m 'not integration' -q
```

本次隔離環境結果：

- 真實本地 Qdrant（合成判決、固定三維向量）與主鏈五情境：14 passed。
- 完整無外部金鑰回歸：380 passed、5 skipped、5 deselected、14 subtests passed。

## 尚未驗收

- 司法院真實帳密、Auth／JList／JDoc 與真實判決。
- `paraphrase-multilingual-MiniLM-L12-v2` 真實嵌入品質。
- 持久主機 Qdrant Server、容器重啟、備份還原與主機增量排程。
- 真實模型對固定法律案例的人工引用品質覆核。

以上項目不得由本次本地合成資料測試推論為已通過。
