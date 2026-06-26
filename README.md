# ⚖️ 智研 AI 法律系統 · SaaS 版

將原本 CLI 版的 [zhiyan-legal](https://github.com/Lucien-1127/zhiyan-legal) 轉換為網頁應用，
提供類似法律人網站的線上法律 AI 諮詢體驗。

## 快速開始

### 1. 設定 API 金鑰

```bash
cp backend/.env.example backend/.env
```

編輯 `backend/.env`，填入你的 API 金鑰。

**支援的 API 提供者：**
| 提供者 | API Base URL | 建議模型 |
|--------|-------------|---------|
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o` |
| OpenRouter | `https://openrouter.ai/api/v1` | `anthropic/claude-3.5-sonnet` |

### 2. 啟動服務

**Windows：** 雙擊 `start.bat`
**WSL/Linux：** `bash start.sh`

### 3. 開啟瀏覽器

前往 http://localhost:8000

## 專案結構

```
智研saas版/
├── backend/
│   ├── main.py          # FastAPI 後端主程式
│   ├── engine.py        # 法律引擎封裝層
│   ├── requirements.txt # Python 相依套件
│   ├── .env             # 環境設定（API 金鑰）
│   └── .env.example     # 設定範本
├── frontend/
│   ├── index.html       # 聊天 UI
│   ├── style.css        # 樣式表（法律專業風格）
│   └── app.js           # 前端邏輯
├── docs/                # 法律規格文件（110+ 份）
├── src/                 # 原始 zhiyan-legal Python 套件
├── start.sh             # WSL/Linux 啟動腳本
├── start.bat            # Windows 啟動腳本
└── README.md
```

## 核心架構

```
使用者輸入 → 模式偵測（法律/一般）→ 提示詞組合（110+ 份法律規格）
                    ↓
              LLM API 呼叫（OpenAI 相容）
                    ↓
           回應 + 引用標記 + 信心指標
```

- **5 層架構**：安全前置(SRP) → 事實閘門(L0) → 人格路由(L1) → 功能模組(L2) → 引用政策
- **G0 鐵律**：寧可說不知道，不可隨意捏造
- **強制引用**：所有法律主張必須標註來源
- **API 無鎖定**：支援任何 OpenAI 相容 API 提供者

## API

| 端點 | 方法 | 說明 |
|------|------|------|
| `/api/status` | GET | 系統狀態檢查 |
| `/api/chat` | POST | 法律 AI 對話 |
| `/api/reload` | POST | 重新載入法律文件 |

### 對話範例

```json
POST /api/chat
{
  "message": "公然侮辱罪的構成要件是什麼？",
  "temperature": 0.3,
  "max_tokens": 4096
}
```

```json
{
  "content": "【公然侮辱罪】...",
  "model": "deepseek-chat",
  "mode": "legal",
  "tokens_in": 4250,
  "tokens_out": 852,
  "mode_label": "⚖️ 法律分析模式"
}
```

## 注意事項

- 法律分析結果僅供參考，不構成正式法律意見
- 使用前請在 `.env` 中設定有效的 API 金鑰
- 首次啟動會自動建立虛擬環境並安裝相依套件
