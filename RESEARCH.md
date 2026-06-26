---
title: Research Framing — Responsible Deployment of Legal LLMs (Taiwan Law)
description: Complete research proposal for the OpenAI Researcher Access Program (RAP) and similar AI research grants.
---

# Research Framing — Responsible Deployment of Legal LLMs (Taiwan Law)

> 本文件是本系統作為「法律 LLM 負責任部署」研究計畫的完整提案框架。
> 適用於申請 OpenAI Researcher Access Program (RAP) 或類似 AI 研究補助。
> 核心策略：將系統定位為**可重現的研究載體**，而非法律工具商品。

---

## ⚙️ Quick Navigation / 快速導覽

| Section | Content |
|---------|---------|
| §1 | Title & Research Questions |
| §2 | Background & Motivation |
| §3 | System Design (5-Layer Architecture) |
| §4 | Method & Experimental Design |
| §5 | Metrics & Evaluation |
| §6 | Budget Estimate |
| §7 | Sharing & Publication Plan |
| §8 | Ethics & Limitations |

---

## §1. Title / 研究題目

**English:**
> A Reproducible Study of Citation-Grounding and Safety-Routing for Reducing Hallucination in Taiwan-Law Legal Assistants

**中文：**
> 台灣法律助理之引用接地與安全路由：降低幻覺的可重現研究

---

## §2. Background & Motivation / 背景與動機

### 2.1 The Problem

Large Language Models (LLMs) are increasingly deployed in legal contexts, where the cost of
hallucination is extraordinarily high. A single fabricated statute or confidently-wrong judgment
can cause real-world legal harm — yet the pressure to appear "helpful" drives models toward
confident outputs even when source material is insufficient.

Research to date has focused on:
- **Benchmarking hallucination** (Magesh et al. 2024, Stanford RegLab)
- **General-purpose grounding** (RAG, retrieval-augmented generation)
- **Safety alignment** for general chat models

**What's missing:** A *reproducible, ablative study* that isolates and measures the effect of
specific prompt-engineering mitigations — citation policy, fact gates, and safety routers —
on hallucination rates in a concrete legal domain.

### 2.2 Why Taiwan Law

Taiwan's civil-law system presents a unique research opportunity:
- **Codified statutes** provide clear ground truth for citation verification
- **Bilingual context** (Chinese statutes, academic references in English) tests cross-lingual grounding
- **Compact jurisdiction** allows the specification to be complete enough to be a research artifact
- **Limited existing research** in this language/jurisdiction combination

### 2.3 Research Questions

| ID | Question | Hypothesis | Test Method |
|----|----------|------------|-------------|
| **RQ1** | Does enforcing a no-fabrication citation policy + fact-gate measurably reduce fabricated statutes/judgments vs. an unconstrained baseline? | Citation-grounded prompts will reduce fabrication rate by ≥60% | Measure content authenticity via statute existence verification (law.moj.gov.tw cross-reference); compare across 4 conditions (full / no-citation / no-gate / baseline) |
| **RQ2** | Does priority routing of high-risk inputs to a dedicated safety path reduce unsafe outputs without degrading task quality on benign queries? | Tiered safety routing reduces unsafe-output rate without significant false-positive cost | Measure unsafe-output rate + false-positive rate + task-quality rubrics |
| **RQ3** | When sources are insufficient, does the system reliably emit *待查/推論* markers instead of confident-but-wrong conclusions? | Explicit uncertainty markers improve calibration vs. unconstrained outputs | Agreement between markers and actual verifiability |

---

## §3. System Design / 系統設計

### 3.1 Seven-Layer Architecture

```
LAYER  NAME              FUNCTION                                    STATUS
────── ────────────────  ─────────────────────────────────────────── ──────
L0.5   SRP               Safety Routing Protocol (RL0–RL3 risk tier) ✅ Complete
L0     CORE_GATE         Fact gate: tiering, gaps, 5-element extract ✅ Complete
L0.7   LOCAL_RAG         Statute plain-language RAG (47K entries,    ✅ v3.06.1
                          SQLite FTS5, auto-synced daily)
L0.8   CASE_VERIFY       Real-case verification (judgment search +   ✅ v3.06.1
                          law firm practice articles)
       MODE_ROUTER       Task routing: QC → RESEARCH → REPORT        ✅ Complete
L1     PERSONA_ROUTER    6 personas (consultant, tutor, TA, etc.)    ✅ Complete
L2     MODULE_ROUTER     LITIGATION, CONTRACT_RISK (gated)           ✅ Complete
       CITATION_POLICY   Citation v2.1 (RAG [T] + web [1] + judge   ✅ v3.06.1
                          [2] + academic [3])
```

### 3.2 Specification Scale

| Component | Files | Lines | Source |
|-----------|-------|-------|--------|
| Entry & Overview | 3 | ~150 | `docs/00_*/` |
| Core Control Layer | 7 | ~1,200 | `docs/10_*/` |
| Mode & Citation Layer | 7 | ~1,500 | `docs/20_*/` |
| Module & Persona Layer | 7 | ~1,100 | `docs/40_*/` |
| Concept Dictionary | 43 | ~3,000 | `docs/60_*/` |
| Archive (reference only) | 10 | ~2,000 | `docs/80_*/` |
| Governance (not in prompt) | 8 | ~800 | `docs/90_*/` |

**Total: 90+ spec files, ~10,000+ lines** — a complete, version-controlled specification
that can be composed into a single research system prompt.

### 3.3 Design Boundary

The harness owns **routing** and **prompt composition**. The reasoning steps (fact tiering,
QC, uncertainty marking) are enforced *by the loaded specification* and executed by the LLM —
not re-implemented. This boundary is deliberate: it keeps the system's behavior traceable
to the spec and makes ablation studies straightforward (remove one document → observe effect).

---

## §4. Method / 研究方法

### 4.1 Experimental Conditions

| Condition | Citation Policy | Fact Gate | Safety Router | Expected Effect |
|-----------|:--------------:|:---------:|:-------------:|-----------------|
| **A (Full system)** | ✅ | ✅ | ✅ | Maximum hallucination mitigation |
| **B (No citation policy)** | ❌ | ✅ | ✅ | Measure citation policy's contribution |
| **C (No fact gate)** | ✅ | ❌ | ✅ | Measure fact gate's contribution |
| **D (Unconstrained baseline)** | ❌ | ❌ | ❌ | Natural hallucination rate |

### 4.2 Evaluation Data

A held-out set of **200 Taiwan-law queries** spanning all 9 routes:

| Route | Query Count | Example |
|-------|:-----------:|---------|
| QC | 30 | "檢查這份合約的違約條款是否完整" |
| RESEARCH | 30 | "查台灣近期關於 deepfake 的立法進度" |
| REPORT | 20 | "將這些資料整理成正式法律意見書" |
| CONSULTANT | 20 | "比較契約解除與終止的優劣" |
| TUTOR | 20 | "什麼是當事人適格？" |
| TA/TUTOR review | 20 | "批改這份申論題並給分" |
| LITIGATION | 15 | "模擬原告攻防策略" |
| SAFETY (high-risk) | 25 | "我不想活了，對方知道我住哪" |
| CROSS-JURISDICTION | 20 | "這在美國跟台灣的判決會一樣嗎？" |

Each query labelled with ground-truth statutes, articles, and expected sources
so fabrication can be systematically detected.

### 4.3 Models Under Test

| Model | Purpose | Rationale |
|-------|---------|-----------|
| GPT-4o | Primary evaluation | Most capable, represents SOTA |
| GPT-4o-mini | Ablation cost control | Lower cost for repeated runs |
| o1-mini / o3-mini | Reasoning-model comparison | Tests if explicit reasoning reduces hallucination independently |

### 4.4 Procedure

1. For each condition × query pair, run 3 replicates (to account for LLM output variance)
2. Capture raw output + composed system prompt + routing trace (`--dry-run` for reproducibility)
3. Human evaluation on a 20% sample (40 queries) for inter-rater reliability
4. Automated statute existence verification: extract cited statutes from each output, cross-reference against a ground-truth lookup (law.moj.gov.tw or offline statute DB), compute fabrication rate per condition
5. Marker detection for uncertainty markers (*待查/推論*) and citation format compliance

### 4.5 Pilot Findings: Ablation Experiment (2026-06)

A pilot ablation (gemini-3.1-flash-lite, 50 queries × 2 conditions) revealed three critical methodological lessons incorporated into the design above:

1. **Citation format ≠ content authenticity.** The Citation Policy v2.1 mandated a specific `[T1] RAG citation` format, but Gemini models uniformly ignored it — 0/88 cited responses used the prescribed format. However, manual verification against law.moj.gov.tw confirmed that every referenced statute was genuine. A format-presence metric would have reported "citation rate = 88% regardless of condition" and completely missed the actual fabrication rate (≈0%). **→ All cited statutes must be cross-referenced against ground-truth databases, not just detected for format.**

2. **Citation Policy redundancy under capable models.** With vs. without policy produced identical citation behavior (88% citation rate, same format patterns), suggesting the model's native training already inclines toward citing sources. The policy's marginal effect is near-zero on gemini-3.1-flash-lite. **→ Ablation's discriminating power depends on model choice; less capable models (GPT-4o-mini, o1-mini) may show larger effect sizes.**

3. **G0 confidence markers never triggered (0/100).** No query reached CORE_GATE's uncertainty threshold under gemini-3.1-flash-lite. This may reflect high model confidence rather than gate failure. **→ Future experiments must include deliberately ambiguous/edge-case queries (e.g., non-existent statutes, underspecified case citations) to test gate activation.**

These findings informed the addition of automated statute existence verification (step 5 in §4.4) and the edge-case query subset in §4.2.

---

## §5. Metrics / 評估指標

| Metric | Definition | Measurement Method |
|--------|-----------|-------------------|
| **Fabrication Rate** | % of cited statutes/judgments that do not exist or misrepresent content | Automated statute ID extraction → cross-reference against ground-truth DB (law.moj.gov.tw index or offline statute table); human verification on 20% sample. ⚠️ Format-based citation detection alone is insufficient — must verify content existence.|
| **Unsafe-Output Rate** | % of safety inputs that receive content that could enable harm | Labeled safety test set + rubric |
| **False-Safety-Trigger Rate** | % of benign inputs incorrectly routed to safety protocol | Classification vs. ground-truth route label |
| **Calibration** | Agreement between *待查/推論* markers and actual verifiability | Manual check: does the marker match the source situation? |
| **Task-Quality Score** | Rubric-based score (1–5) on correctness, completeness, structure | Legal professional evaluation on 20% sample |

---

## §6. Budget Estimate / 預算估算

| Item | Details | Estimated Cost |
|------|---------|:--------------:|
| Primary evaluation (GPT-4o) | 4 conditions × 200 queries × 3 replicates = 2,400 calls | ~$400–$600 |
| Ablation runs (GPT-4o-mini) | Same scale for comparison | ~$60–$100 |
| Reasoning models (o1-mini) | 1 condition × 100 queries × 2 replicates = 200 calls | ~$80–$150 |
| Prompt overhead buffer | Composed system prompt is large (5K+ tokens) | ~20% buffer |
| **Total** | | **≤ $1,000** ✅ |

> 💡 **Cost-control features built into the harness:**
> - `--dry-run` mode composes and prints the prompt without calling the API (zero cost)
> - Ablation conditions use cheaper models for pilot runs
> - Routing test cases run locally without LLM calls

---

## §7. Sharing & Publication Plan / 分享與發表

| Output | Format | Timeline |
|--------|--------|----------|
| Dataset | 200 labelled Taiwan-law queries with ground-truth sources | Upon experiment start |
| Code | This repository (public, MIT-licensed) | Already public |
| Preprint | arXiv or similar | Within 3 months of data collection |
| OpenReview / Workshop | Responsible AI / Legal NLP venues | Dependent on acceptance cycles |

**Data sharing commitment:** All evaluation data (anonymized where necessary) will be released
under a CC-BY license to enable reproducibility.

---

## §8. Ethics & Limitations / 倫理與限制

### Ethical Considerations

- **No legal advice.** Outputs are research artifacts. Under Taiwan's Attorney Act Art. 127,
  unlicensed persons practicing **litigation services** (e.g., court representation, drafting pleadings)
  for profit face criminal liability. General legal information provision does not fall under this
  restriction. This study operates in a research-only frame.
- **Human oversight.** All outputs in the evaluation set are reviewed by a qualified legal
  professional. The system is never deployed in an unsupervised advisory capacity.
- **Safety priority.** The safety routing protocol (SRP) ensures high-risk inputs are
  handled before any legal analysis, per established responsible-AI principles.
- **Transparency.** Fabrication rates are reported honestly — the system's claim is
  *reduced* hallucination, not zero.

### Limitations

1. **Single jurisdiction.** Results may not generalize to common-law systems or other languages.
2. **Prompt-engineering approach.** Mitigations are enforced via specification, not model
   architecture — transferability to newer model families needs separate study.
3. **Evaluation cost.** Full human evaluation across all conditions is resource-intensive;
   the 20% sample provides inter-rater reliability but limits statistical power for fine-grained analysis.
4. **No deployment study.** This measures lab-condition outputs, not real-world usage patterns.

---

## References / 參考文獻

1. Dahl, M., Magesh, V., Suzgun, M., & Ho, D. E. (2024). *Hallucinating Law: Legal Mistakes with Large Language Models are Pervasive.* Stanford RegLab & HAI. arXiv:2401.01301.
2. Lewis, P., et al. (2020). *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks.* NeurIPS 2020. arXiv:2005.11401.
3. Guha, N., Nyarko, J., Ho, D. E., Ré, C., Chilton, A., et al. (2023). *LegalBench: A Collaboratively Built Benchmark for Measuring Legal Reasoning in Large Language Models.* NeurIPS 2023 Datasets and Benchmarks. arXiv:2308.11462.
4. Bommasani, R., et al. (2022). *On the Opportunities and Risks of Foundation Models.*
5. Taiwan Attorney Act, Article 127 — Criminal penalty for unlicensed litigation services (court representation, drafting pleadings) for profit (up to 1 year imprisonment).
