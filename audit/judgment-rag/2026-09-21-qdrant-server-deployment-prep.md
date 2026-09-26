# 2026-09-21｜Qdrant Server 部署準備

## 摘要

- Repository：`Lucien-1127/zhiyan-legal`；PR #14。
- 基線：`de1e82321fb688256511ce4a144c67b9ad366b97`。
- 新增 `docker/Dockerfile.backend`，沿用既有 `backend/main.py` 與 `/api/judgments/*`，安裝 `[api,rag]` 選用依賴並以非 root 使用者執行。
- 新增 `compose.judgment-rag.yml`，把後端與 Qdrant Server 放在同一部署堆疊；Qdrant 只加入 internal network，不映射主機埠。
- Qdrant image 固定為 `qdrant/qdrant:v1.19.1`；2026-09-21 重新查證官方 GitHub latest release 為 v1.19.1。
- SQLite manifest、Qdrant storage 與 Hugging Face 模型快取使用三個獨立具名 volume；後端 HTTP 預設只綁定 `127.0.0.1`。

## 設定與安全邊界

- Compose 從主機 `.env` 載入帳密，檔案本身不含司法院帳號、密碼或 API key。
- Compose 強制 `JUDGMENT_QDRANT_PATH=`、`JUDGMENT_QDRANT_HOST=qdrant`，避免把內嵌 Qdrant 寫入容器可拋棄層。
- 文件要求 `.env` 權限 `600`、固定 embedding model revision，並明示 `docker compose down -v` 會刪除持久資料。
- 少量驗收以明確 JID 清單進行；不在未驗收主機上直接跑歷史全量或不受控增量同步。

## 驗證

靜態部署契約共三項：

1. Qdrant image 固定、無 host ports、具有持久 volume 且 private network 為 internal。
2. 後端使用既有 FastAPI app、Server 模式與持久 SQLite，HTTP 僅綁 localhost。
3. Compose 不含司法院帳密，`.env.example` 提供 Server 模式設定。

本次直接執行三個測試函式：

```text
PASS test_backend_uses_existing_fastapi_app_and_server_mode
PASS test_documentation_keeps_credentials_out_of_compose
PASS test_qdrant_server_is_pinned_private_and_persistent
```

`python -m compileall` 通過。

## 證據限制與下一步

- 本執行環境沒有 Docker，因此未執行 `docker compose config`、image build、容器啟動、volume 重啟或網路隔離實測。
- 未連線正式 Ubuntu／VM 主機，也未讀取真實帳密、下載 embedding、啟動 Qdrant Server 或同步司法院資料。
- 推送後以 GitHub CI 驗證 YAML 與靜態契約；正式主機仍須執行 build、健康檢查、volume 重啟、備份還原，以及 20–50 筆真實判決驗收。

官方版本查證：[Qdrant v1.19.1](https://github.com/qdrant/qdrant/releases/tag/v1.19.1)
