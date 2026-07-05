# 智研 AI 法律系統 · 開發路線圖

> **Zhiyan AI Legal System — Development Roadmap (v3.x → v6.x)**
>
> 從核心 RAG 研究平台到完整法律 AI 作業系統的進化路徑。

---

## 路線圖總覽

```
v3.x (當前)          v4.x                v5.x                v6.x
───────────    ─────────────      ─────────────      ─────────────
Core RAG        Agent Workflow      API Ecosystem      Community OSS
Citation v2.1   Multi-Model Orch.   Frontend PWA       Plugin System
Court Sim.      Research Suite      Docker Deploy      SDK & Docs
Safe Routing    Ablation Framework  Production Ops     Ecosystem
```

---

## Phase 1：核心研究平台（Current · v3.x）

> **階段目標**：建立可重現的法律 AI 研究平台，驗證核心假設（不虛構引用、安全路由、事實閘門）。

### 版本歷史

| 版本 | 日期 | 里程碑 |
|:-----|:------|:--------|
| v3.0 | 2026-02 | 初始架構：SRP + CORE_GATE + RAG |
| v3.1 | 2026-03 | 完整提示工程規格（90+ 文件） |
| v3.2 | 2026-04 | Citation Policy v2.0 引用政策 |
| v3.3 | 2026-05 | L0.8 CASE_VERIFY 判決書驗證 |
| v3.4 | 2026-06 | MODE_ROUTER 模式路由 + 6 人格系統 |
| **v3.5** | **2026-07** | **Court Simulation v1 + 訴訟推演模組** |
| v3.6 | 2026-08 | TYPE-S 型態系統強化 + 子代理並行策略 |

### Phase 1 核心交付

| 元件 | 狀態 | 說明 |
|:------|:------|:------|
| **G0 Confidence-first** | ✅ 完成 | 信心宣告層，低信心直接中止 |
| **SRP (L0.5)** | ✅ 完成 | 安全路由協議，RL0–RL3 分級 |
| **CORE_GATE (L0)** | ✅ 完成 | 事實分級（A/B/C）、缺口偵測、五要素提取 |
| **LOCAL_RAG (L0.7)** | ✅ 完成 | 47,001 條法條白話摘要，SQLite FTS5 |
| **CASE_VERIFY (L0.8)** | ✅ 完成 | 司法院判決書查詢整合 |
| **MODE_ROUTER** | ✅ 完成 | 任務路由：QC → RESEARCH → REPORT |
| **Persona Layer (L1)** | ✅ 完成 | 6 人格：MASTER, CONSULTANT, TUTOR, WRITER, TA, LEGAL_WRITER |
| **Citation Policy v2.1** | ✅ 完成 | [T] + [1] + [2] + [3] 四階引用標記 |
| **Hermes Agent Skill** | ✅ 完成 | v3.06 skill 定義，完整路由對應 |

| **Persona Layer (L1)** | ✅ 完成 | 14+ 人格/模組：MASTER, CONSULTANT, TUTOR, WRITER, TA, LEGAL_WRITER, PROMPT_ENGINEER, CONTRACT_RISK + 訴訟策略、安全、Sentinel、法庭模擬、申論測試 |
| **Citation Policy v2.1** | ✅ 完成 | [T] +  +  +  四階引用標記 |
| **Hermes Agent Skill** | ✅ 完成 | v3.08 skill 定義（9 模組、10 條全局約束、contract task mode） |
| **Contract Review** | ✅ 完成 | SkILL-03/SKILL-09：4 子代理管線含 LC-01~LC-15 排版校驗 |
| **Multi-Model Committee** | ✅ 完成 | 3 模型平行合議庭，標示共識/分歧/盲區 |
| **AI Benchmark** | ✅ 完成 | 6 題跨法域申論測驗集，6 項評分標準 |
| **Unified Router** | ✅ 完成 | prompts/modes/router.json 覆蓋 12 task_mode |
| **Court Simulation** | ✅ 完成 | 訴訟推演模組，攻防模擬 |
| **TYPE-S System** | ✅ 完成 | 型態系統：單選題、多選題、申論題、案例題 |
| **Sub-agent Parallel** | ✅ 完成 | 子代理並行排程，多任務同時處理 |
| **Research Suite** | ✅ 完成 | `--dry-run` + 消融實驗框架 |
| **Test Suite** | ✅ 完成 | 81+ 項回歸測試 + 冒煙測試 |
| **96+ Spec Docs** | ✅ 完成 | 完整提示工程規格文件體系 |

### Phase 1 關鍵指標

| 指標 | 當前值 | 目標 |
|:-----|:--------|:------|
| 不虛構引用率 | 待測量 | ≥ 95% |
| 安全路由準確率 | 待測量 | ≥ 99% |
| 事實閘門精確率 | 待測量 | ≥ 90% |
| 法條檢索 Recall@5 | 待測量 | ≥ 85% |
| 測試覆蓋率 | 81+ tests | ≥ 100 tests |

| 不虛構引用率 | 待 committee 全量測試 | ≥ 95% |
| 安全路由準確率 | 待測量 | ≥ 99% |
| 事實閘門精確率 | 待測量 | ≥ 90% |
| 法條檢索 Recall@5 | 待測量 | ≥ 85% |
| 測試覆蓋率 | 115 tests（7 測試檔） | ≥ 100 tests |

---

## Phase 2：代理工作流系統（v4.x）

> **階段目標**：從單一提示工程研究平台，進化為可編排的多代理工作流系統，支援多模型協作。

### 預計時間軸

| 版本 | 預計日期 | 主要功能 |
|:-----|:----------|:----------|
| v4.0 | 2026-09 | 代理工作流引擎（DAG-based） |
| v4.1 | 2026-10 | 多模型協調排程器 |
| v4.2 | 2026-11 | 工作流腳本語言（Zhiyan Workflow DSL） |
| v4.3 | 2026-12 | 完整研究消融框架 + RQ 分析工具 |
| v4.4 | 2027-01 | 代理記憶層（長期記憶 + 上下文管理） |
| v4.5 | 2027-02 | 合約審查自動化工作流 |

### Phase 2 核心交付

#### 代理工作流引擎
```
使用者輸入
    │
    ▼
[工作流解析器] → 動態建立 DAG
    │
    ├── Agent A (法律研究) ──┐
    ├── Agent B (事實提取) ──┤─── 合併結果
    ├── Agent C (引用驗證) ──┘
    └── Agent D (安全審計) ──→ 平行執行
    │
    ▼
[結果彙整器] → [引用格式化] → 輸出
```

#### 多模型協調排程器

| 功能 | 說明 |
|:------|:------|
| **模型路由** | 依任務類型自動選擇最適模型（GPT-5 書狀、Claude 合約、Gemini 法條查詢） |
| **成本優化** | 簡單任務走低成本模型，複雜任務走高性能模型 |
| **並行調度** | 多模型同時處理不同子任務 |
| **容錯降級** | 主模型失敗時自動切換備援模型 |
| **結果對比** | 多模型輸出比對，一致性檢查 |

#### 研究消融框架

```python
# 規劃中的消融實驗 API
from zhiyan_legal.ablation import AblationSuite

suite = AblationSuite(
    conditions=[
        "with_citation_policy",
        "without_citation_policy",
        "with_srp",
        "without_srp",
        "with_core_gate",
        "without_core_gate",
    ],
    metrics=["fabrication_rate", "safety_rate", "citation_accuracy"],
    n_trials=50
)
results = suite.run("刑法第271條的構成要件")
results.export("ablation_report.csv")
```

#### 代理記憶層

```
┌─────────────────────────────┐
│        Agent Memory         │
├─────────────────────────────┤
│ Short-term (對話上下文)      │ ← Session-based
│ Medium-term (案例快取)       │ ← SQLite
│ Long-term (使用模式學習)     │ ← 向量資料庫（規劃中）
│ Episodic (重要判決記錄)      │ ← Judicial API 快取
└─────────────────────────────┘
```

### Phase 2 關鍵指標

| 指標 | 目標 |
|:-----|:------|
| 多模型切換延遲 | < 500ms |
| 工作流編排 overhead | < 10% |
| 成本節省（vs 單一 GPT-5） | ≥ 40% |
| 消融實驗自動化覆蓋率 | 100% |
| 代理記憶 Recall@5 | ≥ 90% |

---

## Phase 3：完整平台（v5.x）

> **階段目標**：從研究工具轉型為可部署的完整平台，包含 API 生態、PWA 前端、容器化部署。

### 預計時間軸

| 版本 | 預計日期 | 主要功能 |
|:-----|:----------|:----------|
| v5.0 | 2027-03 | REST API Gateway v1 |
| v5.1 | 2027-04 | PWA 前端正式版 |
| v5.2 | 2027-05 | Docker 一鍵部署 + Docker Compose |
| v5.3 | 2027-06 | API 文件（OpenAPI / Swagger） |
| v5.4 | 2027-07 | 使用者認證 + API Key 管理 |
| v5.5 | 2027-08 | 監控儀表板 + 使用量分析 |

### Phase 3 核心交付

#### REST API 生態

```
zhiyan-api/
├── api/
│   ├── v1/
│   │   ├── chat.py          POST /v1/chat         法律對話
│   │   ├── research.py      POST /v1/research     法律研究
│   │   ├── review.py        POST /v1/review       合約審查
│   │   ├── simulate.py      POST /v1/simulate     訴訟推演
│   │   ├── statutes.py      GET  /v1/statutes     法條查詢
│   │   ├── cases.py         GET  /v1/cases        判決書查詢
│   │   ├── documents.py     GET  /v1/documents    書狀範本
│   │   └── health.py        GET  /v1/health       健康檢查
│   ├── auth.py              認證中介層
│   ├── rate_limit.py        速率限制
│   └── middleware.py        日誌 + 審計
├── docs/
│   └── openapi.yaml         OpenAPI 3.0 規格
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

#### PWA 前端正式版

基於現有 `law_monitor_app/`（Flutter），擴充為完整前端：

```
智研法律工作站 PWA ── v5.x
├── 🏠 儀表板 (Dashboard)
│   ├── 快速查詢面板
│   ├── 近期案例記錄
│   └── 系統使用統計
├── 💬 法律對話 (Chat)
│   ├── 多輪對話介面
│   ├── 引用顯示面板
│   ├── 人格切換選單
│   └── 歷史記錄
├── 📚 法條查詢 (Statutes)
│   ├── 分類瀏覽
│   ├── FTS5 全文搜尋
│   └── 判決書關聯
├── ⚖️ 訴訟推演 (Simulation)
│   ├── 攻防流程圖
│   ├── 證據管理
│   └── 判決預測
├── 📄 書狀生成 (Documents)
│   ├── 起訴狀生成
│   ├── 答辯狀生成
│   └── 合約審查報告
└── ⚙️ 系統設定
    ├── API Key 管理
    ├── 模型偏好
    └── 安全設定
```

#### Docker 一鍵部署

```yaml
# docker-compose.yml (規劃)
version: '3.8'
services:
  api:
    build: ./zhiyan-api
    ports:
      - "8000:8000"
    env_file: .env
    volumes:
      - ./data:/data
    depends_on:
      - rag-db
  rag-db:
    image: sqlite:latest
    volumes:
      - ./data/rag:/db
  frontend:
    build: ./law_monitor_app
    ports:
      - "3000:3000"
    depends_on:
      - api
```

### Phase 3 關鍵指標

| 指標 | 目標 |
|:-----|:------|
| API 回應時間 (p95) | < 2s |
| PWA Lighthouse 評分 | ≥ 90 |
| Docker 啟動時間 | < 30s |
| API 可用性 | ≥ 99.5% |
| 同時連線數支援 | ≥ 100 |

---

## Phase 4：社群開源生態（v6.x）

> **階段目標**：從單一專案轉型為社群驅動的開源生態系統，建立插件市場與貢獻者社群。

### 預計時間軸

| 版本 | 預計日期 | 主要功能 |
|:-----|:----------|:----------|
| v6.0 | 2027-09 | 插件系統 SDK v1 |
| v6.1 | 2027-10 | 社群貢獻指南 + CI/CD 流程 |
| v6.2 | 2027-11 | 插件市場 + 發布工具 |
| v6.3 | 2027-12 | 法律知識庫社群編輯介面 |
| v6.4 | 2028-01 | 正式 v1.0 穩定版發布 |
| v6.5 | 2028-02+ | 持續維護 + 社群驅動迭代 |

### Phase 4 核心交付

#### 插件系統 SDK

```python
# 規劃中的插件 API
from zhiyan_legal.plugin import ZhiyanPlugin, hook

class TaiwanTaxPlugin(ZhiyanPlugin):
    """稅務法律插件 - 社群貢獻"""

    @property
    def metadata(self):
        return {
            "name": "Taiwan Tax Law",
            "version": "1.0.0",
            "author": "community-contributor",
            "description": "台灣稅務法規專用模組",
        }

    @hook("pre_rag")
    def inject_tax_statutes(self, query, context):
        """在 RAG 檢索前注入稅務法規關鍵詞"""
        tax_keywords = ["所得稅", "營業稅", "遺產稅", "贈與稅"]
        if any(kw in query for kw in tax_keywords):
            context["rag_boost"] = {"category": "tax_law"}
        return query, context

    @hook("post_citation")
    def format_tax_citation(self, citation):
        """稅務引用特殊格式"""
        if citation["source"] == "稅務法令":
            citation["style"] = "tax_v2"
        return citation
```

#### 插件生態藍圖

```
插件類型             範例                         貢獻者
─────────            ────                         ────────
法規擴充             勞動法插件、智財法插件        律師/法律研究者
人格擴充             法官人格、檢察官人格          提示工程師
工作流擴充           併購盡職調查自動化流程        法律科技公司
API 擴充             政府開放資料介接              開發者
前端擴充             儀表板主題、可視化元件        UI/UX 設計師
評估擴充             新評估指標、測試案例          研究人員
```

#### 社群治理模型

```
Zhiyan Legal 社群
├── 核心維護團隊（Core Team）
│   ├── 創始人：Lucien
│   ├── 架構師：負責核心層變更審查
│   └── 發布管理：版本發布 + 品質控管
├── 活躍貢獻者（Active Contributors）
│   ├── 定期 PR 審查
│   └── 插件認證機制
├── 社群成員（Community）
│   ├── 插件開發
│   ├── 知識庫編輯
│   ├── 文件翻譯
│   └── 問題回報與測試
└── 合作夥伴（Partners）
    ├── 學術機構：法律系、AI 實驗室
    ├── 法律科技公司：商業整合
    └── 政府機構：司法院、法扶會
```

### Phase 4 關鍵指標

| 指標 | 目標 |
|:-----|:------|
| 社群貢獻者 | ≥ 20 活躍貢獻者 |
| 插件總數 | ≥ 30 個認證插件 |
| GitHub Stars | ≥ 500 |
| 社群翻譯語言 | ≥ 3（中文、英文、日文） |
| 外部 PR 合併率 | ≥ 70% |

---

## 跨階段依賴圖

```
v3.x (Core RAG)
  │
  ├── 提供 RAG 品質資料 → v4.x 工作流依賴於檢索品質
  ├── 提供引用政策    → v4.x/v5.x 引用格式一致性
  └── 提供安全路由    → 所有後續版本的基礎安全層
  │
  ▼
v4.x (Agent Workflow)
  │
  ├── 提供工作流引擎 → v5.x API 後端依賴
  ├── 提供多模型排程 → v5.x 生產級路由
  └── 提供消融框架   → v6.x 社群實驗工具
  │
  ▼
v5.x (Full Platform)
  │
  ├── 提供 REST API  → v6.x 插件 SDK 的基礎
  ├── 提供 PWA       → v6.x 前端插件嵌入點
  └── 提供 Docker    → v6.x 一鍵部署生態
  │
  ▼
v6.x (Community OSS)
  ← 所有前期階段的整合與開放
```

---

## 風險與對策

| 風險 | 影響 | 對策 |
|:-----|:------|:------|
| 司法院 API 變更 | L0.8 CASE_VERIFY 失效 | 抽象 API 層，支援多資料源備援 |
| LLM API 價格波動 | Phase 2 多模型成本不確定 | 成本感知路由 + 本地小模型選項 |
| 社群貢獻品質參差 | Phase 4 插件品質 | 強制 CI/CD + 程式碼審查 + 自動測試 |
| 法規內容更新頻繁 | RAG 知識庫過時 | 每日同步排程 + 自動異動偵測 |
| 安全事件（prompt injection） | 系統被惡意利用 | SRP 強化 + 輸入消毒 + 輸出審計 |

---

> **路線圖的更新頻率**：本文件每季檢討一次，對應實際開發進度調整。
>
> 最新更新：2026-06

> 最新更新：2026-07-02（v3.08）
>
> *路線圖是動態的。歡迎開 issue 或 PR 提出建議。*
