# Changelog

All notable changes to **zhiyan-legal** are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

...

---

## [3.06.1] — 2026-06-26

### 🟢 Features — P3 (Enhancement)

#### 子代理並行策略（sub_agent.py）
- **新增 `src/zhiyan_legal/sub_agent.py`**：Hermes delegate_task 子代理排程模組，支援五種平行化模式：
  - `parallel_citation_verify()`：條文 + 判決 + 實務文章三路並行查詢
  - `courtroom_parallel()`：法官/檢察官/辯護人三方獨立準備
  - `type_s_review()`：獨立 QA 子代理進行 TYPE-S 審查
  - `parallel_legal_research()`：按法域拆給專門子代理
  - `parallel_rag_online()`：本地 RAG + 聯網平行查詢
- **新增 `docs/10_核心控制層/17_子代理並行策略.md`**：策略設計文件，含五個並行機會分析與加速比計算

### 完整 Commit Index

### CHANGELOG 更新（v3.07 entry）

| SHA | 說明 |
|:----|------|
| `0d9ce16` | feat: 子代理並行策略 v1.0 — sub_agent.py + 設計文件 |
| `8983569` | test: 子代理並行策略測試 25 個（總測試 106） |

### 🟢 Features — P3 (Enhancement)

#### 書狀格式規範與產生器
- **新增 `src/zhiyan_legal/doc_generator.py`**：法院合規書狀產生器，符合民事訴訟書狀規則 §3（114/08/29 修正）：
  - A4 紙張 / 2.5cm 邊界 / 標楷體 14pt / 固定行高 28pt / 頁碼置中
  - `add_title()` / `add_section_title()` / `add_body()` / `add_indent_body()` / `add_reference()`
- **新增 `docs/60_概念詞條/書狀格式規範.md`**：完整格式規範文件，含三來源聯網驗證（law.moj.gov.tw, judicial.gov.tw, cons.judicial.gov.tw）
- **下載司法院官方範本**：`templates/民事書狀範本.docx`
- **安裝 python-docx 1.2.0**：至 zhiyan-legal venv

#### 司法院裁判書開放 API 整合
- **新增 `src/zhiyan_legal/judicial_api.py`**：司法院資料開放平臺裁判書 API 客戶端，支援 Auth / JList / JDoc 三個端點，含法院代碼 37 個、案號解析、JID 組裝、錯誤處理
- **新增 `docs/60_概念詞條/司法院裁判書API整合.md`**：API 規格文件、使用說明、尚未完成項目
- **新增 `tests/test_judicial_api.py`**（10 個測試）：案號解析（4 cases）、JID 組裝（3 cases）、代碼完整性（2 cases）、非法輸入（1 case）

### 🧪 Testing

- **新增 `tests/test_sub_agent.py`**（25 個測試）：5 種平行化模式的 task 結構驗證、edge case（空條號/空法域/空白草稿）、mock hermes_tools.delegate_task 的呼叫慣例。**全覆蓋 25/25 通過。**
- 測試總數：56 → 81 → 106 → **116**（6/9 審查 56 → 6/26 維護 81 → 子代理 106 → 今天 116）

---

## [3.06] — 2026-06-25

### 🔴 Bug Fixes — P1 (Critical)

#### 架構文件一致性
- **RESEARCH.md §3.1**：「Five-Layer Architecture」→「Seven-Layer Architecture」，補入 L0.7 LOCAL_RAG 及 L0.8 CASE_VERIFY 兩層。
- **Citation Policy v2.0 → v2.1**：`30_引用政策_CITATION_POLICY_v2.0.0.md` 新增 [T1][T2] RAG 來源引用格式，與 SKILL.md 的 Citation v2.1 對齊。（檔名保留 v2.0.0 因 26 處跨文件引用，避免破壞既有連結）
- **manifest.py**：LEGAL_WRITER 層標註 FIXME，說明目前無獨立書狀起草文件，暫時指向訴訟策略模組。

### 🟡 Improvements — P2 (High)

- **runner.py**：`MODEL_DEFAULT` 由 `"gpt-5.1"` 改為 `"deepseek-v4-flash"`，與目前主要測試模型一致。
- **router.py**：RESEARCH 關鍵字新增「查詢」。

### 🟢 Features — P3 (Enhancement)

- **Citation Policy**：尾部新增「來源引用對照」表，排除引用來源混亂。

### 完整 Commit Index

| SHA | 說明 |
|:----|------|
| `05510d8` | v3.06.1: fix: 架構審查 6 項修正 |
| `9ae2e86` | v3.06: feat: 新增 L0.8 實務案例驗證層 (previous) |

---

## [3.05] — 2026-06-21

### 🟢 Features — P3 (Enhancement)

#### SKILL.md
- **v3.05 升級**：新增 L0.7 白話 RAG 優先檢索層（47,001 條法條白話翻譯，SQLite FTS5 本地檢索，零套件依賴）。
- **Citation v2.1**：新增 RAG 引用編號體系 `[T1][T2]…`，與聯網 `[1][2]…` 區分。
- **引用優先順序**：白話 RAG [T1] ＞ 聯網官方條文 [1] ＞ 判決書 [2] ＞ 學術 [3]。
- **每日自動 sync**：Google Sheets 資料庫每日凌晨 3:00 自動同步重建索引。

#### docs/
- 系統架構新增 L0.7 層：SRP → L0 → L0.7 RAG → MODE_ROUTER → 功能模組 → Citation v2.1。

### 完整 Commit Index

| SHA | 說明 |
|:----|------|
| `e8aed3d` | sk: feat: 智研RAG整合 v3.05 (hermes-skills) |

---

## [3.04] — 2026-06-09

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

---

## [3.03] — 2026-05-27

Initial public release with core architecture, routing, and documentation framework.
