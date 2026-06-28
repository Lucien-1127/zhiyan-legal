# 多模型合議庭標示器 (Multi-Model Committee Mapper)

zhiyan-legal 的品質閘門。**不裁決，只標示。**

## 安裝

無需額外安裝——依賴：
- Python 3.10+
- OpenAI SDK（已存在於 zhiyan-legal venv）
- google-genai（已安裝）
- 無其他外部依賴

## 使用方式

```bash
# 從 repo 根目錄執行
cd ..

# Dry-run 看看要跑多少
PYTHONPATH=$PWD python3 -m committee.run --dry-run

# 完整執行（hard 類別）
PYTHONPATH=$PWD python3 -m committee.run

# 指定類別 + 輸出 JSON
PYTHONPATH=$PWD python3 -m committee.run \
  --categories nonexistent_article,fabricated_precedent \
  --output /tmp/committee_report.json

# 詳細模式（顯示每個模型判定）
PYTHONPATH=$PWD python3 -m committee.run --verbose
```

## 架構

```
輸入：同一法律查詢
         │
    ┌────┼────┐                Phase 1: Runner
    ▼    ▼    ▼
 Agnes1 Agnes2 Gemini          平行執行
    │    │    │                 
    └────┼────┘
         ▼
    Normalizer                  正規化
    ─────────────────
    Layer A: 用語正規化         Phase 2: Mapper
      "已刪除" / "已廢止" → DELETED
    Layer B: 條號正規化
      "§987" → "民法第987條"
    Layer C: 語意兜底
      difflib 相似度比對
         │
         ▼
    Consensus Mapper            分群 & 標示
    ─────────────────
    ✅ 共識區 → 所有模型一致
    ⚠️ 分歧區 → 模型間意見不同
    ❌ 盲區   → 所有模型全軍覆沒
         │
         ▼
    輸出：CommitteeReport JSON
```

## 輸出格式

```json
{
  "query_id": "Q001",
  "total_models": 3,
  "consensus": 2,
  "disagreement": 1,
  "blind_spot": 0,
  "clusters": [
    {"canonical_ref": "民法第987條", "label": "disagreement",
     "detail": "分歧: deleted vs exists"}
  ],
  "disagreements": [
    {"canonical_ref": "民法第987條",
     "description": "agnes-k1 說「deleted」, gemini 說「exists」"}
  ]
}
```

## 新增模型

編輯 `committee/config.yaml`：

```yaml
models:
  - name: deepseek
    model_id: "deepseek-v4-flash"
    provider: openai
    base_url: "https://api.deepseek.com/v1"
```

或直接修改 `committee/runner.py` 的 `DEFAULT_MODELS`。

## 測試

```bash
# 從 repo 根目錄執行
cd ..
PYTHONPATH=$PWD python3 committee/tests/test_core.py
```

## 設計原則

1. **不裁決** — 合議庭只標示分歧，不做最終判決
2. **不投票** — 3:0 的投票結果可能是集體盲區
3. **透明度優先** — 每個模型的完整回應皆保留
4. **依賴順序** — 語意正規化 > 條號正規化 > 字串比對
