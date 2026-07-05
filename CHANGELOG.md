# Changelog

All notable changes to **zhiyan-legal** are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### 🟢 Features

- **助教人格 v1.2.0**：啟動前檢查拆分兩層、新增換算公式與範例、合併全域約束、新增不確定退路（⚠️ 需核查不計口分）、用語修正、重疊規則合併

### 🟡 Improvements

- **版本號三方對齊**：pyproject.toml → v3.7.2，CITATION.cff → v3.07.2，與 git tag 一致
- **依賴管理補強**：新增 committee/test 兩個 optional group（google-genai, PyYAML, requests, pytest, pytest-cov）
- **Badge 一致化**：Tests 122→123
- **清理已追蹤的實驗殘檔**：移除 7 個 results/exp-citation-ablation-* 目錄
- **committee/README.md 路徑修正**：絕對路徑改為相對路徑

### 🧪 Testing

- 測試總數：122 → **123**（新增 1 個 committee test）

---

## [3.09] — 2026-07-05

### 🟢 Features

#### FEG 三層品質閘門建置

本版建置了全套　FEG（Final Evaluation Gate）三層閘門架構，涵蓋單模型、寫作人格、多模型合議三個層級的輸出品質控制。

**層級架構**：
```
L1 FEG_CORE_EXTREME   ← 第一層：SKILL.md 單模型輸出（法律邏輯）
FEG_WRITING           ← 第二層：LEGAL_WRITER 寫作人格文字品質
FEG_COMMITTEE         ← 第三層：多模型合議結果品質
```

- **SKILL.md → v3.09**：新增 `L1 FEG_CORE_EXTREME` 輸出品質閘門完整節段，含路由優先表、七維速查表（A:引用精確 ~ G:格式規範，含 S1–S5 錨點），層級流程圖更新，GLOBAL_CONSTRAINTS 第 5 條整合 FEG 優先規則、新增第 11 條強制執行條款
- **LEGAL_WRITER → v1.2.0**：新增 `FEG_WRITING` 輸出品質閘門，含七維評分速查表（A:文字精準 ~ G:排版格式）、路由優先表、旗標說明（StyleBreak/BH/QF/AMB/RM/FU）、雙層閘門執行順序圖
- **`committee/FEG_COMMITTEE.md` 新增**：多模型合議結果品質閘門完整規格，含 ConsensusLabel→FEG 映射表、七維評分速查表（A:引用一致 ~ G:報告格式）、BLIND_SPOT→STOP 行為明確規格（圖面最大空缺）、runner.py 整合規格（插入點 + CommitteeHaltError 事後類別）

### 🟡 Improvements

- **FEG 可移植性驗證**：七維評分架構証明可跨層級復用（法律 / 寫作 / 合議三層均七維，語意重映射即可適用）
- **BLIND_SPOT 行為補完**：現有 core.py 定義了標記但未定義觸發後行為，本版在 FEG_COMMITTEE.md 明確規定 5 條強制規則

### ⏳ 待執行（Next Steps）

- `committee/runner.py`：插入 `evaluate_feg_committee()` 閘門函數（規格已定義於 FEG_COMMITTEE.md）
- `committee/core.py`：新增 `CommitteeHaltError` 事後類別
- `committee/tests/`：補一暉 BLIND_SPOT→STOP 驗證測試案例

### 完整 Commit Index

| SHA | 說明 |
|:----|------|
| [`753964173f`](https://github.com/Lucien-1127/zhiyan-legal/commit/753964173f0deaf8fddec4902db9fbc9e89c994c) | feat(SKILL): v3.09 L1 FEG_CORE_EXTREME + 七維速查表 |
| [`1eff6b6f0b`](https://github.com/Lucien-1127/zhiyan-legal/commit/1eff6b6f0bc43141c288b59c5c2eb082ffe4de84) | feat(LEGAL_WRITER): FEG_WRITING 輸出品質閘門 + 七維評分速查表 v1.2.0 |
| [`019502ad1f`](https://github.com/Lucien-1127/zhiyan-legal/commit/019502ad1f8f0ec8d85be69796f49e8d92786928) | feat(committee): FEG_COMMITTEE 輸出品質閘門規格文件 v1.0.0 |

---

## [3.08] — 2026-07-02

### 🟢 Features

#### SKILL.md v3.08 — Hermes Skill Manifest 整合

- **SKILL-09 合約排版生成與校驗**：完整排版規範 v1.0，含頁面設定標準、字型字級規範、條款層次與縮排系統、金額與日期格式防窾改規則、排版校驗清單 LC-01~LC-15
- **SKILL-01 task_mode 新增 `contract` 模式**：合約、契約、NDA、審閱、起草、排版觸發
- **SKILL-03 新增 `LayoutChecker` 子代理**：合議庭四代理架構补完排版校驗局
- **GLOBAL_CONSTRAINTS 第 10 條**：排版校驗強制規則（LC-01 總 LC-15）
- **PART C 合約框架整合排版腳本路由**

### 🟡 Improvements

- **Benchmark v1.0 執行**：agnes-2.0-flash，6 題跨法域，平均分數 91.5/100
- **合約審閱評測初步數據**：Claude CLI 真實借款契約 92/100
- **引用格式統一**：v2.3.0，句尾上標格式
- **TASK_ROUTER CONTRACT_RISK 映射新增**：v1.1.0
- **C5.4 引用政策補完**：來源分級 VERIFIED / CROSS_REFERENCED / USER_REPORTED / NEED_CHECK

### 🔴 Known Issues

- **C5.4 測試 2/5 通過**：FreeLLMAPI 逾時與認證問題導致 T1/T3/T4 失敗，待 API 穩定後重測

### 完整 Commit Index

| SHA | 說明 |
|:----|------|
| [`594f3f3a`](https://github.com/Lucien-1127/zhiyan-legal/commit/594f3f3a69cf7a7da48715a5c415cd3408c6f603) | refactor: 統一引用格式為句尾上標 v2.3.0 |
| [`7c3f2f07`](https://github.com/Lucien-1127/zhiyan-legal/commit/7c3f2f0717dc04e4c939b4025cc4a6b1082617c1) | feat: TASK_ROUTER CONTRACT_RISK 映射 v1.1.0 |
| [`7a17f01e`](https://github.com/Lucien-1127/zhiyan-legal/commit/7a17f01e6e5babb0e706f5dc31bf0521da97ea84) | test: C5.4 驗證測試腳本（2/5 通過） |
| [`73dc0844`](https://github.com/Lucien-1127/zhiyan-legal/commit/73dc08447598dee41c7121a40f8c12437db1cee7) | fix: C5.4 來源分級對應規則 v2.2 |
| [`0abfb006`](https://github.com/Lucien-1127/zhiyan-legal/commit/0abfb006d48d70e2c6b2c99f6213fe63f2fe0b7a) | benchmark: 合約 7 題評測組（Claude CLI） |
| [`d30ef7073`](https://github.com/Lucien-1127/zhiyan-legal/commit/d30ef7073c2c2155790dbc03fe9795178f2cd35a) | ref: 去敏借款契約範本（22條+9風險標記） |

---

## [3.07.1] — 2026-06-26

### 🔴 Bug Fixes — P1 (Critical)

- **LICENSE 補上**：根目錄新增標準 MIT License（2026, Lucien），與 README badge / CITATION.cff 聲明一致。
- **律師法條號修正**：RESEARCH.md §8 原引 Art. 48（事務所型態定義）改為 Art. 127（非律師訴訟業務刑責），經全國法規資料庫查證確認。
- **judicial_api parser 重構**：`parse_case_number` 改為「劑 court name → 劑年度 → parse 字別號次」三步驟，解決連續格式（無空格案號）下 regex 貪婪吞食法院名和年度的問題。
- **test_judicial_api.py**：`test_parse_full_case` assertion 配合 COURT_CODES 鍵値修正 + 新增 6 個 edge case。

### 🟡 Improvements — P2 (High)

- 文件數與版本號統一、測試 badge 更新 81→122、README layout 更新、CHANGELOG 規範化。

### 🧪 Testing

- 測試總數：56 → 81 → 106 → **122**（全數通過）

---

## [3.07] — 2026-06-26

### 🟢 Features — P3 (Enhancement)

#### 子代理並行策略（sub_agent.py）
- 新增 `src/zhiyan_legal/sub_agent.py`：Hermes delegate_task 子代理排程模組，支援五種平行化模式。
- 新增 `docs/10_核心控制層/17_子代理並行策略.md`

#### 書狀格式規範與產生器
- 新增 `src/zhiyan_legal/doc_generator.py`、`docs/60_概念詞條/書狀格式規範.md`、`templates/民事書狀範本.docx`

#### 司法院裁判書開放 API 整合
- 新增 `src/zhiyan_legal/judicial_api.py`、對應文件與測試

### 🧪 Testing

- 測試總數：56 → **81 → 106**

---

## [3.06.1] — 2026-06-25

### 🔴 Bug Fixes — P1 (Critical)

- RESEARCH.md §3.1 架構層數修正、Citation Policy v2.1 對齊、manifest.py FIXME 標註

### 🟡 Improvements — P2 (High)

- runner.py MODEL_DEFAULT 更新、router.py RESEARCH 關鍵字新增「查詢」

---

## [3.06] — 2026-06-25

See [3.06.1] — this release was immediately followed by the patch. The v3.06 tag (`9ae2e86`) is the L0.8 feature milestone.

---

## [3.05] — 2026-06-21

### 🟢 Features

- SKILL.md v3.05：新增 L0.7 白話 RAG 優先檢索層（47,001 條，SQLite FTS5）、Citation v2.1 RAG 引用編號體系

---

## 2026-06-09 — Code Review Sprint

### 🔴 Bug Fixes — P1 (Critical)

- router.py 關鍵字衝突修正、單字邊界保護、LEGAL_WRITER 任務新增、預設 fallback 修正
- pyproject.toml build-backend 修正
- loader.py 遺失文件靜默忽略修正

### 🟡 Improvements — P2 (High)

- runner.py API 錯誤處理、dry-run token 估算、setup.sh cd 路徑修正、全域 print() → logging

### 🟢 Features — P3 (Enhancement)

- router.py describe_route() LEGAL_WRITER 描述、manifest.py ZHIYAN_SKILL_DIR 環境變數、cli.py --list-tasks 、__main__.py

### 🧪 Testing

| Milestone | Tests | Passed |
|-----------|-------|--------|
| Before audit | 14 | 14 |
| After audit | **56** | **56** |

---

*Generated on 2026-07-05 · zhiyan-legal v3.09*
