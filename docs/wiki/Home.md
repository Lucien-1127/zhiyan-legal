# 🏠 智研 AI 法律系統 — 使用手冊

> **Zhiyan AI Legal System** — 台灣法律 AI 研究平台

---

## 快速索引

| 章節 | 說明 |
|:-----|:------|
| 🚀 [快速開始](Quickstart) | 5 分鐘內上手 |
| 🏗️ [系統架構](Architecture) | 七層核心架構說明 |
| 📚 [文件地圖](Documentation-Map) | 90+ 份規格文件導覽 |
| ⚖️ [引用政策](Citation-Policy) | 禁止捏造法條的強制引用機制 |
| 🧪 [壓力測試](Stress-Tests) | 14 項邊界測試結果 |
| 🤖 [代理整合](Agent-Integration) | Hermes / Claude / Gemini 設定 |

---

## 什麼是智研？

智研是一個**可重現的 AI 法律研究平台**，旨在解決大型語言模型在法律領域的幻覺問題。核心創新包含：

- **七層分層架構** — 從信心檢查（G0）到 TYPE-S 校驗的完整管線
- **本地 RAG** — 47,001 條法條的白話摘要資料庫，每日自動同步
- **強制引用政策** — 每條法條判決必須附來源連結，無法驗證則標記
- **安全路由** — 高風險輸入（自傷、暴力等）在法律分析前轉入安全協定

---

## 開始使用

### 需求

- **Hermes Agent**（推薦）或 **Python 3.11+**
- API 金鑰（OpenAI / OpenRouter / Gemini）

### 安裝

```bash
git clone https://github.com/Lucien-1127/zhiyan-legal.git
cd zhiyan-legal
bash scripts/setup.sh
```

### 快速測試

```bash
# 乾執行（零成本）
PYTHONPATH=src python -m zhiyan_legal "何謂公然侮辱？" --dry-run

# 正式查詢
PYTHONPATH=src python -m zhiyan_legal "比較終止契約與解除契約的差異"

# 執行測試
PYTHONPATH=src pytest tests/ -v
```

### Hermes Agent

安裝智研技能後，可直接在對話中使用：

```
/zhiyan 分析這份合約的風險
/zhiyan 什麼是侵權行為的構成要件？
```

---

## 授權

MIT — 輸出為研究目的，**不構成法律意見**。
