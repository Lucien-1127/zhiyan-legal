---
title: 智研 AI 法律系統 · Zhiyan AI Legal System
description: A reproducible research study of citation-grounding and safety-routing for reducing hallucination in Taiwan-law legal assistants.
license: MIT
authors:
  - Lucien (Lucien-1127) <Lucien127@proton.me>
repository: https://github.com/Lucien-1127/zhiyan-legal
---

# 智研 AI 法律系統 · Zhiyan AI Legal System

[![docs](https://img.shields.io/badge/docs-110+_specs-blue)](docs/)
[![Hermes Skill](https://img.shields.io/badge/Hermes-Skill_v3.05-purple)](SKILL.md)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-green)](.)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)
[![法律研究](https://img.shields.io/badge/%E6%B3%95%E5%BE%8B%E7%A0%94%E7%A9%B6-legal-orange)](.)
[![OpenAI](https://img.shields.io/badge/OpenAI-LLM-412991)](.)
[![Deep Research](https://img.shields.io/badge/Deep%20Research-9--lens-8B5CF6)](.)
[![Courtroom](https://img.shields.io/badge/Courtroom-Simulation-1f8f4f)](docs/40_模組與人格層/43_模組_法庭模擬_v1.1.0.md)
[![Essay Test](https://img.shields.io/badge/Essay-3--Zone_Temp-f97316)](docs/40_模組與人格層/44_模組_申論題測試_v1.0.0.md)

> **Language:** [English ↓](#english) ｜ [繁體中文 ↓](#繁體中文)

A **layered, citation-grounded, safety-first** legal-research agent for Taiwan law,
designed as a reproducible research artifact for studying hallucination mitigation.

以分層架構、強制引用政策與安全優先路由為核心的台灣法律研究代理，
作為「法律 LLM 之負責任部署」的可重現研究載體。

---

## English {#english}

### Research Overview

This repository packages a **90+ document prompt-engineering specification** into a reproducible,
testable research platform investigating three core research questions.

| # | Research Question | Design Mitigation | Measured By |
|---|-------------------|-------------------|-------------|
| RQ1 | Does a **no-fabrication citation policy** measurably reduce hallucinated statutes/judgments? | `Citation Policy v2.0` — single authoritative policy forbidding invented sources | Fabrication rate vs. unconstrained baseline |
| RQ2 | Does **priority safety routing** of high-risk inputs reduce harmful outputs without degrading benign-task quality? | `SRP (Safety Routing Protocol)` — tiered risk scoring before any legal analysis | Unsafe-output rate + false-positive rate |
| RQ3 | Does a **fact gate** before conclusions improve uncertainty calibration when sources are insufficient? | `CORE_GATE` — fact tiering, gap flagging, explicit *待查/推論* markers | Calibration between uncertainty markers and actual verifiability |

**Why this matters.** Legal LLMs are a high-stakes deployment surface: a single hallucinated
citation can cause real harm. This system encodes mitigations as *testable mechanisms* — not
aspirational design goals — making them measurable and reproducible.

#### Four Research Properties

1. **🔬 G0: Confidence-first rule.** System must declare confidence level before any output. ❌ Low confidence → "no reliable sources, cannot answer" — no guessing, no fabrication.
2. **🔬 No-fabrication citation policy.** A single authoritative policy (`30_引用政策_CITATION_POLICY_v2.0.0`) prohibits inventing statutes, judgments, or sources. Unverifiable claims must be marked *待查 (to verify)* or *推論 (inferred)*.
3. **🛡️ Fact gate before conclusions.** Every request passes a `CORE_GATE` stage (fact tiering, gap flagging, five-element extraction) before any legal conclusion. A/B/C high-risk case classifications trigger mandatory human-review prompts.
4. **⚠️ Safety-first routing.** Self-harm, threats, fraud, or physical danger inputs are routed to a dedicated safety protocol *before* legal analysis, using tiered risk scoring (RL0–RL3) with Red Flag escalation.

---

### Repository Layout

```
zhiyan-legal/
├── README.md            # This file — research overview + quickstart
├── RESEARCH.md          # Full research framing for grant / Researcher Access applications
├── SKILL.md             # Hermes Agent skill definition (v3.05, 6-layer: SRP→L0→L0.7 RAG→MODE→PERSONA→CITATION)
├── CITATION.cff         # Citation metadata for academic attribution
├── pyproject.toml       # Python package metadata
├── requirements.txt     # Runtime deps: openai + python-dotenv
├── .env.example         # Multi-provider config template
├── .gitignore           # Excludes .venv, __pycache__, .env
├── scripts/setup.sh      # One-command install script (venv + deps + .env)
├── docs/                # Full specification (110+ files, 7 layers)
│   ├── 00_入口與總覽/   # Entry guide & overview (3 files)
│   ├── 10_核心控制層/   # Core control: persona, boot, gate, router (7 files)
│   ├── 20_模式與引用層/ # Modes: REPORT / RESEARCH / QC + citation policy (7 files)
│   ├── 40_模組與人格層/ # Modules: litigation, safety, Sentinel, personas (7 files)
│   ├── 60_概念詞條/     # Concept dictionary: 43 legal-term entries (43 files)
│   ├── 80_封存參考/     # Archive: deprecated/reference versions (10 files)
│   └── 90_維運治理/     # Governance: smoke tests, changelogs (8 files)
├── src/zhiyan_legal/     # Python harness (API-agnostic, any provider)
│   ├── cli.py            # CLI entry point (`python -m zhiyan_legal ...`)
│   ├── loader.py         # Composes the system prompt from docs/
│   ├── manifest.py       # Load order + task map + exclusion rules
│   ├── router.py         # Keyword routing → task label (14 test cases)
│   └── runner.py         # OpenAI-compatible API runner (no vendor lock-in)
└── tests/test_routing.py # 14 regression tests for routing logic
```

### System Architecture

```
G0 → INTAKE → SRP_SAFETY_CHECK → CORE_GATE_FACT_TIER → MODE_ROUTER → PERSONA_ROUTER → CITATION_POLICY → OUTPUT
G0 → INTAKE → SRP_SAFETY_CHECK → CORE_GATE_FACT_TIER → L0.7_RAG → MODE_ROUTER → PERSONA_ROUTER → CITATION_POLICY → OUTPUT

- **G0**: Confidence-first — ❌ Low = stop immediately
- **L0.5**: SRP — Safety Routing Protocol (risk scoring RL0–RL3)
- **L0**: CORE_GATE — Fact tiering, gap detection, five-element extraction
- **L0.7**: LOCAL_RAG — 47,001 statute plain-language entries in SQLite FTS5; auto-synced daily from Google Sheets; cited as [T1][T2]…
- **MODE_ROUTER**: Task routing — QC → RESEARCH → REPORT (priority order)
- **L1**: PERSONA — 6 personas: MASTER, CONSULTANT, TUTOR, WRITER, TA, LEGAL_WRITER
- **L2**: MODULE — LITIGATION, CONTRACT_RISK (gated by L0 + fact check); CITATION — Policy v2.1: RAG [T] + web [1] + judgment [2] + academic [3]
```

---

### Quickstart

#### Option A: Via Hermes Agent (Recommended)

```bash
# The skill is already loaded if you have it installed
/zhiyan Please analyze this contract for risks

# Or from CLI:
hermes chat -q "/zhiyan What constitutes public insult under Taiwan law?"
```

#### Option B: Standalone Python CLI (Any API Provider)

```bash
# 0. Optional: if docs/ is not at repo root
# export ZHIYAN_DOCS_DIR=/path/to/zhiyan-legal/docs

# 1. Clone and install
git clone https://github.com/Lucien-1127/zhiyan-legal.git
cd zhiyan-legal
bash scripts/setup.sh            # interactive: venv + deps + .env

# 2. Edit .env — choose your API provider:
#    ZHIYAN_API_KEY=sk-...
#    ZHIYAN_API_BASE_URL=https://api.openai.com/v1
#    ZHIYAN_MODEL=gpt-5.1

# 3. Dry-run (0 cost)
PYTHONPATH=src python -m zhiyan_legal "What is public insult?" --dry-run

# 4. Real call
PYTHONPATH=src python -m zhiyan_legal "Compare termination vs. rescission of contract"

# 5. Run tests
PYTHONPATH=src pytest tests/ -v
```

#### API Provider Compatibility

| Provider       | Base URL                                                    | Example Model                      |
|----------------|-------------------------------------------------------------|------------------------------------|
| OpenAI         | `https://api.openai.com/v1`                                  | `gpt-5.1`                          |
| OpenRouter     | `https://openrouter.ai/api/v1`                               | `anthropic/claude-sonnet-4.6`      |
| DeepSeek       | `https://api.deepseek.com`                                   | `deepseek/deepseek-v4-flash`       |
| Google Gemini  | `https://generativelanguage.googleapis.com/v1beta/openai`    | `gemini-3-flash-preview`           |
| MiniMax        | `https://api.minimax.chat/v1`                                | `minimax-m3`                       |
| NVIDIA         | `https://api.nvidia.com/v1`                                  | `nvidia/nemotron-3-super` (free)   |
| **Any custom** | Your endpoint                                                | Any model                          |

---

### For OpenAI Researcher Access Program Applicants

This project is structured as a **reproducible research study** — not a commercial legal tool.
If you are affiliated with an eligible institution, this repository provides:

1. A **complete, versioned, 110+ document specification** (docs/)
2. **Three testable research questions** with defined metrics (see RESEARCH.md)
3. **A reproducible harness** with ablation conditions
4. **Pre-defined evaluation methodology** (fabrication rate, unsafe-output rate, calibration)

> 💡 **Tip:** Frame your application around the *research questions* in RESEARCH.md.
> The program funds the *study of responsible deployment* — demonstrate how your experiment
> generates measurable evidence about hallucination mitigation.

---

### Related Work

- **Henderson et al. (2023)** — Foundation Model Transparency Reports
- **Magesh et al. (2024)** — Hallucination Detection in Legal LLMs (Stanford RegLab)
- **Sun et al. (2024)** — LegalBench: A Collaboratively Built Benchmark for Measuring Legal Reasoning
- **Taiwan Attorney Act, Art. 48** — Constraints on B2C legal-advice delivery

---

### License

This project is distributed under the **MIT License** — see [`LICENSE`](LICENSE).

> ⚖️ Outputs are research artifacts, **not legal advice**. Under Taiwan's Attorney Act Art. 48,
> B2C legal-advice delivery is constrained. Keep all use in a research / non-advisory frame.

---

## 繁體中文 {#繁體中文}

### 研究概述

本專案將 **90 份以上的提示工程規格文件**，封裝為可重現、可測試的研究平台，
探討三個核心研究問題。

| # | 研究問題 | 設計對策 | 測量方式 |
|---|---------|---------|---------|
| RQ1 | **不虛構引用政策**是否能可測量地減少 LLM 捏造法條／判決？ | `引用政策 v2.0` — 單一權威政策禁止虛構來源 | 捏造率 vs. 無約束對照組 |
| RQ2 | **安全優先路由**能否在不降低一般任務品質的前提下減少有害輸出？ | `SRP 安全路由協議` — 任何法律分析前先進行分層風險評分 | 不安全輸出率 + 誤觸發率 |
| RQ3 | **事實閘門**能否在來源不足時，改善不確定性校正？ | `核心閘門` — 事實分級、缺口標示、*待查/推論* 顯式標記 | 不確定標記與實際可驗證性的一致性 |

**為何重要。** 法律 LLM 是高風險部署領域：一條捏造的法條引用就能造成實際傷害。
本系統將緩解措施編碼為*可測試的機制* —— 而非僅僅是設計目標 —— 使其可測量且可重現。

#### 四大研究特性

1. **🔬 G0：信心優先規則。** 系統必須在任何輸出前先宣告信心等級。❌ 低信心 →「無可靠資料來源，無法回答此問題」—— 不猜測、不捏造。
2. **🔬 不虛構引用政策。** 單一權威政策（`30_引用政策_CITATION_POLICY_v2.0.0`）禁止虛構法條、判決或來源。無法查證者一律標示「待查」或「推論」。
3. **🛡️ 結論前必經事實閘門。** 每次請求先過 `CORE_GATE`（事實分級、缺口標示、五要素提取），模型不得直接跳到勝率或責任判斷。A/B/C 高風險案件觸發強制人工複核提示。
4. **⚠️ 安全優先路由。** 自傷、威脅、詐騙、人身危險等輸入先進安全模組，再談法律分析，使用分層風險評分（RL0–RL3）搭配紅旗升級機制。

---

### 儲存庫結構

```
zhiyan-legal/
├── README.md            # 本文件 — 研究概述 + 快速開始
├── RESEARCH.md          # 完整研究框架（供科研補助申請用）
├── SKILL.md             # Hermes Agent 技能定義 (v3.05, 6層: SRP→L0→L0.7 RAG→MODE→PERSONA→CITATION)
├── CITATION.cff         # 學術引用元資料
├── pyproject.toml       # Python 套件資訊
├── requirements.txt     # 相依套件：openai + python-dotenv
├── .env.example         # 多供應商設定範本
├── .gitignore           # 排除 .venv, __pycache__, .env
├── scripts/setup.sh      # 一鍵安裝腳本（虛擬環境 + 相依套件 + .env）
├── docs/                # 完整規格文件（110+ 篇，7 層）
│   ├── 00_入口與總覽/   # 入口導覽（3 篇）
│   ├── 10_核心控制層/   # 核心控制：人格、啟動、閘門、路由（7 篇）
│   ├── 20_模式與引用層/ # 模式：報告 / 研究 / 品質檢查 + 引用政策（7 篇）
│   ├── 40_模組與人格層/ # 模組：訴訟、安全、哨兵偵測、人格（7 篇）
│   ├── 60_概念詞條/     # 概念辭典：43 個法律術語（43 篇）
│   ├── 80_封存參考/     # 封存：已棄用/歷史版本（10 篇）
│   └── 90_維運治理/     # 治理：冒煙測試、變更記錄（8 篇）
├── src/zhiyan_legal/     # Python 執行框架（API 無關，支援任何供應商）
│   ├── cli.py            # 命令列入口（`python -m zhiyan_legal ...`）
│   ├── loader.py         # 從 docs/ 組成系統提示詞
│   ├── manifest.py       # 載入順序 + 路由對應 + 排除規則
│   ├── router.py         # 關鍵詞路由 → 任務標籤（14 項測試）
│   └── runner.py         # 符合 OpenAI 標準的 API 執行器（無供應商鎖定）
└── tests/test_routing.py # 14 項路由回歸測試
```

### 系統架構

```
G0 → 輸入 → SRP 安全檢查 → CORE_GATE 事實分級 → MODE_ROUTER 路由 → PERSONA_ROUTER 人格 → CITATION_POLICY 引用 → 輸出

五層架構：
G0   信心層級    — 信心優先：❌ 低信心立即中止
L0.5 SRP        — 安全路由協議（風險評分 RL0–RL3）
L0   核心閘門    — 事實閘門：分級、缺口偵測、五要素提取
     模式路由    — 任務路由：QC → RESEARCH → REPORT（優先順序）
L1   人格        — 6 種人格：MASTER, CONSULTANT, TUTOR, WRITER, TA, LEGAL_WRITER
L2   功能模組    — 訴訟推演, 合約風險（需 L0 + 事實查核）
     引用政策    — 引用政策 v2.0：行內標記 + 段落末尾 + 全文彙總
```

---

### 快速開始

#### 方式 A：透過 Hermes Agent（推薦）

```bash
# 若技能已安裝，直接對話觸發
/zhiyan 請分析這個契約是否有風險

# 或從命令列：
hermes chat -q "/zhiyan 什麼是公然侮辱罪？"
```

#### 方式 B：獨立 Python 命令列工具（任何 API 皆可）

```bash
# 0. 可選：若 docs/ 不在 repo 根目錄
# export ZHIYAN_DOCS_DIR=/path/to/zhiyan-legal/docs

# 1. 下載並安裝
git clone https://github.com/Lucien-1127/zhiyan-legal.git
cd zhiyan-legal
bash scripts/setup.sh            # 互動式：虛擬環境 + 相依套件 + .env

# 或手動：
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# 2. 編輯 .env — 選擇你的 API 供應商：
#    ZHIYAN_API_KEY=sk-...
#    ZHIYAN_API_BASE_URL=https://api.openai.com/v1
#    ZHIYAN_MODEL=gpt-5.1

# 3. 乾跑（0 成本）
PYTHONPATH=src python -m zhiyan_legal "什麼是公然侮辱罪？" --dry-run

# 4. 正式呼叫
PYTHONPATH=src python -m zhiyan_legal "比較契約解除與終止的優劣"

# 5. 跑測試
PYTHONPATH=src pytest tests/ -v
```

#### API 供應商相容性

| Provider       | Base URL                                                    | 範例模型                           |
|----------------|-------------------------------------------------------------|-----------------------------------|
| OpenAI         | `https://api.openai.com/v1`                                  | `gpt-5.1`                          |
| OpenRouter     | `https://openrouter.ai/api/v1`                               | `anthropic/claude-sonnet-4.6`      |
| DeepSeek       | `https://api.deepseek.com`                                   | `deepseek/deepseek-v4-flash`       |
| Google Gemini  | `https://generativelanguage.googleapis.com/v1beta/openai`    | `gemini-3-flash-preview`           |
| MiniMax        | `https://api.minimax.chat/v1`                                | `minimax-m3`                       |
| NVIDIA         | `https://api.nvidia.com/v1`                                  | `nvidia/nemotron-3-super` (free)   |
| **任何自訂**   | 你的端點                                                      | 任何模型                           |

---

### 給 OpenAI Researcher Access Program 申請者

本專案以**可重現研究**為架構，並非商業法律工具。
若你具有符合資格的研究機構所屬身分，此儲存庫提供：

1. **完整、版本化的 110+ 文件規格**（docs/）
2. **三個可測試的研究問題**，附明確定義的測量指標（見 RESEARCH.md）
3. **可重現的執行框架**，附消融實驗條件
4. **預先定義的評估方法**（捏造率、不安全輸出率、校正）

> 💡 **建議：** 以 RESEARCH.md 中的*研究問題*為核心撰寫申請書。
> 此計畫補助的是「負責任部署研究」—— 展示你的實驗如何為法律領域的幻覺抑制
> 產出可測量的證據。

完整研究提案範本（含預算估算、倫理考量與發表計畫）見 [`RESEARCH.md`](RESEARCH.md)。

---

### 相關文獻

- **Henderson 等 (2023)** — 基礎模型透明度報告
- **Magesh 等 (2024)** — 法律 LLM 幻覺偵測研究（Stanford RegLab）
- **Sun 等 (2024)** — LegalBench：法律推理能力協作評測基準
- **中華民國律師法第 48 條** — 非律師執行法律業務之限制

---

### 授權

本專案以 **MIT 授權條款** 發布 — 詳見 [`LICENSE`](LICENSE)。

> ⚖️ **重要提醒：** 系統輸出為研究人工製品，**非法律意見**。依據中華民國律師法第 48 條，
> B2C 法律意見交付受法律限制。所有使用請維持在研究／非諮詢框架內。

---

## Citation / 引用

BibTeX:

```bibtex
@software{zhiyan_legal_2026,
  author = {Lucien (Lucien127@proton.me)},
  title = {Zhiyan AI Legal System: A Reproducible Study of Citation-Grounding and Safety-Routing for Legal LLMs},
  year = {2026},
  url = {https://github.com/Lucien-1127/zhiyan-legal}
}
```

APA:

> Lucien. (2026). *Zhiyan AI Legal System: A Reproducible Study of Citation-Grounding and Safety-Routing for Legal LLMs* (v3.04) [Software]. https://github.com/Lucien-1127/zhiyan-legal
