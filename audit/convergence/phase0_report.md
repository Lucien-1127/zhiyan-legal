# Phase 0 收斂報告 — zhiyan-legal（正式版）

- Repository: Lucien-1127/zhiyan-legal @ main b68c75f
- 日期：2026-08-24
- 模式：五份互相獨立 Read-only Audit → Z0-NORMALIZE → Phase 0 Gate
- 狀態：**Phase 0 完成。Gate 判定：BLOCKED（詳見第五節）。未開始 Phase 1，等待 Acceptance。**
- 未修改任何既有檔案；`audit/convergence/` 為唯一新增產出。

---

## 一、Audit 執行紀錄

| Task | 角色 | 執行方式 | 結果摘要 |
|---|---|---|---|
| Z0-A | Repository Inventory & Static Analysis | API 子代理（DeepSeek 任務書） | 25 項盤點＋Canonical Model 搜尋＋import graph |
| Z0-B | Contract Gap & Consistency Reviewer | API 子代理（Gemini 任務書）＋Drive 規格本地化 9 檔 | Traceability Matrix 24 項，alignment **22/100** |
| Z0-C1 | Independent Architecture Reviewer | API 子代理（OpenRouter 主審） | architecture_status = **FRAGMENTED** |
| Z0-C2 | Adversarial Architecture Reviewer | API 子代理（C1 完成後派出，獨立分析後才比較） | 對主張 a-d 全 AGREE、零 false positive、4 新 critical |
| Z0-D | Senior Architecture Reviewer | **agy CLI（Gemini Pro 會員會話）**，READ-only | 判定 **NOT_READY** |

Normalize 規則：合併 evidence 不計票、禁止模型投票、CONFIRMED 須可重現證據、無衝突產生（C1 截斷部分已由 C2 獨立複驗覆蓋）。

## 二、Finding Registry 摘要（共 18 項；完整版見 phase0_findings.json）

### CRITICAL ×4（全部 blocking）
| ID | 標題 | 報告者 |
|---|---|---|
| ZHIYAN-F-0001 | 五檔語法錯誤，主套件無法載入（engine/router/sub_agent/committee-runner/test_manifest） | A,B,C1,C2,D |
| ZHIYAN-F-0002 | Decision strictness 階層不存在；唯一 Verdict=PASS/FAIL/ERROR | A,B,C1,C2,D |
| ZHIYAN-F-0003 | /api/chat 直連 LLM 零 gate ＋ error 回 200 空內容（fake-success）；目前僅被語法錯誤「意外」擋住 | B,C1,C2,D |
| ZHIYAN-F-0004 | **真實格式 API key 拼接硬編碼於 committee/runner.py:28-30 並進入 git 歷史**（A 先行發現、C2 獨立複驗為有效金鑰） | A,C2 |

### HIGH ×8
F-0005 Drive 四契約與 9 Gate 零落地（22/100）｜F-0006 GovernanceContract 零呼叫點｜F-0007 policy marker 亂碼致 regex 永遠放行｜F-0008 雙套 judgment schema 分叉＋循環引用｜F-0009 runner stub 破損契約（3 個活躍消費者）｜F-0010 key discovery 三套互不知情＋讀個人 profile＋subprocess grep＋跨 provider fallback 配固定 base_url｜F-0011 engine 五項內部缺陷（load_docs 重複定義、sync 分支繞過驗證、history role 注入、key rotation 空操作、startup 非原子）｜F-0012 validate_output advisory-only＋失敗遮罩空清單

### MEDIUM ×5 / LOW ×1
F-0013 committee_core 死拷貝｜F-0014 12 處 sys.path hack／雙 namespace｜F-0015 CI workflow 事故＋紅燈仍 merge｜F-0017 domain→fastapi 反向依賴｜F-0016 版本號三方不一致＋README 拼接｜F-0018 死碼空殼群＋.db 追蹤

## 三、Cross-audit 一致性

- 主張 a-d 由 C2 獨立複驗：**全 AGREE、零 false positive**
- F-0004 secret 由兩個 audit 獨立確認（Z0-A 發現、Z0-C2 驗證金鑰格式有效性）
- 衝突物件：0（無 NEEDS_VERIFICATION conflict）
- Z0-B alignment score 22/100；Z0-C1 status FRAGMENTED（可收斂不需重寫）；Z0-D 判定 NOT_READY

## 四、AGY（Z0-D）核心交付

- Actual Core：src/zhiyan_legal/engine.py（執行核心，目前因語法損壞無法載入）＋docs/10_核心控制層（提示詞規格核心）——雙軌
- Do-not-delete List：judgment schema(src)、engine、manifest/loader、router、regulation_tracker/diff/api、judicial_api、committee core/normalizer/mapper、sdk/、INVARIANTS.md、data/articles、docs/、law_monitor_app/
- Legacy Candidates：runner.py（先補 shim）、根目錄 zhiyan_legal/（吸收差異後轉 shim）、committee_core/（deletion manifest 後移除）、backend/engine.py（暫留）、gen_nda_* 變體歸檔、regulation_tracker.db git rm --cached
- 最低風險收斂順序：止血修復→綠燈基準→雙軌消除→金鑰組態整合→契約程式化→北極星語意收斂
- Phase 1 驗收條件：ast.parse/compile 全綠、import 單向化、CI 單一乾淨流程全綠、dry-run 連通、版本錨定一致

## 五、Phase 0 Gate 判定（G0-01 ～ G0-10）

| Gate | 判定 | 依據 |
|---|---|---|
| G0-01 Baseline captured | **PASS** | 五份審計完成並入庫 |
| G0-02 Repository classified | **PASS** | Z0-A 全目錄 16 類分類標記 |
| G0-03 Canonical model duplicates identified | **PASS** | F-0008＋Z0-A duplicate_models 六組 |
| G0-04 Architecture gaps identified | **PASS** | Z0-B 24 項 matrix（score 22/100） |
| G0-05 Security findings identified | **PASS** | F-0004 secret＋F-0010/F-0011 注入面（secret detection 掃描其餘零命中） |
| G0-06 Do-not-delete list exists | **PASS** | Z0-D G節 12 項清單 |
| G0-07 Test baseline known | **PASS** | 測試基線已知：test_manifest 本身壞、router/engine 壞致必敗、committee/graphrag/backend 幾乎零覆蓋 |
| G0-08 No Repository modification occurred | **PASS** | 全程 READ-only；僅新增 audit/convergence/ 兩檔 |
| G0-09 Findings normalized | **PASS** | Finding Registry 18 項（ZHIYAN-F-0001~0018），衝突 0 |
| G0-10 Phase 1 scope can be bounded | **NEEDS_VERIFICATION** | Phase 1 範圍可界定（schemas+execution contract 種子已選），但 AGY 判定 NOT_READY：須先完成 Section F 止血（修語法+shim+CI）才能安全開工 |

### 最終判定：**BLOCKED**

原因：
1. ZHIYAN-F-0004（secret 已入 git 歷史）——依硬性規則 13，secret detection 為 merge blocker，且需要你立即到金鑰平台輪換該 Agnes key（本報告不記錄完整 key）。
2. Z0-D 判定 NOT_READY——主執行路徑語法中斷（F-0001）＋CI 失效無防護網（F-0015），Phase 1 重構缺乏安全基礎。
3. G0-10 為 NEEDS_VERIFICATION：待止血完成後重估。

### BLOCKED 解除條件（建議作為 Phase 0.5 止血任務包，交 Codex 執行）
1. 使用者側：撤銷輪換外洩的 Agnes keys。
2. Codex：修復五處語法錯誤（Z0-D F節有逐檔修法）。
3. Codex：runner.py 補 run_llm 相容 shim（包裝 query_sync）。
4. Codex：清理 test.yml 成單一乾淨流程＋啟用 branch protection（需 repo owner 於 GitHub 設定）。
5. 驗證：compileall 歸零＋pytest collection 通過＋CI 綠燈。
6. 完成後重跑 Gate → PASS → 核准 Phase 1。

---

**STOP. Phase 0 結束於 BLOCKED。不開始 Phase 1，等待你的 Acceptance 與止血授權。**
