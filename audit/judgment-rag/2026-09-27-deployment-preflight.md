# 判決庫部署預檢與 `.env` 載入驗收

日期：2026-09-27

## 發現的問題

操作文件要求把司法院帳密放在專案根目錄 `.env`，但 `zhiyan-judgment-rag` CLI
先前只讀取程序環境，沒有自行載入 `.env`。使用者照文件設定後，CLI 仍可能以空帳密
執行；同時 Compose 沒有在後端啟動前驗證 Server 模式、模型 revision 或 manifest
持久路徑。

## 本次修正

- CLI 從目前目錄向上尋找最近的 `.env`，並以 `override=False` 保留部署 secrets／
  主機環境變數的優先權。
- 新增 `preflight`；不初始化 embedding、SQLite 或 Qdrant，也不發出網路請求。
- 報告只顯示 `JUDICIAL_API_USER`／`JUDICIAL_API_PASSWORD` 是否存在，不輸出內容。
- `--require-server` fail closed 檢查 Qdrant Server 模式、絕對 manifest 路徑、固定模型
  revision、數值設定與 `.env` 權限。
- Compose 後端在啟動 uvicorn 前強制執行 `preflight --require-server`。

## 可重跑驗證

```bash
python -m pytest -q \
  tests/test_judgment_preflight.py \
  tests/test_judgment_deployment_assets.py \
  tests/test_judicial_api.py
```

針對性驗證：24 passed。

完整無金鑰回歸：385 passed、5 skipped、5 deselected、14 subtests passed。
Python 編譯檢查與 `git diff --check` 均通過。

## 證據限制

本次只驗證設定載入、秘密遮蔽及 fail-closed 啟動契約。執行環境仍沒有持久部署主機、
Docker 執行器或司法院真實帳密，因此未啟動 Qdrant Server、未下載真實模型、未同步
真實判決，也未驗收備份還原或排程觸發。
