# PR 審查與失敗邊界

GitHub 分支保護仍要求 `review`。工作流程由維護者發出明確的 PR 留言指令後才執行。GitHub 的 `issue_comment` 事件使用預設分支上的工作流程，開啟或更新 PR 不會自動觸發外部審查。

工作流程先讀取 PR 的最新提交 SHA，對該 SHA 發布 `review: pending`。第三方審查結束後發布 `success` 或 `failure`。新提交須取得自己的成功狀態。

維護者可使用 `/orcacode-review` 或 `@orcacode-review`。PR 須為同一儲存庫、開啟中且非草稿。前置驗證只讀取 GitHub 事件與 API，不 checkout 或執行 PR 程式。外部 fork、不具權限的留言者與缺少金鑰等情況會被拒絕。

第三方 Action 固定完整提交，引擎固定 1.3.13；P0／P1 問題與過大差異維持阻擋。設定 4 個並行、引擎 10 分鐘、工作 20 分鐘上限；這不是金額上限，供應商金鑰仍應設定錢包額度。

真實審查依賴 `ORCAROUTER_API_KEY` 與外部服務，失敗保持紅燈。未經知情同意，不應啟用或觸發會把私有程式碼傳往第三方的流程。AI 程式審查不取代功能、資料或正式部署驗收。

## 已取得的錯誤證據

CineAgent run 35519395418 的 GitHub 原始註記：
`This workflow run required approval but was not approved before it expired.`
中文：工作需要核准，但在核准前已到期。該次沒有進入審查，不能診斷為金鑰或模型問題。

智研 PR #13 先前只有三個 Python 成功檢查，main 分支另要求 `review`。本次保留同名狀態並修正它的來源與目標提交，沒有降低合併保護。

- https://github.com/Lucien-1127/CineAgent/actions/runs/35519395418
- https://github.com/Continuum-AI-Corp/orca-code-review/tree/6d253e0399c84848fedc8801176d6bea77817762

## GitHub 第一方審查證據驗證

`Verify independent review evidence` 從 GitHub API 讀取 PR、提交、正式審查及 Review Threads。流程驗證來源儲存庫、工作流程 ref、PR 編號、基底與最新 head SHA。僅 checkout 受信任工作流程的 SHA，工作權限為唯讀。

維護者可在工作流程已進入受信任分支後執行 `workflow_dispatch`，或在 PR 留言 `/verify-review`。同儲存庫的 PR 推送新提交時也會重新驗證。變數 `INDEPENDENT_REVIEWER_IDS` 由管理者設定，接受空白分隔的 GitHub 數字使用者 ID。開放前須實際確認獨立性並逐一核對儲存庫權限。

獨立審查者須對**當前 head** 提交 GitHub 正式核准，並在審查本文記錄以下各區段的具體證據。一般 Conversation 留言、測試綠燈及舊 SHA 核准皆無法完成驗證。

```markdown
## 程式邏輯
## 安全漏洞
## 回歸風險
## 測試覆蓋
## 架構一致性
## Review Threads
```

對智研法律系統的變更，應核對 CIT-01 到 CIT-12、臺灣一手來源、法規版本與法律時點、原文、canonical Claim／Evidence、Qdrant／SQLite 一致性、ASK／SAFE 和 API 契約、索引 v3 遷移、憑證處理及 Git 歷史。司法院 API、遠端 Qdrant、正式模型及部署分別記錄實際驗證狀態。

`PASS` 對應完整、獨立且當前的 GitHub 證據。未解 thread、要求修改、提交者核准自身變更或未知同名 `review` 屬於 `FAIL`。缺少或過期的核准、API 錯誤與權限不足屬於 `BLOCKED`。核准後再讀取 PR、審查和 threads 以攔截驗證期間的更新。

### 安全導入

本流程的 Actions 工作名稱為 `Independent review evidence`。它目前只輸出驗證裁決，無法寫入必要的 `review`。目前 `review` 允許 `Any source`，上線前須另核准專用 GitHub App 作為唯一可信的狀態來源。僅將 `review` 綁到共用的 GitHub Actions App 仍無法區分來源工作流程。

可透過同儲存庫內由管理者控制的受保護分支導入發布器。限制該分支及其 GitHub Actions environment 的變更與密鑰存取。發布器由版本固定的驗證器讀取 GitHub 即時證據，只能對相同且當前的 head 發布 `review`。改變來源前，須保留三個必要 Python 檢查及其 GitHub Actions 來源，並確認審查撤銷與新阻塞 thread 會被原生保護或可信發布器攔截。無法確認時合併維持阻塞。

設定來源、建立 App、發布狀態與啟用工作流程皆須經正式驗收。回滾可停用新驗證工作流程並撤銷專用 App 授權，必要 `review` 會繼續阻擋合併。OrcaCode 維持停用。

離線驗證指令為 `python -m pytest tests/contract/test_verify_review.py -vv`。
