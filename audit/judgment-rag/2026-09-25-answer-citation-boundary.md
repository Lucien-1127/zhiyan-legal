# 2026-09-25｜回答與引用傳遞邊界

## 本次完成

- canonical `Citation` 的 `exact_quote`、`locator`、來源標題與驗證狀態會以 JSON 資料送入 provider request。
- 提示明確把引註標示為不受信任資料，禁止把判決原文當作指令。
- 引註清單為空時，提示禁止宣稱存在判決或其他來源支持。
- `/api/chat` 回應新增 `citations`，包含 `citation_id`、`source_id`、來源類型、標題、定位、精確原文、證據等級、驗證狀態、適用時點與驗證時間。
- 回應只輸出仍能對應 canonical `Evidence` 的引註，避免孤兒 citation 外洩到前端。

## 驗證

執行環境：Python 3.12.14；安裝 `committee,api,test` extras；沒有司法院帳密、真實嵌入模型或 Qdrant Server。

```bash
git diff --check
python -m compileall -q src backend tests/test_judgment_answer_citations.py
ZHIYAN_API_KEY=sk-ci-placeholder python -m pytest tests/ --tb=short -m 'not integration' -q
```

結果：`350 passed, 9 skipped, 5 deselected, 14 subtests passed`。

新增針對性驗收涵蓋：有判決引註、無來源不得產生引註、人工覆核仍保留可核對來源；既有 application integration 另涵蓋 provider failure 必須轉為 `STOP`，不得降級交付。

## 邊界與下一步

本次使用合成 canonical evidence/citation 與假 provider，不代表真實 Qdrant、嵌入模型、司法院 API、法律引用品質或正式主機部署通過。下一步須把本地 Qdrant 搜尋結果安全轉成 canonical claim/evidence/citation，再驗收正常、缺資料、無來源、模型失敗與人工覆核的完整 `/api/chat` 主鏈。
