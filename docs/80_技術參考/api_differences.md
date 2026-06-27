# 司法院判決 API 對比

## 官方 API（data.judicial.gov.tw）
- 需要帳號密碼（你已忘記）
- 限制 00:00–06:00 才能查
- 回傳 7 天前的異動資料
- 只能用 JID 精準查詢，無全文搜尋
- 只能查判決，無法查法條或釋憲

## MCP Taiwan Legal DB（mcp-taiwan-legal-db）
- 免帳密，直接爬 judgment.judicial.gov.tw 公開頁面
- 無時間限制，白天也能查
- 即時資料，非 7 天前
- 支援全文搜尋（關鍵字、法院、案件類型）
- 還能查全國法規（law.moj.gov.tw）+ 釋憲（cons.judicial.gov.tw）
- pip install mcp-taiwan-legal-db 即可

## 結論
官方 API 唯一用途是做離線批次備份（凌晨定時抓），日常查詢全部用 MCP 就好。
