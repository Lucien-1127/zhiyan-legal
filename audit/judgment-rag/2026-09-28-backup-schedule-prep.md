# 判決庫備份與排程部署準備（2026-09-28）

## 本次版本

- 基線：PR #14 head `d58d3b93a69e2a80d3aae4e6aae4fce9fdc59cd0`
- 狀態：本地實作與回歸通過，尚待提交與 GitHub CI

## 實際變更

- 新增具名 volume 離線備份腳本，保存 SQLite／原文與 Qdrant 資料及 SHA-256。
- 備份 helper 以 root 讀取 volume 後，將封存檔 ownership 還給執行帳號並設為 600，避免 Docker group 使用者無法校驗或搬移備份。
- 新增只允許還原至空 volume 的還原腳本，不會刪除或覆寫 live data。
- 新增受鎖、限時、限定 API 時段的單次增量同步 wrapper。
- 新增 user systemd service／timer 範例，失敗時有界重試。
- 新增靜態部署契約與 Bash 語法測試。

## 證據界線

- 部署資產局部測試：6 passed。
- 完整無外部金鑰回歸：391 passed、5 skipped、5 deselected、14 subtests passed。
- `systemd-analyze --user verify` 因隔離環境沒有 user manager 而無法執行；unit 仍待正式主機載入驗證。
- 本次只驗證程式與部署資產，沒有執行真實司法院 API、真實 embedding 或正式主機寫入。
- 沒有把 Docker Compose 設定、腳本測試或 CI 通過當成備份還原／排程已實際驗收。
- 正式驗收仍需持久主機、受控 `.env`、20–50 筆真實判決、容器重啟、隔離還原與 timer 實際觸發證據。

## 下一個可執行動作

1. 提交並推送至 PR #14，等待 GitHub CI。
2. PR #13／#14 合併阻塞解除後依序合併。
3. 取得已授權持久主機後依文件完成真實驗收。
