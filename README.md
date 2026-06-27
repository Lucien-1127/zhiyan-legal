---
title: 智研 AI 法律系統 · Zhiyan AI Legal System
description: 以分層架構、強制引用政策與安全路由為核心的可重現台灣法律 AI 研究平台。
license: MIT
authors:
  - Lucien (Lucien-1127) <Lucien127@proton.me>
repository: https://github.com/Lucien-1127/zhiyan-legal
---

# 智研 AI 法律系統 · Zhiyan AI Legal System

[![Hermes Skill](https://img.shields.io/badge/Hermes-v3.07-8B5CF6)](SKILL.md)
[![Docs](https://img.shields.io/badge/docs-100%2B_specs-blue)](docs/)
[![MkDocs](https://img.shields.io/badge/MkDocs-Material-0094F5)](https://lucien-1127.github.io/zhiyan-legal/)
[![Wiki](https://img.shields.io/badge/wiki-6_pages-2E8B57)](docs/wiki/)
[![Python](https://img.shields.io/badge/python-3.10+-376F9B)](.)
[![License](https://img.shields.io/badge/license-MIT-3DA639)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-122_passed-3DA639)](tests/)
[![CI](https://img.shields.io/badge/GitHub%20Actions-pages-2088FF)](.github/workflows/)

> 以分層架構、強制引用政策與安全路由為核心的台灣法律 AI 研究平台。  
> A citation-grounded, safety-first legal AI research platform for Taiwan law.

<p align="center">
  <img src="docs/banner.png" alt="智研AI法律工作站" width="100%">
</p>

---

<details open>
<summary><b>🇹🇼 繁體中文</b></summary>

## 概述

本專案將 **100 份以上的提示工程規格文件**封裝為可重現的研究平台，探討三個核心問題：

| # | 研究問題 | 對策 | 測量方式 |
|:--|:---------|:-----|:---------|
| RQ1 | **不虛構引用政策**能否減少捏造法條？ | 引用政策 v2.1 | 捏造率 vs. 無約束對照組 |
| RQ2 | **安全優先路由**能否減少有害輸出？ | SRP 分層風險評分 | 不安全輸出率 + 誤觸發率 |
| RQ3 | **事實閘門**能否改善不確定性校正？ | 核心閘門 — 分級 + 缺口標示 | 標記準確性 |

> **為何重要。** 一條捏造的法律引用就能造成實際傷害。本系統將每項緩解措施編碼為*可測試的機制*——可測量、可重現、可供消融實驗。

---

## 四大研究特性

| # | 特性 | 原則 |
|:--|:-----|:-----|
| G0 | **信心優先** | 輸出前先宣告信心。❌ 低 → 中止。 |
| 🔬 | **不虛構政策** | 禁止捏造法條／判決。不可查證者標示「待查」或「推論」。 |
| 🛡️ | **事實閘門** | 核心閘門分級後才下結論。A/B/C 類觸發人工複核提示。 |
| ⚠️ | **安全路由** | 高風險輸入先進安全模組，再談法律分析。 |

---

## 系統架構（v3.07）

```
G0 → 輸入 → SRP → CORE_GATE → L0.7 本地RAG → L0.8 案例驗證 → 模式 → 人格 → 引用 → 輸出

G0     信心層級              ❌ 低 = 中止
L0.5   SRP                   安全路由協議（RL0–RL3）
L0     核心閘門 + Sentinel   事實分級、程序階段偵測、法域優先序、五要素提取、禁止事項
L0.7   本地 RAG              47,001 條法條白話摘要（SQLite FTS5）
L0.8   案例驗證 + 憲判檢查   司法院判決書 MCP 查詢、憲法法庭強制檢查（113憲判3等）
       模式路由              任務路由：QC → RESEARCH → REPORT → TA → WRITER → PROMPT_ENGINEER …
L1     人格                  6 種人格：MASTER、CONSULTANT、TUTOR、WRITER、TA、LEGAL_WRITER
L2     功能模組              訴訟推演、合約風險、申論測試、法庭模擬；引用 v2.1：[T] + [1] + [2] + [3]

MCP    基礎設施              GCP MCP ×6（BigQuery/Storage/Run/Logging/Compute/ResourceManager）
                             + MCP Taiwan Legal DB（取代官方 API，22/24 壓力測試通過）
```

---

## 儲存庫結構

```
zhiyan-legal/
├── .github/                  Issue/PR 模板 + CI/CD（GitHub Pages, 測試）
├── docs/                     100 份規格文件，7 層 + wiki/
│   ├── 00_入口與總覽/        入口與總覽
│   ├── 10_核心控制層/        主人格、啟動流程、核心閘門
│   ├── 20_模式與引用層/      模式與引用政策
│   ├── 40_模組與人格層/      功能模組、人格模組（含 WRITER、TA、PROMPT_ENGINEER）
│   ├── 60_概念詞條/          法域、風險、詞條
│   ├── 80_封存參考/          舊版參考文件
│   └── 90_維運治理/          文件治理、測試、更新說明
├── references/               技能參考文件（TA prompt、WRITER prompt、壓力測試報告等）
├── src/zhiyan_legal/         Python 框架（API 無關），含法規異動追蹤
├── tests/                    測試套件（122 項）
├── mkdocs.yml                GitHub Pages 設定（MkDocs Material）
├── RESEARCH.md               完整研究提案
├── SKILL.md                  Hermes Agent 技能定義（v3.07）
└── CITATION.cff              引用資訊（v3.07）
```

---

## 快速開始

### 透過 Hermes Agent

```bash
/zhiyan 請分析這個契約是否有風險
hermes chat -q "/zhiyan 什麼是公然侮辱罪？"
```

### 獨立 Python CLI

```bash
git clone https://github.com/Lucien-1127/zhiyan-legal.git
cd zhiyan-legal && bash scripts/setup.sh

# 乾跑（零成本）
PYTHONPATH=src python -m zhiyan_legal "什麼是公然侮辱？" --dry-run

# 正式呼叫
PYTHONPATH=src python -m zhiyan_legal "比較契約解除與終止"

# 跑測試
PYTHONPATH=src pytest tests/ -v
```

---

## 文件導覽

| 資源 | 說明 |
|:-----|:------|
| 📖 [MkDocs 站台](https://lucien-1127.github.io/zhiyan-legal/) | 完整線上文件（GitHub Pages） |
| 📘 [Wiki](docs/wiki/) | 快速開始、架構、引用政策、壓力測試 |
| 🎯 [願景](docs/vision.md) | 從 AI 工具到 AI 法律作業系統 |
| 🗺️ [路線圖](docs/roadmap.md) | Phase 1–4 開發規劃 |
| 🏗️ [架構](docs/architecture.md) | 七層系統完整規格 |
| 📋 [Issues](https://github.com/Lucien-1127/zhiyan-legal/issues) | Bug 回報與功能建議 |

---

## 給 RAP 申請者

本專案為**可重現研究**——非商業工具。提供：
1. 完整 100+ 文件規格
2. 三個附指標的研究問題
3. 消融實驗框架（`--dry-run` 模式零成本測試）
4. 預定義評估方法

> 以 [`RESEARCH.md`](RESEARCH.md) 中的研究問題為核心撰寫申請書。

---

## 引用

```bibtex
@software{zhiyan_legal_2026,
  author = {Lucien (Lucien127@proton.me)},
  title = {Zhiyan AI Legal System},
  year = {2026},
  version = {v3.07},
  url = {https://github.com/Lucien-1127/zhiyan-legal}
}
```

---

## 授權

MIT — 詳見 [`LICENSE`](LICENSE)。系統輸出為研究人工製品，**非法律意見**。

</details>

---

<details>
<summary><b>🇬🇧 English</b></summary>

## Overview

This repository packages a **100+ document prompt-engineering specification** into a reproducible research platform investigating three core questions:

| # | Research Question | Mitigation | Measured By |
|:--|:------------------|:-----------|:------------|
| RQ1 | Does a **no-fabrication citation policy** reduce hallucinated statutes? | Citation Policy v2.1 | Fabrication rate vs. baseline |
| RQ2 | Does **priority safety routing** reduce harmful outputs? | SRP — tiered risk scoring | Unsafe-output + false-positive rate |
| RQ3 | Does a **fact gate** improve uncertainty calibration? | CORE_GATE — fact tiering + gap flagging | Marker-vs-verifiability agreement |

> **Why this matters.** A single hallucinated legal citation can cause real harm. This system encodes every mitigation as a *testable mechanism* — measurable, reproducible, and designed for ablation studies.

---

## Four Research Properties

| # | Property | Principle |
|:--|:---------|:----------|
| G0 | **Confidence-first** | Declare confidence before any output. ❌ Low → stop. |
| 🔬 | **No-fabrication policy** | Forbid invented statutes/judgments. Unverifiable → mark `待查`/`推論`. |
| 🛡️ | **Fact gate** | CORE_GATE tiering before any conclusion. A/B/C cases trigger human-review prompt. |
| ⚠️ | **Safety routing** | High-risk inputs routed to safety protocol *before* legal analysis. |

---

## System Architecture (v3.07)

```
G0 → INPUT → SRP → CORE_GATE → L0.7 LOCAL_RAG → L0.8 CASE_VERIFY → MODE → PERSONA → CITATION → OUTPUT

G0              Confidence-first                ❌ Low = stop
L0.5            SRP                             Safety Routing Protocol (RL0–RL3)
L0              CORE_GATE + Sentinel            Fact tiering, program stage detection, domain priority, 5-element extraction
L0.7            LOCAL_RAG                       47,001 statute plain-language entries (SQLite FTS5)
L0.8            CASE_VERIFY + CONST. CHECK       MCP judgment search + mandatory constitutional court check
                MODE_ROUTER                     QC → RESEARCH → REPORT → TA → WRITER → PROMPT_ENGINEER …
L1              PERSONA                         6 personas: MASTER, CONSULTANT, TUTOR, WRITER, TA, LEGAL_WRITER
L2              MODULE                          LITIGATION, ESSAY_TEST, COURTROOM; CITATION v2.1: [T] + [1] + [2] + [3]

MCP             INFRASTRUCTURE                  GCP MCP ×6 + MCP Taiwan Legal DB (replaces official API, 22/24 stress-tested)
```

---

## Quickstart

### Via Hermes Agent

```bash
/zhiyan Analyze this contract for risks
hermes chat -q "/zhiyan What constitutes public insult under Taiwan law?"
```

### Standalone Python CLI

```bash
git clone https://github.com/Lucien-1127/zhiyan-legal.git
cd zhiyan-legal && bash scripts/setup.sh

# Dry-run (zero cost)
PYTHONPATH=src python -m zhiyan_legal "What is public insult?" --dry-run

# Real call
PYTHONPATH=src python -m zhiyan_legal "Compare termination vs. rescission"

# Run tests
PYTHONPATH=src pytest tests/ -v
```

---

## For RAP Applicants

This project is a **reproducible research study** — not a commercial tool. Includes:
1. Complete 100+ document specification
2. Three testable research questions with metrics
3. Ablation-ready harness (`--dry-run` mode for zero-cost experiments)
4. Pre-defined evaluation methodology

> Frame your application around the research questions in [`RESEARCH.md`](RESEARCH.md).

---

## Citation

```bibtex
@software{zhiyan_legal_2026,
  author = {Lucien (Lucien127@proton.me)},
  title = {Zhiyan AI Legal System},
  year = {2026},
  version = {v3.07},
  url = {https://github.com/Lucien-1127/zhiyan-legal}
}
```

---

## License

MIT — see [`LICENSE`](LICENSE). Outputs are research artifacts, **not legal advice**.

</details>
