---
title: 智研 AI 法律系統 · Zhiyan AI Legal System
description: A reproducible research study of citation-grounding and safety-routing for reducing hallucination in Taiwan-law legal assistants.
license: MIT
authors:
  - Lucien (Lucien-1127) <Lucien127@proton.me>
repository: https://github.com/Lucien-1127/zhiyan-legal
---

# 智研 AI 法律系統 · Zhiyan AI Legal System

> A **layered, citation-grounded, safety-first** legal-research agent for Taiwan law,
> designed as a **reproducible research artifact** for studying hallucination mitigation
> in high-stakes legal LLM deployment.
>
> 以分層架構、強制引用政策與安全優先路由為核心的台灣法律研究代理，
> 作為「法律 LLM 之負責任部署」的可重現研究載體。

[![docs](https://img.shields.io/badge/docs-110+_specs-blue)](docs/)
[![Hermes Skill](https://img.shields.io/badge/Hermes-Skill_v3.04-purple)](SKILL.md)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-green)](.)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)

---

## Research Overview / 研究概述

This repository packages a **90+ document prompt-engineering specification** into a reproducible,
testable research platform that investigates three core questions:

| # | Research Question | Design Mitigation | Measured By |
|---|-------------------|-------------------|-------------|
| RQ1 | Does a **no-fabrication citation policy** measurably reduce hallucinated statutes/judgments? | `Citation Policy v2.0` — single authoritative policy forbidding invented sources | Fabrication rate vs. unconstrained baseline |
| RQ2 | Does **priority safety routing** of high-risk inputs reduce harmful outputs without degrading benign-task quality? | `SRP (Safety Routing Protocol)` — tiered risk scoring before any legal analysis | Unsafe-output rate + false-positive rate |
| RQ3 | Does a **fact gate** before conclusions improve uncertainty calibration when sources are insufficient? | `CORE_GATE` — fact tiering, gap flagging, explicit *待查/推論* markers | Calibration between uncertainty markers and actual verifiability |

**Why this matters.** Legal LLMs are a high-stakes deployment surface: a single hallucinated
citation can cause real harm. This system encodes three mitigations as *testable mechanisms* —
not aspirational design goals — making them measurable and reproducible.

### Three Research Properties

1. **🔬 No-fabrication citation policy.** A single authoritative policy (`30_引用政策_CITATION_POLICY_v2.0.0`) prohibits inventing statutes, judgments, or sources. Unverifiable claims must be marked *待查 (to verify)* or *推論 (inferred)*.
2. **🛡️ Fact gate before conclusions.** Every request passes a `CORE_GATE` stage (fact tiering, gap flagging, five-element extraction) before any legal conclusion — the model cannot jump directly to win-rate or liability claims.
3. **⚠️ Safety-first routing.** Inputs signalling self-harm, threats, fraud, privacy leakage, or physical danger are routed to a dedicated safety protocol *before* any legal analysis, using a tiered risk scoring system (RL0–RL3).

---

## Repository Layout / 儲存庫結構

```
zhiyan-legal/
├── README.md            # This file — research overview + quickstart
├── RESEARCH.md          # Full research framing for grant / Researcher Access applications
├── SKILL.md             # Hermes Agent skill definition (v3.01, 5-layer architecture)
├── CITATION.cff         # Citation metadata for academic attribution
├── docs/                # Full specification (110+ files, 7 layers)
│   ├── 00_入口與總覽/   # Entry guide & overview (3 files)
│   ├── 10_核心控制層/   # Core control: persona, boot, gate, router (7 files)
│   ├── 20_模式與引用層/ # Modes: REPORT / RESEARCH / QC + citation policy (7 files)
│   ├── 40_模組與人格層/ # Modules: litigation, safety, Sentinel, personas (7 files)
│   ├── 60_概念詞條/     # Concept dictionary: 43 legal-term entries (43 files)
│   ├── 80_封存參考/     # Archive: deprecated/reference versions (10 files)
│   └── 90_維運治理/     # Governance: smoke tests, changelogs (8 files)
├── scripts/setup.sh      # One-command install script (venv + deps + .env)
├── src/zhiyan_legal/     # Python harness (API-agnostic, any provider)
│   ├── cli.py            # CLI entry point (`python -m zhiyan_legal ...`)
│   ├── loader.py         # Composes the system prompt from docs/
│   ├── manifest.py       # Load order + task map + exclusion rules
│   ├── router.py         # Keyword routing → task label (14 test cases)
│   └── runner.py         # OpenAI-compatible API runner (no vendor lock-in)
├── tests/test_routing.py # 14 regression tests for routing logic
```

### System Architecture / 系統架構

```
INTAKE → SRP_SAFETY_CHECK → CORE_GATE_FACT_TIER → MODE_ROUTER → PERSONA_ROUTER → CITATION_POLICY → OUTPUT

5-Layer Architecture:
L0.5  SRP           — Safety Routing Protocol (risk scoring RL0–RL3)
L0    CORE_GATE     — Fact gate: tiering, gap detection, five-element extraction
      MODE_ROUTER   — Task routing: QC → RESEARCH → REPORT (priority order)
L1    PERSONA       — 6 personas: MASTER, CONSULTANT, TUTOR, WRITER, TA, LEGAL_WRITER
L2    MODULE        — LITIGATION, CONTRACT_RISK (gated by L0 + fact check)
      CITATION      — Citation Policy v2.0: inline + per-paragraph + full-end list
```

---

## Quickstart / 快速開始

### Option A: Via Hermes Agent (推薦 / Recommended)

```bash
# The skill is already loaded if you have it installed
# Just trigger in chat:
/zhiyan 請分析這個契約是否有風險

# Or from CLI:
hermes chat -q "/zhiyan 什麼是公然侮辱罪?"
```

### Option B: Standalone Python CLI (任何 API 皆可)

```bash
# 1. Clone and install
git clone https://github.com/Lucien-1127/zhiyan-legal.git
cd zhiyan-legal
bash scripts/setup.sh            # interactive: venv + deps + .env

# Or manually:
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# 2. Edit .env — 選擇你的 API Provider:
#    (OpenAI, OpenRouter, DeepSeek, Gemini, or any OpenAI-compatible API)
#    ZHIYAN_API_KEY=sk-...
#    ZHIYAN_API_BASE_URL=https://api.openai.com/v1
#    ZHIYAN_MODEL=gpt-4o

# 3. Run (dry-run: 0 cost, no API call)
PYTHONPATH=src python -m zhiyan_legal "什麼是公然侮辱罪?" --dry-run

# 4. Run (real call)
PYTHONPATH=src python -m zhiyan_legal "比較契約解除與終止的優劣"

# 5. Run tests
PYTHONPATH=src pytest tests/ -v
```

### API Provider Compatibility

| Provider | Base URL | Example Model |
|----------|----------|---------------|
| OpenAI | `https://api.openai.com/v1` | `gpt-4o`, `gpt-4o-mini` |
| OpenRouter | `https://openrouter.ai/api/v1` | `anthropic/claude-sonnet-4` |
| DeepSeek | `https://api.deepseek.com` | `deepseek-chat`, `deepseek-reasoner` |
| Google Gemini | `https://generativelanguage.googleapis.com/v1beta/openai` | `gemini-2.5-flash` |
| Xiaomi MiMo | `https://api.xiaomimimo.com/v1` | `mimo-v2.5` |
| **Any custom** | Your endpoint | Any model |

---

## For OpenAI Researcher Access Program Applicants

This project is structured as a **reproducible research study** — not a commercial legal tool.
If you are affiliated with an eligible institution, the combination of:

1. A **complete, versioned, 110+ document specification** (docs/)
2. **Three testable research questions** with defined metrics (see RESEARCH.md)
3. **A reproducible harness** with ablation conditions (full system / no citation policy / no fact gate / baseline)
4. **Pre-defined evaluation methodology** (fabrication rate, unsafe-output rate, calibration)

makes this a strong candidate for the **Researcher Access Program**.

> 💡 **Tip:** Frame your application around the *research questions* in RESEARCH.md,
> not around "building a legal AI." The program funds *study of responsible deployment* —
> demonstrate how your experiment will generate measurable evidence about hallucination
> mitigation in high-stakes legal domains.

See [`RESEARCH.md`](RESEARCH.md) for the full research proposal template,
including budget estimates, ethics considerations, and publication plans.

---

## Related Work / 相關文獻

- **Henderson et al. (2023)** — Foundation Model Transparency Reports
- **Magesh et al. (2024)** — Hallucination Detection in Legal LLMs (Stanford RegLab)
- **Sun et al. (2024)** — LegalBench: A Collaboratively Built Benchmark for Measuring Legal Reasoning
- **Taiwan Attorney Act, Art. 48** — Constraints on B2C legal-advice delivery

---

## License / 授權

This project is distributed under the **MIT License** — see [`LICENSE`](LICENSE).

> ⚖️ **Important:** Outputs are research artifacts, **not legal advice**. Under Taiwan's
> Attorney Act Art. 48, B2C legal-advice delivery is constrained. Keep all use in a
> research / non-advisory frame.

---

## Citation / 引用

If you use this system in your research:

```bibtex
@software{zhiyan_legal_2026,
  author = {Lucien (Lucien127@proton.me)},
  title = {Zhiyan AI Legal System: A Reproducible Study of Citation-Grounding and Safety-Routing for Legal LLMs},
  year = {2026},
  url = {https://github.com/Lucien-1127/zhiyan-legal}
}
```
