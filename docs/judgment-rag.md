# 司法院判決書自有向量庫

本專案提供一條可重跑的判決書資料管線：

```text
司法院官方 Auth / JList / JDoc
        ↓
SQLite manifest（JID、版本、內容 hash、移除稽核）
        ↓
中文語意切片（保留主文、事實、理由與來源定位）
        ↓
本地 Qdrant（判決切片向量與 metadata）
        ↓
CLI 或 FastAPI /api/judgments/search
```

## 安裝

在專案根目錄執行：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[rag,api]'
```

第一次使用多語嵌入模型時，`sentence-transformers` 會下載模型。預設模型是
`paraphrase-multilingual-MiniLM-L12-v2`，向量維度為 384，適合先在本機建立中文判決庫。
若要替換模型，必須同時使用新的 Qdrant collection，避免不同維度混寫。

## 憑證與本地資料

請將以下設定放入本機 `.env` 或部署平台的 secret，不要提交至 Git：

```dotenv
JUDICIAL_API_USER=你的司法院公開平台帳號
JUDICIAL_API_PASSWORD=你的司法院公開平台密碼
JUDICIAL_API_BASE_URL=https://data.judicial.gov.tw/jdg/api
JUDGMENT_MANIFEST_PATH=data/judgments/manifest.sqlite3
JUDGMENT_QDRANT_PATH=data/qdrant
JUDGMENT_QDRANT_COLLECTION=zhiyan_legal_judgments
JUDGMENT_EMBED_MODEL=paraphrase-multilingual-MiniLM-L12-v2
JUDGMENT_CHUNK_MAX_CHARS=800
JUDGMENT_CHUNK_OVERLAP=80
JUDGMENT_EMBED_BATCH_SIZE=32
```

`manifest.sqlite3` 與 Qdrant 目錄包含判決全文與向量，應放在加密磁碟、私有備份或受控的部署環境，不應推送至公開 Git repository。專案的 `.gitignore` 已建議排除這些產物。

## 指令

查看狀態：

```bash
zhiyan-judgment-rag status
```

查詢已建立的本地判決向量庫：

```bash
zhiyan-judgment-rag search "毒品危害防制條例 再犯期間 三年" --top-k 8
```

同步司法院官方近期異動：

```bash
zhiyan-judgment-rag sync-changes
```

依 JID 檔案同步指定判決：

```bash
zhiyan-judgment-rag sync-jids data/judgments/jids.txt
```

每列一個 JID，例如：

```text
TPHM,110,毒抗,1212,20210831,1
CHDM,100,訴,1552,20130517,2
```

## 歷史全量 bootstrap

司法院的裁判書資料開放平台另提供按月份的批次資源。官方裁判書 API 的 JList 是異動同步入口，不是歷史全量目錄；因此建議採用以下流程：

1. 從司法院資料開放平台的「裁判書」分類下載需要的月份批次檔。
2. 在受控的本地資料目錄解壓與整理，將每筆 JDoc JSON 保留為 JSON Lines，一行一個官方 JDoc 回應。
3. 執行：

```bash
zhiyan-judgment-rag import-jsonl /secure/path/judgments-2024.jsonl
```

`import-jsonl` 對同一 JID 使用內容 hash 去重；內容沒有變化時不重複向量化，內容變化時以最新全文與新切片覆蓋舊索引。若官方資料回傳已移除訊息，該 JID 會從 Qdrant 移除，但 manifest 會保留移除稽核紀錄。

本版本先刻意要求 bootstrap 輸入標準化 JSONL，不直接假設每一種官方 RAR 內部檔案格式；這可避免把批次檔案格式猜錯而污染法律資料庫。可以依你實際下載的批次檔內容再增加專用解包轉換器。

## FastAPI 端點

啟動 backend 後，向量庫為延遲載入：

```bash
GET /api/judgments/status
POST /api/judgments/search
```

查詢 payload：

```json
{
  "query": "買賣物有瑕疵時買受人可以主張什麼？",
  "top_k": 8,
  "year": ""
}
```

回傳會包含 `jid`、法院、裁判日期、案由、切片序號、原文與來源 URL；前端或 LLM 層應把這些欄位轉成可核對的判決引用，不應只顯示向量分數。

## 同步規則

司法院官方規格指出，同一 `JID` 代表同一筆裁判書；後續同一 `JID` 的內容應覆蓋先前版本。若官方回覆判決已移除或不再公開，本專案會刪除該 JID 的向量點。建議在 API 開放時段執行 `sync-changes`，並保留每次執行的輸出與 manifest 備份。

## 安全邊界

這個向量庫是法律研究與引用檢索工具，不代表檢索到的判決必然適用於個案。回答層仍應保留裁判日期、法院、案號、原文切片與官方來源，並做現行有效性、案件事實與引用內容的人工覆核。

## 官方資料來源

- [司法院裁判書開放 API 規格說明](https://opendata.judicial.gov.tw/api/Newses/42/file)
- [司法院資料開放平台開發指引](https://opendata.judicial.gov.tw/DevelopmentGuide)
- [司法院裁判書批次資源分類](https://opendata.judicial.gov.tw/data/api/rest/categories/051/resources)

所有官方資料的使用仍應遵循司法院當期公告、授權條款與個資／隱私要求。
