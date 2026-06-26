# 🚀 快速開始

## 1. 環境準備

### Python 環境

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### API 金鑰

設定環境變數或寫入 `.env`：

```bash
# .env
OPENAI_API_KEY=sk-...
OPENROUTER_API_KEY=...
GEMINI_API_KEY=...
```

## 2. 執行查詢

```bash
# 研究模式（最完整）
PYTHONPATH=src python -m zhiyan_legal "毒品危害防制條例第4條的構成要件" --mode research

# 快速查核
PYTHONPATH=src python -m zhiyan_legal "公然侮辱的要件" --mode qc

# 報告模式
PYTHONPATH=src python -m zhiyan_legal "比較不作為犯與作為犯" --mode report
```

## 3. 執行走勢測試

```bash
PYTHONPATH=src python -m pytest tests/ -v --tb=short
```

## 4. 使用 Hermes Agent

1. 在 Hermes Agent 中載入智研技能
2. 輸入 `/zhiyan` 後加上你的法律問題
3. 系統會自動路由到對應模式

## 常見問題

**Q: 沒有 API 金鑰可以測試嗎？**
A: 可以！使用 `--dry-run` 模式，系統會執行完整流程但不呼叫 LLM。

**Q: 斷網時還能用嗎？**
A: 法條查詢（RAG）可以離線運作，但判決查核需要網路連線至司法院網站。
