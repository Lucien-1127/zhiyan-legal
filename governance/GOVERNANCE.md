# Governance Contract (V13.2)

核心決策規則 (Decision Rules):
1. **Need RAG?**: 檢查請求是否包含法條/案號/具體事件；非事實類請求禁止觸發 RAG。
2. **Need Committee?**: 若信心分 > 95 且問題屬簡單型，禁止觸發 Committee 以節省開銷。
3. **Need Web Search?**: 嚴格禁止外部 Web Search，僅限本地 MCP 與官方 API 來源。
4. **Need Human Confirmation?**: 凡涉不可逆操作 (DELETE/UPDATE) 或敏感資料輸出 (LV3)，強制暫停。
5. **Can Execute Tool?**: 必須通過 Capability Registry 查核才可調用 Shell/SQL。
6. **Can Write Database?**: 僅限資料 ingest 節點，Writer Agent 禁止直接寫入。
