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
正式環境可用 `JUDGMENT_EMBED_MODEL_REVISION` 固定模型 revision。若要替換模型、revision、
切片設定或向量維度，必須同時使用新的空 Qdrant collection，再明確執行重建，避免
不同語意空間混寫。

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
JUDGMENT_EMBED_MODEL_REVISION=
JUDGMENT_CHUNK_MAX_CHARS=800
JUDGMENT_CHUNK_OVERLAP=80
JUDGMENT_EMBED_BATCH_SIZE=32
```

`manifest.sqlite3` 與 Qdrant 目錄包含判決全文與向量，應放在加密磁碟、私有備份或受控的部署環境，不應推送至公開 Git repository。專案的 `.gitignore` 已建議排除這些產物。

CLI 會從目前目錄往上尋找最近的專案 `.env`，且不覆蓋主機或部署平台已注入的
環境變數。設定後先執行不連線、不載入模型的預檢；輸出只顯示帳密是否存在，不會
顯示帳號或密碼內容：

```bash
chmod 600 .env
zhiyan-judgment-rag preflight
```

正式 Qdrant Server 主機應使用較嚴格模式：

```bash
zhiyan-judgment-rag preflight --require-server
```

此模式會要求帳密存在、`.env` 權限不開放給群組／其他使用者、
`JUDGMENT_QDRANT_PATH` 為空、`JUDGMENT_QDRANT_HOST` 已設定、manifest 使用絕對路徑，
並固定 `JUDGMENT_EMBED_MODEL_REVISION`。任一條件未通過會以 exit code 2 結束。

## Qdrant Server 部署準備

正式 Ubuntu／VM 主機可沿用既有 `backend/main.py`，以專用 Compose 檔啟動後端與
Qdrant Server。Qdrant 固定為 `v1.19.1`；它只連到內部 Docker network，不映射到
主機連接埠。FastAPI 預設也只綁定主機 `127.0.0.1:8000`，應由既有反向代理提供
TLS 與外部存取控管。

```bash
cp .env.example .env
chmod 600 .env
# 編輯 .env：填入司法院帳密、固定 JUDGMENT_EMBED_MODEL_REVISION，勿提交 Git。

docker compose -f compose.judgment-rag.yml config
docker compose -f compose.judgment-rag.yml up -d --build
docker compose -f compose.judgment-rag.yml ps
```

後端容器啟動前也會執行 `preflight --require-server`；設定不完整時容器會明確失敗，
不會在未知模型版本、local Qdrant 或缺少司法院帳密的狀態下假裝可用。由於 Compose
只把 `.env` 的值注入容器，主機端檔案權限仍須在 `docker compose up` 前由上方命令檢查。

Compose 會強制使用下列 Server 模式設定，避免誤把內嵌 Qdrant 資料寫進容器層：

```dotenv
JUDGMENT_MANIFEST_PATH=/data/judgments/manifest.sqlite3
JUDGMENT_QDRANT_PATH=
JUDGMENT_QDRANT_HOST=qdrant
JUDGMENT_QDRANT_PORT=6333
```

`judgment_manifest`、`judgment_qdrant` 與 `judgment_models` 都是具名持久 volume；執行
`docker compose down` 不會刪除，但 `docker compose down -v` **會永久刪除資料**，
正式主機不可在未備份時使用 `-v`。

先確認一般 API 存活，再讓判決端點第一次載入模型並連線 Qdrant：

```bash
curl --fail http://127.0.0.1:8000/api/status
curl --fail http://127.0.0.1:8000/api/judgments/status
```

少量真實驗收應使用明確 JID 清單，不先跑歷史全量或不受控的近期清單：

```bash
docker compose -f compose.judgment-rag.yml cp \
  /secure/path/jids.txt backend:/tmp/jids.txt
docker compose -f compose.judgment-rag.yml exec -T backend \
  zhiyan-judgment-rag sync-jids /tmp/jids.txt
docker compose -f compose.judgment-rag.yml exec -T backend \
  zhiyan-judgment-rag status
```

這份 Compose 是部署準備，不代表正式主機已安裝或已同步判決。上線前仍須保存
volume 備份／還原證據，並用 20–50 筆真實判決完成 API、模型、Qdrant Server 與
HTTP 搜尋驗收。

### 備份與還原演練

以下腳本會先停掉後端與 Qdrant，對兩個資料 volume 做一致的離線封存，再重新啟動。
備份目的地必須是受控磁碟上的絕對路徑；腳本不會備份 `.env` 或模型快取：

```bash
ops/judgment-rag/backup.sh /secure/backups/zhiyan-judgments
```

備份目錄包含 SQLite／原文、Qdrant 資料、SHA-256 校驗檔與來源 commit。正式驗收要記錄
備份前後的 `zhiyan-judgment-rag status`、搜尋結果與 `/api/chat` 引用。

還原腳本刻意只接受**全新的空 volume**，不會清空或覆寫現有判決資料。先用另一個
Compose project name 建立隔離的空 volume，再執行：

```bash
COMPOSE_PROJECT_NAME=zhiyan-judgment-restore \
  ops/judgment-rag/restore.sh \
  /secure/backups/zhiyan-judgments/20260928T021500+0800 \
  --confirm-empty-target
```

校驗失敗、目標非空或解壓失敗時都不會宣告成功；解壓中斷時服務會保持停止，避免把
部分還原的索引開放查詢。還原完成後必須重新執行 preflight、狀態、搜尋與引用驗收。

### 主機增量排程

`ops/judgment-rag/sync-once.sh` 會先確認專案 `.env` 存在且權限為 600、鎖定單一
執行個體、確認台北時間介於 02:00–06:00、執行 Server 模式 preflight，再跑
`sync-changes` 與 `status`。成功或失敗的輸出與 exit code 都保留在
`data/judgments/ops/runs/`，預設保存 30 天；不記錄 `.env` 內容。

範例 user systemd unit 假設 repository 位於 `~/zhiyan-legal`：

```bash
mkdir -p ~/.config/systemd/user
cp ops/judgment-rag/systemd/zhiyan-judgment-sync.* ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now zhiyan-judgment-sync.timer
systemctl --user list-timers zhiyan-judgment-sync.timer
```

若 repository 不在該位置，先修改 service 的 `WorkingDirectory` 與 `ExecStart`。執行帳號
必須已有 Docker 權限，且主機重新開機後仍要執行 user timer 時，管理者需依主機政策
啟用 linger。timer 不使用 `Persistent=true`，避免主機在 API 時段外開機時補跑。
同步失敗會每 10 分鐘重試，單次最長三小時；`flock` 會阻止兩次同步重疊。

上述檔案只是可審查的部署資產。只有在已授權持久主機上看到 timer 實際觸發、
20–50 筆真實同步統計、失敗重試紀錄，以及隔離還原後相同搜尋／引用結果，才能標記
「主機排程、備份還原已驗收」。

## 指令

查看狀態：

```bash
zhiyan-judgment-rag status
```

`status` 會顯示 `index_fingerprint`、`index_state` 與模型實際回報的
`embedding_max_tokens`。指紋包含 collection、模型、模型 revision、實際向量維度、
token 上限、切片上限／重疊及嵌入輸入模板版本。

`JUDGMENT_CHUNK_MAX_CHARS` 是第一層字元上限；送入模型前，程式還會以 tokenizer
計算「案由標題＋段落類型＋切片全文」的完整 token 數，超過模型上限就再次分段，
避免 `sentence-transformers` 靜默截斷。查詢文字若超過模型上限則直接回報錯誤，不會
悄悄只使用前段內容。升級到這個 token-aware 格式時，索引指紋會改變，請使用新的
空 collection 執行 `rebuild-index`。

變更上述任一設定時，先指定**新的空 collection**，再執行：

```bash
JUDGMENT_QDRANT_COLLECTION=zhiyan_legal_judgments_v2 \
zhiyan-judgment-rag rebuild-index
```

若沿用原 collection，程式會拒絕啟動；若新名稱已含向量，也會拒絕採用。重建中狀態為
`rebuild_pending`，完成前拒絕查詢部分索引；失敗時可用同一設定重跑。舊 collection
不會自動刪除，完成驗收與備份後再由管理者處理。

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

`POST /api/chat` 可明確啟用本地判決檢索，並把通過 manifest 有效版本檢查的
Qdrant 切片綁定為 canonical `Claim`／`Evidence`／`Citation`：

```json
{
  "message": "毒品案件再犯期間如何判斷？",
  "task": "RESEARCH",
  "use_judgments": true,
  "judgment_top_k": 5,
  "judgment_year": ""
}
```

`use_judgments` 只允許搭配 `task=RESEARCH`。檢索在工作執行緒進行，不阻塞
FastAPI event loop；索引未就緒會回傳 HTTP 503。找不到同時具有原文、裁判日期與
來源定位的切片時，證據閘門會回 `ASK`，不會呼叫模型或虛構引註。

`citations` 欄位回傳來源標題、JID／切片定位、精確原文、裁判日期與驗證狀態。
語意檢索只證明「找到了這段原文」，不證明判決適用於個案，因此標記為
`PARTIAL`／`NEED_CHECK`，仍須人工覆核案件事實與法律適用。
模型請求只會把這批引註當成不受信任的資料，並明確禁止在引註清單為空時虛構來源。

API 同步產生的 `source_url` 會使用實際設定的 `JUDICIAL_API_BASE_URL` 再加上
`/JDoc`，因此透過受控 proxy 或測試端點同步時，不會誤標成正式 API 位址。若同一 JID
的來源端點改變，即使判決全文 hash 相同，也會重新發布 Qdrant payload，避免 SQLite
與向量搜尋結果顯示不同來源。歷史 JSONL 沒有執行期 client，預設仍標示司法院正式
JDoc 端點。

## 同步規則

司法院官方規格指出，同一 `JID` 代表同一筆裁判書；後續同一 `JID` 的內容應覆蓋先前版本。若官方回覆判決已移除或不再公開，本專案會刪除該 JID 的向量點。建議在 API 開放時段執行 `sync-changes`，並保留每次執行的輸出與 manifest 備份。

確認撤下時，live manifest 會立即清空該 JID 的全文、內容 hash、案件 metadata、
PDF／來源連結及切片，只保留 JID、`removed_at`、狀態與原因等稽核欄位。
向量刪除失敗會標記為 `removal_pending`，該次不計入成功移除；相同撤下資料
下次同步會重試，成功後改為 `removed`。撤下後若官方重新公開，即使內容相同
也會重新建立切片與向量。

這項流程只清理 live SQLite 與 Qdrant，不會回頭修改既有備份、匯出檔或應用層快取。
部署時應為判決資料設定受控保存期限，限制備份權限，並在還原後先套用最新 tombstone
再開放查詢；API／前端快取也應依 JID 失效，避免從舊快取重新顯示已撤下全文。
若必須保留撤下前快照供內部稽核，應放在獨立受控儲存區，不得重新匯入檢索集合。

## 本地 Qdrant 回歸驗證

可先用合成判決與固定測試向量驗證儲存行為，不需下載嵌入模型或提供司法院帳密：

```bash
python -m pip install -e '.[test]' 'qdrant-client>=1.10.0'
PYTHONPATH=src python -m pytest \
  tests/test_judgment_resources.py \
  tests/test_judgment_qdrant_integration.py \
  tests/test_judgment_answer_context.py \
  tests/interfaces/test_chat_judgment_retrieval.py \
  tests/test_judgment_index_fingerprint.py -q
```

測試在暫存目錄實際建立 Qdrant 本地儲存與 SQLite，涵蓋版本更新、保留其他 JID、
刪除失敗、批次已寫入但回覆失敗後重跑，以及關閉後重新開啟與查詢。
錯誤由測試注入，沒有連線至 Qdrant Server 或司法院；這不代表真實嵌入品質、
網路故障或正式主機驗收通過。未安裝 `qdrant-client` 時，Qdrant 測試模組會明確跳過。

自行建立 `JudgmentRagIndex` 時須在 `finally` 呼叫 `index.close()`，以釋放 Qdrant
及 SQLite。直接使用 `JudgmentVectorStore` 時也須呼叫 `store.close()`。
關閉 Qdrant 發生錯誤時，索引仍會嘗試關閉 SQLite，並讓錯誤傳回呼叫端。
這項修補針對已成功建立的索引；初始化失敗與多執行緒生命週期仍待獨立驗收。

## 安全邊界

這個向量庫是法律研究與引用檢索工具，不代表檢索到的判決必然適用於個案。回答層仍應保留裁判日期、法院、案號、原文切片與官方來源，並做現行有效性、案件事實與引用內容的人工覆核。

## 官方資料來源

- [司法院裁判書開放 API 規格說明](https://opendata.judicial.gov.tw/api/Newses/42/file)
- [司法院資料開放平台開發指引](https://opendata.judicial.gov.tw/DevelopmentGuide)
- [司法院裁判書批次資源分類](https://opendata.judicial.gov.tw/data/api/rest/categories/051/resources)

所有官方資料的使用仍應遵循司法院當期公告、授權條款與個資／隱私要求。
