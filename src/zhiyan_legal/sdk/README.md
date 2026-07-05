# Zhiyan Legal AI SDK v1.0.0

提供 Python 原生介面呈現 Zhiyan API，內建統一路由器與合議庭支援。

---

## 安裝

```bash
pip install -e .[sdk]   # 開發安裝
# 或從套件根目錄：
PYTHONPATH=src python -c "from zhiyan_legal.sdk import ZhiyanClient"
```

## 快速開始

```python
from zhiyan_legal.sdk import ZhiyanClient

client = ZhiyanClient()  # 自動讀取 .env

# 基本查詢（自動路由到正確任務）
result = client.query("什麼是公然侮辱？")
print(result.content)      # 回應文字
print(result.task)         # "TUTOR"
print(result.provider)     # "zhiyan" / "agnes" / "gemini"
print(result.latency_ms)   # 記錄延遲

# 指定任務
result = client.query("分析這份合約風險", task="QC")

# 合議庭模式（全部提供商平行驗證）
committee = client.committee("正當防衛的構成要件？")
print(committee.verdict)         # "consensus" / "dissensus" / "blind_spot"
print(committee.merged_content)  # 主應商回應
for vote in committee.votes:
    print(f"  {vote.provider}: {vote.content[:80]}...")

# DRY-RUN 測試（不發送真實 API）
result = client.query("測試", dry_run=True)

# async 环境（FastAPI）
import asyncio
result = asyncio.run(client.aquery("張三點死從與正當防衛有何差異？"))
```

## 提供商路由模式

| Priority | 提供商 | 路由時機 |
|:--------:|------|----------|
| 0 | **Zhiyan 本公司 API** | 所有請求首先導向 |
| 1 | Agnes AI (Key1) | Zhiyan 失效時 fallback |
| 2 | Agnes AI (Key2) | Agnes Key1 失效時 fallback |
| 3 | Google Gemini | 合議庭 / 最後 fallback |

## 必要環境變數

```bash
# .env 或導出複製至 .env
ZHIYAN_API_KEY=sk-...           # 本公司 API 金鑰（必須）
ZHIYAN_API_BASE_URL=https://... # API 基礎 URL
ZHIYAN_MODEL=gpt-4o-mini        # 主要模型

AGNES_API_KEY_1=...             # Agnes 席次
1
AGNES_API_KEY_2=...             # Agnes 席次 2
GEMINI_API_KEY=...              # Google Gemini
```

## 異常處理

```python
from zhiyan_legal.sdk import ZhiyanClient, ZhiyanAPIError, ZhiyanAuthError, ZhiyanTimeoutError

client = ZhiyanClient()
try:
    result = client.query("查詢")
except ZhiyanAuthError as e:
    print(f"API 金鑰錯誤: {e}")     # 不重試
except ZhiyanTimeoutError as e:
    print(f"逾時: {e.provider}")      # 將自動 fallback 到下一供應商
except ZhiyanAPIError as e:
    print(f"API 錯誤 [{e.status_code}]: {e}")
```

## 目錄結構

```
src/zhiyan_legal/sdk/
├── __init__.py          ← 公開介面匯出
├── client.py            ← ZhiyanClient 主實體
├── models.py            ← 資料模型定義
├── exceptions.py        ← 自定義異常
├── provider_registry.py ← 提供商注冊表
├── api_router.py        ← 統一 API 路由器
└── README.md            ← 此文件
```
