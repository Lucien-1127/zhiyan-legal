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
