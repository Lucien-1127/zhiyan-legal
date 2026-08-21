# audit/ — 系統審計結果

此目錄集中存放所有系統審計輸出，統一命名規則：`snake_case.json`。

| 檔案 | 說明 |
|------|------|
| `results.json` | 系統綜合審計結果 |
| `prompt_engineering.json` | Prompt 工程審計 |
| `governance_security.json` | 治理與安全審計 |
| `test_and_data.json` | 測試與資料審計 |
| `devops.json` | DevOps 審計 |

> 舊版根目錄 `audit_*.json` / `audit-*.json` 已於 v3.9.4 廢棄，請以此目錄為準。
