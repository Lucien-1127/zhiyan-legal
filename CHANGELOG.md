# Changelog

All notable changes to **zhiyan-legal** are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased] — 2026-06-09

This session covers a single intensive code-review sprint.
All changes were reviewed, implemented, and verified on the `main` branch.

### 🔴 Bug Fixes — P1 (Critical)

#### `router.py`
- **關鍵字衝突修正**：`比對` 原同時存在於 `QC` 與 `RESEARCH`，造成不確定路由行為；移出 `RESEARCH`，保留於 `QC`（改為 `核對比對`）。
- **單字邊界保護**：單字關鍵字 `告`、`殺` 在正常詞語中（如「報告」、「抹殺」）會誤觸 `LITIGATION`/`SAFETY`；`告` 改為複合詞（`告人`/`告他`/`提告`/`被告`/`告訴`/`控告`），`殺` 加入邊界保護邏輯（前後皆為中文字時不匹配）。
- **新增 `LEGAL_WRITER` 任務**：補上起草、合約、律師函、訴狀、法律文書、契約等 6 個觸發詞。
- **預設 fallback 修正**：`default` 由 `"QC"` 改為 `"CONSULTANT"`，符合無關鍵字問句的真實使用情境。

#### `pyproject.toml`
- **`build-backend` 修正**：`setuptools.backends._legacy:_Backend`（私有 API）改為 `setuptools.build_meta`。

#### `loader.py`
- **遺失文件靜默忽略**：`compose()` 中 `missing` 變數僅收集但從未使用，改為 `warnings.warn()` 發出警告。

### 🟡 Improvements — P2 (High)

#### `runner.py`
- **API 錯誤處理**：`client.chat.completions.create()` 加入 `try/except`，捕獲 `400/429/500` 及空 `choices`，避免 crash。
- **dry-run token 估算**：`split()` 改為 `count_tokens()`（`len // 4`），對中文不再嚴重低估。

#### `setup.sh`
- **`cd` 路徑錯誤**：`cd "$SCRIPT_DIR"` 解析到 `scripts/` 子目錄，導致找不到 `requirements.txt`；改為 `cd "$PROJECT_ROOT"`。

#### 全域
- **`print()` → `logging`**：`runner.py`、`manifest.py` 加入 `logging.getLogger("zhiyan_legal")`；CLI 新增 `--verbose` 開啟 `DEBUG` 層級輸出。

### 🟢 Features — P3 (Enhancement)

#### `router.py`
- `describe_route()` 新增 `LEGAL_WRITER` 描述：`"合約起草 (Legal Writing)"`。

#### `manifest.py`
- `SKILL_DIR` 支援 `ZHIYAN_SKILL_DIR` 環境變數覆寫，解除對 `.hermes/` 路徑的硬編碼依賴。

#### `cli.py`
- 新增 `--list-tasks` 參數，列出所有支援的任務類型與對應範例關鍵字。
- 新增 `__main__.py`，支援 `python -m zhiyan_legal` 直接執行。

#### 清理
- 刪除根目錄殘留空檔案 `=1.0.0`。

### 🧪 Testing

#### `tests/test_routing.py`（+7 cases）
- 修正 `test_mixed_qc_research` docstring 自相矛盾（說明文字與 assert 方向相反）。
- 修正 `test_default_qc` docstring 更新為「預設 CONSULTANT」。
- 新增 LEGAL_WRITER 觸發測試（4 cases）：合約、律師函、訴狀、法律文書。
- 新增 `test_qc_verification`：驗證 `核對比對` → `QC`。
- 新增邊界保護測試（6 cases）：`報告` 不觸 LITIGATION、`告他`/`被告` 正確觸發、`抹殺` 不觸 SAFETY、`殺人` 正確觸發、`調查` 仍為 RESEARCH。

#### `tests/test_loader.py`（new — 9 cases）
- `load_file()`：frontmatter 剝離、無 frontmatter、前後空白 strip。
- `compose()`：多文件串接、標頭插入、遺失文件警告、截斷邏輯（精確長度斷言）、空檔案跳過。
- `count_tokens()`：`len // 4` 估算驗證。

#### `tests/test_manifest.py`（new — 22 cases）
- `Layer` dataclass 結構驗證。
- `CORE_LAYERS` 完整性（數量 8、名稱、檔案）。
- `TASK_LAYERS` 任務覆蓋（含 LEGAL_WRITER 新增驗證）。
- `EXCLUDED_DIRS` / `EXCLUDED_FILES` 格式。
- `resolve_doc()`：正常路徑 + `FileNotFoundError`（monkeypatch tempfile）。
- `get_load_order()`：排序、去重、預設 QC、未知 task fallback。

### 📊 Coverage Milestone

| Milestone | Tests | Passed |
|-----------|-------|--------|
| Before audit | 14 | 14 |
| After audit | **56** | **56** |

Covered modules: `router`, `loader`, `manifest`.

### Commit Index

| SHA | Description |
|-----|-------------|
| [`557ff08`](https://github.com/Lucien-1127/zhiyan-legal/commit/557ff08) | merge: 架構改進全部到位 |
| [`a1b27ae`](https://github.com/Lucien-1127/zhiyan-legal/commit/a1b27ae) | 架構改進：邊界保護、logging、API 錯誤處理、--list-tasks |
| [`7d41faa`](https://github.com/Lucien-1127/zhiyan-legal/commit/7d41faa) | test: 新增 test_manifest.py（22 個測試） |
| [`1cbab97`](https://github.com/Lucien-1127/zhiyan-legal/commit/1cbab97) | fix: test_compose_truncation 斷言改為精確長度檢驗 |
| [`670735d`](https://github.com/Lucien-1127/zhiyan-legal/commit/670735d) | test: 補上 LEGAL_WRITER/loader 測試 + default 改為 CONSULTANT |
| [`1d9132e`](https://github.com/Lucien-1127/zhiyan-legal/commit/1d9132e) | merge: 程式碼審查 7 項問題修正 |

---

*Generated on 2026-06-09 · zhiyan-legal code review sprint*
