# 評估資料集 — zhiyan-legal Evaluation Dataset

> **狀態**：🟡 種子階段（15/200 queries 已完成）  
> **目標**：200 queries，涵蓋 9 條路由 × 標準/邊界兩種難度

## 結構

```
data/
├── eval_queries.json        # 主資料集（JSON，可機器讀取）
├── eval_schema.json         # JSON Schema（驗證用）
└── articles/                # 全國法規資料庫原始 JSON（來源：law.moj.gov.tw）
```

## 路由分配（計畫）

| Route | 計畫數 | 標準 | Edge Case | 主測 RQ |
|-------|:------:|:----:|:---------:|:-------:|
| QC | 30 | 20 | 10 | RQ1 |
| RESEARCH | 30 | 20 | 10 | RQ1、RQ3 |
| REPORT | 20 | 15 | 5 | RQ1 |
| CONSULTANT | 20 | 15 | 5 | RQ1 |
| TUTOR | 20 | 15 | 5 | RQ1 |
| TA | 20 | 15 | 5 | RQ1 |
| LITIGATION | 15 | 10 | 5 | RQ1、RQ2 |
| SAFETY | 25 | RL1:10/RL2:10 | RL3:5 | RQ2 |
| CROSS_JUR | 20 | 15 | 5 | RQ1 |
| **合計** | **200** | **145** | **55** | — |

## Edge Case 設計原則（觸發 CORE_GATE G0）

- **不存在條文**：如「勞動基準法第500條」「民事訴訟法第1000條之3」
- **不存在項次**：如「民法第600條第3項」（條文存在但該項不存在）
- **近期修法模糊**：引用最新版本但未指定版本年份，資料可能過期
- **SIMULATION 語境**：法庭模擬中含高危詞，測試 SRP 語境感知能力
- **跨域概念混淆**：引用不適用條文作為依據

## 驗證

```bash
python scripts/validate_dataset.py data/eval_queries.json
```

## 標注規範

1. `statutes[].moj_verified = true` — 在 [law.moj.gov.tw](https://law.moj.gov.tw) 確認條文存在
2. `verifiable_claims[].is_fabricatable = true` — 標記 LLM 容易捏造的聲明
3. `expected_gate_trigger` — 明確預期系統應觸發的閘門動作
4. SAFETY queries — 僅在 condition_A（full system）下執行，B/C/D 設為 false

## 授權

CC-BY-4.0
