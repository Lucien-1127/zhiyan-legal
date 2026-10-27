# PR 審查與失敗邊界

必要檢查仍叫 `review`，分支保護不變。審查流程使用 `pull_request_target`，因此工作流程只採用主分支已信任的版本，PR 不能竄改流程後取得 `ORCAROUTER_API_KEY`。

工作本身不把預設分支上的綠燈當成 PR 審查結果。它會取得 PR 最新提交 SHA，先在該提交發布 `review: pending`，第三方審查完成後再發布 `success` 或 `failure`。只有 PR 最新提交上的 `review` 成功，才能滿足既有合併規則。

自動審查限同儲存庫、非草稿、作者關係為 OWNER／MEMBER／COLLABORATOR 的開啟中 PR。前置檢查不下載、不 checkout，也不執行 PR 程式；外部 fork、非可信作者、缺少金鑰或其他不合資格情況都不得進入第三方審查。

維護者原有的 `/orcacode-review` 與 `@orcacode-review` 指令保留，同樣拒絕外部 fork。留言觸發時也會把結果寫回該 PR 最新提交；如果 PR 在執行期間又有新提交，舊 SHA 的結果不能替代新版驗收。

第三方 Action 固定完整提交，引擎固定 1.3.13；P0／P1 問題與過大差異維持阻擋。設定 4 個並行、引擎 10 分鐘、工作 20 分鐘上限；這不是金額上限，供應商金鑰仍應設定錢包額度。

真實審查依賴 `ORCAROUTER_API_KEY` 與外部服務，失敗保持紅燈。未經知情同意，不應啟用或觸發會把私有程式碼傳往第三方的流程。AI 程式審查不取代功能、資料或正式部署驗收。

## 已取得的錯誤證據

CineAgent run 35519395418 的 GitHub 原始註記：
`This workflow run required approval but was not approved before it expired.`
中文：工作需要核准，但在核准前已到期。該次沒有進入審查，不能診斷為金鑰或模型問題。

智研 PR #13 先前只有三個 Python 成功檢查，main 分支另要求 `review`。本次保留同名狀態並修正它的來源與目標提交，沒有降低合併保護。

- https://github.com/Lucien-1127/CineAgent/actions/runs/35519395418
- https://github.com/Continuum-AI-Corp/orca-code-review/tree/6d253e0399c84848fedc8801176d6bea77817762
