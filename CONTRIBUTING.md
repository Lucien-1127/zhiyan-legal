# 貢獻指南 · Contributing

感謝你協助改善智研。這是一個法律 AI 研究框架；可重現性、來源定位與安全邊界比功能數量更重要。

## 適合的貢獻

- 可重現的錯誤與最小測試案例
- 法規、裁判、引用或時效性驗證修正
- 路由、主張－證據綁定與合議庭機制改善
- 安裝、CLI、API、文件與開發者體驗改善
- 不含個資且授權清楚的 benchmark／評估資料

若變更會改變法律判斷規則、資料授權、公開 API 或整體架構，請先建立 issue 說明問題、證據、風險與替代方案。

## 開發環境

```bash
git clone https://github.com/Lucien-1127/zhiyan-legal.git
cd zhiyan-legal
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
```

需要完整功能：

```bash
python -m pip install -e ".[all]"
```

## 驗證

提交前至少執行與變更相關的測試。完整的無金鑰測試與 CI 對齊：

```bash
python -m pytest tests/ --tb=short \
  --ignore=tests/test_c54_validation.py \
  --ignore=tests/run_ablation_v8_committee.py \
  -m "not integration"

zhiyan-legal "測試查詢" --dry-run --output json
```

套件或 metadata 變更另執行：

```bash
python -m pip install build
python -m build
```

不要宣稱測試通過，除非附上實際執行命令與結果。

## 法律與研究資料規則

1. 不提交真實當事人的姓名、聯絡方式、完整案號或其他可識別資料。
2. 新增法規或裁判主張時，附官方 URL、資料日期及可定位段落。
3. 區分「引用格式正確」、「來源存在」與「來源支持主張」三件事。
4. 模型輸出不能直接當 ground truth；需以官方法源、人工標註或明示的評估規則驗證。
5. 新增 benchmark 時，說明資料來源、授權、抽樣方法、排除條件與已知限制。
6. 不在 issue、測試 fixture、log、commit 或文件中加入 API key、token 或密碼。

## 開發流程

1. 從 `main` 建立短期分支，例如 `fix/citation-parser` 或 `docs/quickstart`。
2. 先新增會失敗的測試，再實作行為變更；純文件修正除外。
3. 保持變更聚焦，不在同一 PR 混入無關重構。
4. 使用 Conventional Commits，例如：

```text
fix(router): avoid safety false positive in compound words
docs: replace duplicated README quickstart
test(verification): cover expired regulation evidence
```

5. PR 需說明：問題、方案、驗證方式、風險與未完成項目。

## Issue 回報資訊

Bug 或幻覺案例請盡量附上：

- 智研 commit／版本
- Python 與作業系統版本
- 執行命令與路由模式
- 是否為 dry-run、mock 或真實 provider
- 已移除秘密與個資的最小輸入
- 實際結果、預期結果與判斷依據
- 若涉及法律內容，附官方法源與查詢日期

請勿公開 API key 或未匿名化的個案文件。安全問題依 [SECURITY.md](SECURITY.md) 私下回報。

## Review 原則

維護者會優先檢查：

- 是否有可重現證據與測試
- 是否維持向後相容或清楚說明 breaking change
- 是否誇大法律正確性、研究結果或多模型共識
- 是否增加資料、隱私、成本或供應商鎖定風險
- 文件、CLI 與實際行為是否一致

提交貢獻即表示你同意依本專案的 [MIT License](LICENSE) 授權該貢獻。
