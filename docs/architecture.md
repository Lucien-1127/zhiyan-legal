# 智研 AI 法律系統 · 系統架構

> **Zhiyan AI Legal System — Eight-Layer Architecture**
>
> 從輸入到輸出的完整架構設計，涵蓋安全路由、事實閘門、RAG 檢索、判決驗證、型態系統、委員會品質閘門、模式路由、人格層與引用政策。

---

## 一、架構總覽

```
使用者輸入（User Input）
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│  L0.5  SRP          安全路由協議 (Safety Routing Protocol)    │
│        RL0─RL3      風險分級、高風險分流、緊急轉接            │
└───────────────────────┬──────────────────────────────────────┘
                        │  Safe
                        ▼
┌──────────────────────────────────────────────────────────────┐
│  L0    CORE_GATE     核心閘門 (Fact Gate)                     │
│        A/B/C 分級    事實提取、缺口偵測、五要素分析           │
│        ※ A/B/C = 事實明確度分級（非風險分級）               │
└───────────────────────┬──────────────────────────────────────┘
                        │  Verified
                        ▼
┌──────────────────────────────────────────────────────────────┐
│  L0.7  LOCAL_RAG     本地 RAG 檢索                           │
│        FTS5 全文搜尋  47,001 條法條白話摘要                   │
└───────────────────────┬──────────────────────────────────────┘
                        │  + Statute Context
                        ▼
┌──────────────────────────────────────────────────────────────┐
│  L0.8  CASE_VERIFY   判決書驗證層                            │
│        司法院 API    判決書查詢、實務見解比對                │
└───────────────────────┬──────────────────────────────────────┘
                        │  + Case Precedent
                        ▼
┌──────────────────────────────────────────────────────────────┐
│  L0.9  TYPE-S        型態系統 (Type System)                   │
│        單選/多選/申論/案例   輸出格式校驗                    │
│        ※ 原 L0.8 TYPE-S，為避免層號衝突升為 L0.9            │
└───────────────────────┬──────────────────────────────────────┘
                        │  + Type-Validated
                        ▼
┌──────────────────────────────────────────────────────────────┐
│  L0.95 COMMITTEE     多模型合議品質閘門                       │
│        FEG_COMMITTEE  CONSENSUS/DISAGREEMENT/BLIND_SPOT      │
│        runner.py 平行執行 Agnes×2 + Gemini                   │
└───────────────────────┬──────────────────────────────────────┘
                        │  Consensus / DLV
                        ▼
┌──────────────────────────────────────────────────────────────┐
│       MODE_ROUTER    模式路由                                 │
│        QC / RESEARCH / REPORT / CONSULTANT / TUTOR / TA     │
│        LITIGATION / COURTROOM / LEGAL_WRITER / WRITER       │
│        PROMPT_ENGINEER / SAFETY / CONTRACT                  │
│        依任務類型選擇人格與輸出格式                          │
└───────────────────────┬──────────────────────────────────────┘
                        │  Routed
                        ▼
┌──────────────────────────────────────────────────────────────┐
│  L1    PERSONA        人格層 (Persona Layer)                  │
│        核心 6 種：MASTER / CONSULTANT / TUTOR / WRITER       │
│                   TA / LEGAL_WRITER                         │
│        擴充 2 種：PROMPT_ENGINEER / SENTINEL                 │
└───────────────────────┬──────────────────────────────────────┘
                        │  Persona-Adapted
                        ▼
┌──────────────────────────────────────────────────────────────┐
│  L2    CITATION v2.1  引用政策 (Citation Policy)              │
│        [T1] 本地白話 RAG  [1] 聯網法規  [2] 判決  [3] 學術  │
│        ※ 統一採用 SKILL.md Citation v2.1 標記定義            │
│        強制不虛構、不可查證標示「待查」「推論」              │
└───────────────────────┬──────────────────────────────────────┘
                        │  + Citations
                        ▼
┌──────────────────────────────────────────────────────────────┐
│  G0    OUTPUT         信心宣告 + 最終輸出                     │
│        Confidence-first  低信心 → 中止                       │
└──────────────────────────────────────────────────────────────┘
```

---

## 二、層級詳解

### 2.1 L0.5 — SRP 安全路由協議（Safety Routing Protocol）

**職責**：在進行任何法律分析之前，先評估輸入的風險等級。

```
輸入
  │
  ▼
┌─────────────────────┐
│  SRP Assessment     │
│  ┌───────────────┐  │
│  │ RL0: 一般法律  │  │ ← 正常法律問題，走標準流程
│  │ RL1: 敏感話題  │  │ ← 需附加免責聲明
│  │ RL2: 高風險    │  │ ← 需安全引導 + 資源轉介
│  │ RL3: 緊急      │  │ ← 直接轉接求助專線，中止分析
│  └───────────────┘  │
└─────────────────────┘
  │
  ├── RL0, RL1 ──→ CORE_GATE
  ├── RL2      ──→ CORE_GATE + 安全附註
  └── RL3      ──→ 緊急轉接（跳過法律分析）
```

| 風險等級 | 關鍵詞範例 | 處理方式 |
|:---------|:-----------|:---------|
| RL0 | 契約、民法、刑法、訴訟 | 正常法律分析 |
| RL1 | 離婚、監護權、遺產 | 附加情感關懷提示 |
| RL2 | 自傷、虐待、家暴 | 安全引導 + 資源轉介 |
| RL3 | 自殺、緊急、救命 | 直接轉接 1925/113/110 |

---

### 2.2 L0 — CORE_GATE 核心閘門（Fact Gate）

**職責**：事實分級、提取五要素、標示資訊缺口。

> ⚠️ **命名說明**：CORE_GATE 的 A/B/C 分級為**事實明確度分級**（A=明確/B=需查證/C=不足），與 G5 安全邊界的**風險等級**（Risk Tier A/B/C）命名相同但含義不同，請勿混淆。

```
A 級：事實明確且有直接法源 → 直接處理
B 級：需進一步查證       → 標示「待查」
C 級：資訊不足            → 要求補充資料
```

---

### 2.3 L0.7 — LOCAL_RAG 本地檢索層

**職責**：從本地法律知識庫中檢索相關法條，提供白話摘要與原文對照。

- SQLite FTS5 全文搜尋引擎，支援中文分詞（jieba）
- 47,001 條法律條文白話摘要
- 每日同步更新機制、信心排名 + 來源追溯
- 實作位置：`src/zhiyan_legal/loader.py`

---

### 2.4 L0.8 — CASE_VERIFY 判決書驗證層

**職責**：使用司法院開放資料 API 驗證判決書引用，補充實務見解。

```
1. 判決書查詢（Judicial API）
   ├── 關鍵詞 → 司法院裁判書查詢系統
   └── 支援：最高法院、高等法院、地方法院

2. 實務見解比對（交叉驗證）

3. 引用驗證
   ├── 確認判決確實存在
   └── 標示「已驗證」或「待查」
```

**API 整合細節**：`docs/60_概念詞條/司法院裁判書API整合.md`

---

### 2.5 L0.9 — TYPE-S 型態系統（Type System）

> ⚠️ **版本說明**：原編號 L0.8（與 CASE_VERIFY 衝突），自 v3.9.1 起升為 **L0.9**。

**職責**：根據任務型態，規範輸出格式與驗證標準。

| 型態 | 名稱 | 強制欄位 |
|:-----|:-----|:---------|
| `single_choice` | 單選題 | 選項列表、正確答案、解析 |
| `multiple_choice` | 多選題 | 所有正確答案、各項解析 |
| `essay` | 申論題 | 評分標準、範例答案、批改回饋 |
| `case_analysis` | 案例題 | 事實摘要、爭點、法條適用、結論 |

---

### 2.6 L0.95 — COMMITTEE 多模型合議品質閘門

> **新增於 v3.9.1**，解決原架構中 committee 系統與主流程完全脫鉤的問題。

**職責**：平行執行多模型，對法律結論進行共識驗證，作為進入 MODE_ROUTER 前的品質閘門。

**架構設計**：

```
TYPE-S 輸出
  │
  ▼
┌──────────────────────────────────────────────┐
│  L0.95 COMMITTEE                              │
│                                               │
│  平行執行：Agnes×2 + Gemini（runner.py）      │
│                                               │
│  FEG_COMMITTEE 七維閘門評估：                 │
│  A:引用一致 B:推理一致 C:覆蓋完整            │
│  D:任務對齊 E:共識品質 F:安全合規 G:報告格式  │
│                                               │
│  ConsensusLabel 路由：                        │
│  ├── CONSENSUS       → DLV → MODE_ROUTER     │
│  ├── DISAGREEMENT    → ASK（回報分歧）        │
│  ├── BLIND_SPOT      → STOP（CommitteeHalt） │
│  └── UNIQUE_INSIGHT  → VM 驗證流程           │
└──────────────────────────────────────────────┘
```

**實作位置**：`committee/runner.py`、`committee/core.py`、`committee/FEG_COMMITTEE.md`

**子代理協作（SKILL-03）**：
- `ClauseExtractor` — 條款拆解
- `RiskReviewer` — 風險評估
- `LegalVerifier` — 引用驗證
- `LayoutChecker` — 排版校驗（LC-01~LC-15）

---

### 2.7 MODE_ROUTER 模式路由

**職責**：根據任務類型決定工作模式，間接影響人格選擇與輸出風格。

> ⚠️ **v3.9.1 更新**：補齊全部 13 個模式（原文件僅列 6 個）。

| 模式 | 名稱 | 人格 | 觸發情境 |
|:-----|:-----|:-----|:---------|
| `QC` | 品質控制 | TA | 快速答案核查 |
| `RESEARCH` | 深度研究 | MASTER / CONSULTANT | 法律深度分析 |
| `REPORT` | 報告生成 | LEGAL_WRITER | 書狀文件生成 |
| `CONSULTANT` | 顧問諮詢 | CONSULTANT | 實務建議 |
| `TUTOR` | 教學輔導 | TUTOR | 法律知識教學 |
| `TA` | 助教批改 | TA | 作業評分 |
| `LITIGATION` | 訴訟推演 | MASTER + CONSULTANT | 攻防模擬 |
| `COURTROOM` | 法庭模擬 | MASTER + CONSULTANT | Court Simulation |
| `LEGAL_WRITER` | 書狀撰寫 | LEGAL_WRITER | 司法文書起草 |
| `WRITER` | 法律寫作 | WRITER | 法律文章、合約條款 |
| `PROMPT_ENGINEER` | 提示工程 | PROMPT_ENGINEER | 深度法律分析研究 |
| `SAFETY` | 安全處理 | SENTINEL | 高風險對話路由 |
| `CONTRACT` | 合約審查 | CONSULTANT + LEGAL_WRITER | 合約風險掃描 |

**實作位置**：`manifest.py` 中的 `TASK_MAP` 與 `router.py`。

---

### 2.8 L1 — PERSONA 人格層（Persona Layer）

**職責**：8 種法律人格（6 核心 + 2 擴充），各自擁有獨立的 system prompt、知識邊界與語氣規範。

> ⚠️ **v3.9.1 更新**：補入 `PROMPT_ENGINEER` 與 `SENTINEL` 兩種擴充人格（router.json 已引用但原文件未定義）。

**核心 6 種人格**：

| 人格 | 適合場景 | 語氣 | 專業深度 |
|:-----|:---------|:-----|:---------|
| **MASTER** | 複雜法律問題、訴訟策略 | 權威、精準 | 最高 |
| **CONSULTANT** | 合約審查、風險評估 | 實務、謹慎 | 高 |
| **TUTOR** | 法律教學、考試輔導 | 耐心、教育性 | 中高 |
| **WRITER** | 法律文章、契約條款 | 專業、流暢 | 中 |
| **TA** | 作業批改、評分反饋 | 建設性、明確 | 中 |
| **LEGAL_WRITER** | 書狀、起訴狀、答辯狀 | 正式、格式嚴謹 | 高 |

**擴充 2 種人格**（模式專屬角色）：

| 人格 | 適合場景 | 對應模式 | 備註 |
|:-----|:---------|:---------|:-----|
| **PROMPT_ENGINEER** | 深度法律研究、查詢優化 | `PROMPT_ENGINEER` (research) | router.json 已引用 |
| **SENTINEL** | 安全風險對話前置檢測 | `SAFETY` / `sentinel` | 42_模組定義 |

人格切換協議：
- 明確宣告切換：`/persona TUTOR`
- 自動模式路由：`RESEARCH → MASTER`
- 多人格協作：`LITIGATION → MASTER + CONSULTANT`

---

### 2.9 L2 — CITATION v2.1 引用政策

**職責**：強制引用規範，禁止虛構法條與判決。

> ⚠️ **v3.9.1 更新**：統一採用 SKILL.md Citation v2.1 標記定義，廢棄原 §2.8 的 [T]/[1]/[2]/[3] 舊定義。

**引用標記系統（Citation v2.1 統一版）**：

| 標記 | 來源類型 | 格式範例 |
|:-----|:---------|:---------|
| `[T1]` | 本地白話 RAG（優先） | `[T1] 民法第184條（白話摘要）` |
| `[1]` | 聯網官方法規 | `[1] 全國法規資料庫` |
| `[2]` | 司法院判決書 | `[2] 最高法院109年台上字第1234號` |
| `[3]` | 學術文獻 | `[3] 王澤鑑，《民法總則》` |

**引用優先順序**：`[T1]` 白話 RAG ＞ `[1]` 聯網法規 ＞ `[2]` 判決書 ＞ `[3]` 學術

**強制規則**：
1. 每條法律主張必須有對應引用標記
2. 不可查證的主張必須標示「待查」或「推論」
3. 違反不虛構原則 → 輸出中斷 + 審計記錄

**政策文件**：`docs/20_模式與引用層/30_引用政策_CITATION_POLICY_v2.0.0.md`

---

## 三、完整資料流

```
使用者：「刑法第271條殺人罪的構成要件是什麼？」

Step 1: L0.5 SRP   → RL0（一般法律問題）→ 通過
Step 2: L0  CORE_GATE → A 級（事實明確）
Step 3: L0.7 LOCAL_RAG → FTS5「刑法 第271條」→ 條文全文 + 白話
Step 4: L0.8 CASE_VERIFY → 最高法院相關判決要旨
Step 5: L0.9 TYPE-S  → essay 申論輸出格式
Step 6: L0.95 COMMITTEE → CONSENSUS → DLV
Step 7: MODE_ROUTER → RESEARCH → 人格 MASTER
Step 8: L1 PERSONA (MASTER) → 載入 system prompt
Step 9: L2 CITATION v2.1 → [T1] + [2] 格式化
Step 10: G0 OUTPUT → 信心宣告高 + 輸出
```

---

## 四、與外部元件的整合

### 4.1 提示工程（Prompt Engineering）

```
docs/
├── 10_核心控制層/          → G0, SRP, CORE_GATE, TYPE_S
├── 20_模式與引用層/        → MODE_ROUTER, CITATION_POLICY
├── 30_安全與治理層/        → 風險評分規則
├── 40_模組與人格層/        → 8 人格 system prompt
├── 60_概念詞條/            → 法律名詞定義
└── 90_維運治理/            → 冒煙測試、驗收標準
```

### 4.2 Committee 系統整合

```
committee/
├── runner.py          → 平行執行 Agnes×2 + Gemini
├── core.py            → ConsensusLabel 定義
├── mapper.py          → 結果映射
├── FEG_COMMITTEE.md   → 七維品質閘門規格
└── tests/             → committee 單元測試
```

整合協議：
1. COMMITTEE 的**輸入**來自 L0.9 TYPE-S 的輸出
2. COMMITTEE 的**輸出**（CONSENSUS/DLV）才進入 MODE_ROUTER
3. BLIND_SPOT → 觸發 CommitteeHaltError，不進入 MODE_ROUTER

---

## 五、關鍵設計決策

| 決策 | 選擇 | 理由 |
|:-----|:------|:------|
| RAG 引擎 | SQLite FTS5 | 輕量、無需外部服務 |
| API 介面 | OpenAI-compatible | 最大相容性，支援多供應商 |
| 人格實作 | 獨立 system prompt | 模組化、可測試、可擴展 |
| 引用格式 | Citation v2.1 [T1]/[1]/[2]/[3] | 統一定義，來源可追溯 |
| 型態系統 | 自訂 TYPE-S (L0.9) | 台灣法律教育需求特化 |
| 代理架構 | Hermes Agent skill-based | 生態系整合、工作流編排 |

---

## 六、安全性考量

```
1. Input Layer:    輸入消毒 + prompt injection 偵測
2. SRP Layer:      分級路由 + 高風險阻斷
3. RAG Layer:      檢索內容過濾 + 敏感詞封鎖
4. Committee Layer: BLIND_SPOT → 強制中止
5. Output Layer:   輸出審計 + 引用驗證
6. Audit Layer:    完整日誌 + 可回溯性
```

---

## 七、版本與變更記錄

| 版本 | 日期 | 變更內容 |
|:-----|:------|:---------|
| v3.0 | 2026-02 | 初始架構定義 |
| v3.2 | 2026-04 | 加入 L0.8 CASE_VERIFY |
| v3.4 | 2026-06 | 加入 MODE_ROUTER + 完整人格層 |
| v3.5 | 2026-07 | 加入 TYPE-S 型態系統 |
| v3.6 | 2026-08 | 子代理並行策略 |
| **v3.9.1** | **2026-07-05** | **H1-H6 修復：TYPE-S 升 L0.9、補 COMMITTEE 層（L0.95）、MODE_ROUTER 補齊 13 模式、PERSONA 補 PROMPT_ENGINEER+SENTINEL、Citation 統一 v2.1、CORE_GATE A/B/C 命名說明** |

---

> **架構演進原則**：每層可獨立演進、獨立測試、獨立替換。
>
> 維護者：Lucien · 最新更新：2026-07-05
