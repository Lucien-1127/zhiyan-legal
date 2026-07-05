# 智研 AI 法律系統

> **Zhiyan AI Legal System** — 以分層架構、強制引用政策與安全路由為核心的台灣法律 AI 研究平台

---

## 🎯 三大研究問題

| # | 研究問題 | 緩解機制 |
|---|---------|---------|
| RQ1 | 禁止捏造引用的政策能否降低法條幻覺率？ | Citation Policy v2.1 |

| RQ1 | 禁止捏造引用的政策能否降低法條幻覺率？ | Citation Policy v2.1 + Multi-Model Committee |
| RQ2 | 優先安全路由能否降低有害輸出？ | SRP 分層風險評分 |
| RQ3 | 事實閘門能否改善不確定性校準？ | CORE_GATE 事實分級 + 缺口標記 |

## 🏗️ 系統架構

```
G0 → INTAKE → SRP → CORE_GATE → L0.7 RAG → L0.8 CASE_VERIFY → MODE → PERSONA → CITATION → OUTPUT
```

## 🔬 四大研究特性

- **G0 信心優先** — 輸出前宣告信心度，低信心即停止
- **🔬 禁止捏造** — 禁止虛構法條/判決，無法驗證者標記 `待查`
- **🛡️ 事實閘門** — CORE_GATE 在得出結論前進行分層驗證
- **⚠️ 安全路由** — 高風險輸入在法律分析前轉入安全協定

## 📚 快速導覽

| 章節 | 內容 |
|:-----|:------|
| [總覽](00_入口與總覽/00_開始閱讀_入口導覽_v2.1.0.md) | 從這裡開始閱讀 |
| [核心控制層](10_核心控制層/10_主人格_MASTER_v2.0.0.md) | MASTER、BOOT、CORE_GATE |
| [模式與引用](20_模式與引用層/20_模式_REPORT_報告_v2.0.0.md) | REPORT、RESEARCH、QC、CITATION |
| [模組與人格](40_模組與人格層/53_人格_總綱_v2.0.0.md) | 6 種人格、法庭模擬、申論批改 |
| [概念詞條](60_概念詞條/60_概念詞條_INDEX_v1.0.0.md) | 安全、法律、事實分級等 40+ 詞條 |
| [願景](vision.md) | 從 AI 工具到 AI 法律作業系統 |
| [路線圖](roadmap.md) | Phase 1~4 開發規劃 |
| [架構](architecture.md) | 七層系統架構完整規格 |

---

| [模組與人格](40_模組與人格層/53_人格_總綱_v2.0.0.md) | 14 種人格/模組（含合約起草、風險策略、提示詞工程） |
| [概念詞條](60_概念詞條/60_概念詞條_INDEX_v1.0.0.md) | 安全、法律、事實分級等 40+ 詞條 |
| [願景](vision.md) | 從 AI 工具到 AI 法律作業系統 |
| [路線圖](roadmap.md) | Phase 1~4 開發規劃（v3.08 當前進度） |
| [架構](architecture.md) | 七層系統架構完整規格 |
| [Benchmark](benchmark/essay-questions.md) | AI 法律推理能力測驗集（6 題跨法域） |

## ⚡ 快速開始

```bash
# Hermes Agent
/zhiyan 分析這份合約的風險

# Python CLI
git clone https://github.com/Lucien-1127/zhiyan-legal.git
cd zhiyan-legal && bash scripts/setup.sh
PYTHONPATH=src python -m zhiyan_legal "何謂公然侮辱？"
```

> ⚠️ 輸出為研究用途，**不構成法律意見**。請諮詢合格律師。
