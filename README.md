---
title: 智研 AI 法律系統 · Zhiyan AI Legal System
description: A reproducible research study of citation-grounding and safety-routing for reducing hallucination in Taiwan-law legal assistants.
license: MIT
authors:
  - Lucien (Lucien-1127) <Lucien127@proton.me>
repository: https://github.com/Lucien-1127/zhiyan-legal
---

# 智研 AI 法律系統 · Zhiyan AI Legal System

[![Hermes Skill](https://img.shields.io/badge/Hermes-v3.06-8B5CF6)](SKILL.md)
[![Docs](https://img.shields.io/badge/docs-110+_specs-blue)](docs/)
[![Python](https://img.shields.io/badge/python-3.10+-376F9B)](.)
[![License](https://img.shields.io/badge/license-MIT-3DA639)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-81_passed-3DA639)](tests/)

> **A citation-grounded, safety-first legal AI research platform for Taiwan law.**

> 以分層架構、強制引用政策與安全路由為核心的台灣法律 AI 研究平台。

---

<details open>
<summary><b>🇬🇧 English</b></summary>

## Overview

This repository packages a **90+ document prompt-engineering specification** into a reproducible
research platform investigating three core questions:

| # | Research Question | Mitigation | Measured By |
|:--|:------------------|:-----------|:------------|
| RQ1 | Does a **no-fabrication citation policy** reduce hallucinated statutes? | Citation Policy v2.1 | Fabrication rate vs. baseline |
| RQ2 | Does **priority safety routing** reduce harmful outputs? | SRP — tiered risk scoring | Unsafe-output + false-positive rate |
| RQ3 | Does a **fact gate** improve uncertainty calibration? | CORE_GATE — fact tiering + gap flagging | Marker-vs-verifiability agreement |

> **Why this matters.** A single hallucinated legal citation can cause real harm.
> This system encodes every mitigation as a *testable mechanism* — measurable, reproducible,
> and designed for ablation studies.

---

## Four Research Properties

| # | Property | Principle |
|:--|:---------|:----------|
| G0 | **Confidence-first** | Declare confidence before any output. ❌ Low → stop. |
| 🔬 | **No-fabrication policy** | Forbid invented statutes/judgments. Unverifiable → mark `待查`/`推論`. |
| 🛡️ | **Fact gate** | CORE_GATE tiering before any conclusion. A/B/C cases trigger human-review prompt. |
| ⚠️ | **Safety routing** | High-risk inputs routed to safety protocol *before* legal analysis. |

---

## System Architecture

```
G0 → INTAKE → SRP → CORE_GATE → L0.7 RAG → L0.8 CASE_VERIFY → MODE → PERSONA → CITATION → OUTPUT

G0     Confidence-first     ❌ Low = stop
L0.5   SRP                  Safety Routing Protocol (RL0–RL3)
L0     CORE_GATE            Fact tiering, gap detection, 5-element extraction
L0.7   LOCAL_RAG            47,001 statute plain-language entries (SQLite FTS5, daily sync)
L0.8   CASE_VERIFY          Real-case check via judgment.judicial.gov.tw + law firm articles
       MODE_ROUTER          Task routing: QC → RESEARCH → REPORT
L1     PERSONA              6 personas: MASTER, CONSULTANT, TUTOR, WRITER, TA, LEGAL_WRITER
L2     MODULE               LITIGATION, CONTRACT_RISK; CITATION v2.1: [T] + [1] + [2] + [3]
```

## Repository Layout

```
zhiyan-legal/
├── README.md                 This file
├── RESEARCH.md               Full research proposal (grant applications)
├── SKILL.md                  Hermes Agent skill definition (v3.06)
├── CITATION.cff              Academic citation metadata
├── pyproject.toml             Package metadata
├── requirements.txt           Deps: openai + python-dotenv
├── scripts/setup.sh            One-command install
├── docs/                     110+ specification documents, 7 layers
├── src/zhiyan_legal/          Python harness (API-agnostic)
│   ├── cli.py                 CLI entry point
│   ├── loader.py              System prompt composer
│   ├── manifest.py            Load order + task map
│   ├── router.py              Keyword routing (81 tests)
│   └── runner.py              OpenAI-compatible API runner
└── tests/test_routing.py      81 regression tests
```

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

## API Provider Compatibility

| Provider | Base URL | Example Model |
|:---------|:---------|:--------------|
| OpenAI | `https://api.openai.com/v1` | `gpt-5.1` |
| OpenRouter | `https://openrouter.ai/api/v1` | `anthropic/claude-sonnet-4.6` |
| DeepSeek | `https://api.deepseek.com` | `deepseek/deepseek-v4-flash` |
| Google Gemini | `https://generativelanguage.googleapis.com/v1beta/openai` | `gemini-3-flash-preview` |
| NVIDIA | `https://api.nvidia.com/v1` | `nvidia/nemotron-3-super` (free) |

## For RAP Applicants

This project is a **reproducible research study** — not a commercial tool. Includes:
1. Complete 110+ document specification
2. Three testable research questions with metrics
3. Ablation-ready harness (`--dry-run` mode for zero-cost experiments)
4. Pre-defined evaluation methodology

> Frame your application around the research questions in [`RESEARCH.md`](RESEARCH.md).

## Citation

```bibtex
@software{zhiyan_legal_2026,
  author = {Lucien (Lucien127@proton.me)},
  title = {Zhiyan AI Legal System},
  year = {2026},
  url = {https://github.com/Lucien-1127/zhiyan-legal}
}
```

## License

MIT — see [`LICENSE`](LICENSE). Outputs are research artifacts, **not legal advice**.

</details>

<details>
<summary><b>🇹🇼 繁體中文</b></summary>

## 概述

本專案將 **90 份以上的提示工程規格文件**封裝為可重現的研究平台，探討三個核心問題：

| # | 研究問題 | 對策 | 測量方式 |
|:--|:---------|:-----|:---------|
| RQ1 | **不虛構引用政策**能否減少捏造法條？ | 引用政策 v2.1 | 捏造率 vs. 無約束對照組 |
| RQ2 | **安全優先路由**能否減少有害輸出？ | SRP 分層風險評分 | 不安全輸出率 + 誤觸發率 |
| RQ3 | **事實閘門**能否改善不確定性校正？ | 核心閘門 — 分級 + 缺口標示 | 標記準確性 |

> **為何重要。** 一條捏造的法律引用就能造成實際傷害。本系統將每項緩解措施
> 編碼為*可測試的機制*——可測量、可重現、可供消融實驗。

---

## 四大研究特性

| # | 特性 | 原則 |
|:--|:-----|:-----|
| G0 | **信心優先** | 輸出前先宣告信心。❌ 低 → 中止。 |
| 🔬 | **不虛構政策** | 禁止捏造法條／判決。不可查證者標示「待查」或「推論」。 |
| 🛡️ | **事實閘門** | 核心閘門分級後才下結論。A/B/C 類觸發人工複核提示。 |
| ⚠️ | **安全路由** | 高風險輸入先進安全模組，再談法律分析。 |

---

## 系統架構

```
G0 → 輸入 → SRP → CORE_GATE → L0.7 本地RAG → L0.8 案例驗證 → 模式 → 人格 → 引用 → 輸出

G0     信心層級       ❌ 低 = 中止
L0.5   SRP            安全路由協議（RL0–RL3）
L0     核心閘門        事實分級、缺口偵測、五要素提取
L0.7   本地 RAG        47,001 條法條白話摘要（SQLite FTS5，每日同步）
L0.8   案例驗證        司法院判決書查詢＋律師事務所實務見解
       模式路由        任務路由：QC → RESEARCH → REPORT
L1     人格            6 種人格：MASTER、CONSULTANT、TUTOR、WRITER、TA、LEGAL_WRITER
L2     功能模組        訴訟推演、合約風險；引用 v2.1：[T] + [1] + [2] + [3]
```

## 儲存庫結構

```
zhiyan-legal/
├── README.md                 本文件
├── RESEARCH.md               完整研究提案（科研補助申請）
├── SKILL.md                  Hermes Agent 技能定義（v3.06）
├── CITATION.cff              學術引用元資料
├── pyproject.toml             套件資訊
├── requirements.txt           相依：openai + python-dotenv
├── scripts/setup.sh            一鍵安裝
├── docs/                      110+ 規格文件，7 層
├── src/zhiyan_legal/           Python 框架（API 無關）
│   ├── cli.py                  命令列入口
│   ├── loader.py               系統提示詞組成
│   ├── manifest.py             載入順序＋路由對應
│   ├── router.py               關鍵詞路由（81 項測試）
│   └── runner.py               OpenAI 相容 API 執行器
└── tests/test_routing.py       81 項回歸測試
```

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

## API 供應商相容性

| 供應商 | Base URL | 範例模型 |
|:-------|:---------|:---------|
| OpenAI | `https://api.openai.com/v1` | `gpt-5.1` |
| OpenRouter | `https://openrouter.ai/api/v1` | `anthropic/claude-sonnet-4.6` |
| DeepSeek | `https://api.deepseek.com` | `deepseek/deepseek-v4-flash` |
| Google Gemini | `https://generativelanguage.googleapis.com/v1beta/openai` | `gemini-3-flash-preview` |
| NVIDIA | `https://api.nvidia.com/v1` | `nvidia/nemotron-3-super`（免費） |

## 給 RAP 申請者

本專案為**可重現研究**——非商業工具。提供：
1. 完整 110+ 文件規格
2. 三個附指標的研究問題
3. 消融實驗框架（`--dry-run` 模式零成本測試）
4. 預定義評估方法

> 以 [`RESEARCH.md`](RESEARCH.md) 中的研究問題為核心撰寫申請書。

## 引用

```bibtex
@software{zhiyan_legal_2026,
  author = {Lucien (Lucien127@proton.me)},
  title = {Zhiyan AI Legal System},
  year = {2026},
  url = {https://github.com/Lucien-1127/zhiyan-legal}
}
```

## 授權

MIT — 詳見 [`LICENSE`](LICENSE)。系統輸出為研究人工製品，**非法律意見**。

</details>
