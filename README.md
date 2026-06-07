---
title: 智研 AI 法律系統 · Zhiyan AI Legal System
---
# 智研 AI 法律系統 · Zhiyan AI Legal System

> A layered, **citation-grounded**, **safety-first** legal-research agent for Taiwan law,
> packaged as a runnable harness over the **OpenAI API**.
> 以分層架構、強制引用政策與安全優先路由為核心的台灣法律研究代理，可直接在 OpenAI API 上運行。

[![tests](https://img.shields.io/badge/tests-pytest-blue)](tests/) ·
Python ≥ 3.10 · License: see [`LICENSE`](LICENSE)

---

## English overview

This project turns a 90-document prompt-engineering specification into a small,
testable Python package that composes a single system prompt at runtime and calls
the OpenAI API.

It is designed as a study object for the **responsible deployment of legal large
language models (LLMs)**. Three design properties make it a research artifact rather
than a chat wrapper:

1. **No-fabrication citation policy.** A single authoritative policy
   (`docs/20_.../30_引用政策_CITATION_POLICY`) forbids inventing statutes, judgments,
   statistics, or sources, and requires unverifiable claims to be marked *待查 (to verify)*
   or *推論 (inferred)*.
2. **Fact gate before conclusions.** Every request passes a `CORE_GATE` stage
   (fact tiering, gap flagging) before any legal conclusion, so the model cannot jump
   to win-rate or liability claims.
3. **Safety-first routing.** Inputs signalling self-harm, threats, fraud, privacy leakage,
   or physical danger are routed to a dedicated safety module *before* any legal analysis.

### Architecture

```
INTAKE → SAFETY_CHECK → FACT_GATE → ROUTE → EXECUTE → QC → DELIVER   (state machine)
```

- **Core control layer** (`docs/10_*`): one authoritative system prompt, master persona,
  boot order, fact gate, runbook, task router.
- **Mode & citation layer** (`docs/20_*`): REPORT / RESEARCH / QC modes + the single citation policy.
- **Module & persona layer** (`docs/40_*`): litigation strategy, safety handling, cross-jurisdiction
  pre-check (Sentinel), and consultant / TA-review / tutor personas.
- **Concept dictionary** (`docs/60_*`): 43 legal-term entries used as auxiliary knowledge.
- **Archive / governance** (`docs/80_*`, `docs/90_*`): reference-only and ops material —
  **never loaded into the live prompt** (enforced in code).

The runtime composes prompts in a fixed, documented order:

```
09_AGENT_SYSTEM_PROMPT → 10_MASTER → 13_SPACE_CORE → 11_BOOT
→ 12_CORE_GATE → 14_RUNBOOK → 15_TASK_ROUTER → 30_CITATION_POLICY
→ (+ the task-specific mode/persona file for the routed task)
```

### Quickstart

```bash
# 1. install
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. configure
cp .env.example .env        # then put your real OPENAI_API_KEY in .env

# 3a. dry-run — no API call, no spend: see routing + which docs load
PYTHONPATH=src python -m zhiyan_legal "幫我把這篇整理成研究報告並附來源" --dry-run

# 3b. real call
PYTHONPATH=src python -m zhiyan_legal "白話解釋行政處分是什麼"

# 4. run the regression tests (the spec's 10 routing cases)
PYTHONPATH=src pytest -q
```

### Repository layout

```
zhiyan-legal/
├── README.md            # this file
├── RESEARCH.md          # research framing for grant / Researcher Access applications
├── LICENSE              # ⚠ placeholder — choose a license deliberately (see file)
├── CITATION.cff         # citation metadata
├── pyproject.toml       # packaging + pytest config
├── requirements.txt
├── .env.example         # OPENAI_API_KEY, OPENAI_MODEL
├── docs/                # the full original specification, preserved unchanged
│   ├── 00_入口與總覽/   ├── 10_核心控制層/   ├── 20_模式與引用層/
│   ├── 40_模組與人格層/ ├── 60_概念詞條/     ├── 80_封存參考/  └── 90_維運治理/
├── src/zhiyan_legal/    # runtime
│   ├── manifest.py      # load order + task map + exclusion rules (mirrors the spec)
│   ├── router.py        # keyword routing → task label
│   ├── loader.py        # composes the system prompt; enforces exclusions
│   ├── runner.py        # OpenAI API call (+ dry-run)
│   └── cli.py           # `python -m zhiyan_legal ...`
└── tests/test_routing.py
```

### Scope boundary

The harness owns **routing** and **prompt composition**. The state machine's reasoning
steps (fact tiering, QC, uncertainty marking) are enforced *by the loaded specification*
and executed by the LLM — not re-implemented in Python. This boundary is deliberate and
documented so the system's behavior stays traceable to the spec.

---

## 中文總覽

本專案把一套 90 份文件的提示工程規格，整理成可測試的 Python 套件：執行時依
**固定且有文件依據的順序**組裝單一系統提示詞，再呼叫 OpenAI API。

定位為「**法律大型語言模型 (LLM) 之負責任部署**」的研究載體，三項設計使其成為研究
人工製品 (research artifact) 而非聊天外殼：

1. **不虛構引用政策**：唯一權威政策禁止虛構法條、判決、統計、來源；無法查證者
   一律標示「待查」或「推論」。
2. **結論前必經事實閘門**：每次請求先過 `CORE_GATE`（事實分級、缺口標示），
   模型不得直接跳到勝率或責任判斷。
3. **安全優先路由**：自傷、威脅、詐騙、個資外洩、人身危險等訊號，先進安全模組，
   再談法律分析。

### 快速開始

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                       # 填入你的 OPENAI_API_KEY

# 乾跑：不呼叫 API、不花額度，只看路由與載入文件
PYTHONPATH=src python -m zhiyan_legal "我被威脅，對方知道我住哪" --dry-run

# 跑回歸測試（規格的 10 個路由案例）
PYTHONPATH=src pytest -q
```

### 重要：關於「申請 OpenAI 研究用 API」

OpenAI 的 **Researcher Access Program（研究者存取計畫）** 有資格門檻：申請者須與
學術機構或研究組織有實質連結，或為從事研究（非營運支援）的非營利組織；額度上限
US$1,000、效期 12 個月、每季（3／6／9／12 月）審查一次。

身為獨立商業顧問，你很可能不符資格，且把本系統當「商品」呈現並不適配「研究」補助。
若仍要嘗試，唯一可行的切入是把本系統的**引用接地、事實閘門與安全路由**包裝成
「負責任部署研究」——範本見 [`RESEARCH.md`](RESEARCH.md)。請先讀完該檔再決定。

### 授權注意

[`LICENSE`](LICENSE) 目前是**保護優先的暫定授權**，不是最終決定。由於本系統具商業
價值，請刻意在「專有／寬鬆開源／Copyleft」三條路線中擇一後再替換，避免無意間
釋出可商用的智慧財產。
