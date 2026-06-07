---
title: RESEARCH.md — Responsible-deployment framing
---
# RESEARCH.md — Responsible-deployment framing

> **Purpose.** A template for positioning this system as a *research study* rather than a
> commercial product, for use when applying to programs like the **OpenAI Researcher
> Access Program (RAP)** or similar AI-research grants.
> 本檔是把本系統包裝成「研究」而非「商品」的範本，供申請 OpenAI 研究者存取計畫
> (RAP) 或類似 AI 研究補助時填寫。

---

## ⚠ Read this first / 先讀這段

RAP eligibility is the binding constraint, not repository quality:

- **Affiliation required.** Applicants must have an active affiliation with an academic
  institution or research organization, or be a nonprofit conducting research (not
  operational support). An independent commercial consultant generally does **not** qualify.
- **Fit.** The program funds the study of *responsible AI deployment, risk mitigation, and
  societal impact* — not productization. Frame this as a study of a phenomenon, with
  measurable research questions, not as "build my legal tool."
- **Mechanics.** Up to US$1,000 in credits, valid 12 months; quarterly review
  (Mar/Jun/Sep/Dec); 4–6 weeks to credit after a decision; bound by OpenAI's usage and
  sharing-&-publication policies.

If you lack an eligible affiliation, more realistic alternatives include: a university
co-author/PI, an applied-AI / API-credits track that does not require academic affiliation,
or simply paying for API usage (the harness's `--dry-run` mode lets you minimize spend
while developing).

---

## 1. Title

*A reproducible study of citation-grounding and safety-routing for reducing hallucination
in Taiwan-law legal assistants.*
（台灣法律助理之引用接地與安全路由：降低幻覺的可重現研究。）

## 2. Research questions

- **RQ1 (grounding).** Does enforcing a no-fabrication citation policy + a fact-gate stage
  measurably reduce fabricated statutes/judgments versus an unconstrained baseline?
- **RQ2 (safety routing).** Does priority routing of high-risk inputs (self-harm, threats,
  fraud, privacy, physical danger) to a dedicated safety path reduce unsafe or harmful
  outputs without degrading task quality on benign legal queries?
- **RQ3 (uncertainty calibration).** When sources are insufficient, does the system reliably
  emit *待查/推論* markers instead of confident-but-wrong conclusions?

## 3. Why this is responsible-deployment research

Legal LLMs are a high-stakes deployment surface: hallucinated citations and overconfident
conclusions cause concrete harm. This system encodes three mitigations as *testable
mechanisms* — a single authoritative citation policy, a fact gate that precedes any
conclusion, and a safety-first router — making them measurable rather than aspirational.

## 4. Method

- **Models.** Evaluate across OpenAI publicly available models (the credits target).
- **Conditions.** (a) full system; (b) ablation: citation policy removed; (c) ablation:
  fact gate removed; (d) unconstrained baseline.
- **Harness.** This repository. `--dry-run` reproduces the exact composed prompt per
  condition; the router's behavior is pinned by `tests/test_routing.py`.
- **Data.** A held-out set of Taiwan-law queries spanning the 9 routes (research, report,
  QC, consultant, TA-review, tutor, litigation, safety, cross-jurisdiction), each labelled
  with ground-truth statutes/sources so fabrication can be detected.

## 5. Metrics

- **Fabrication rate:** fraction of cited statutes/judgments that do not exist or do not say
  what is claimed (human-verified on a sample).
- **Unsafe-output rate** on the high-risk subset; **false-safety-trigger rate** on benign inputs.
- **Calibration:** agreement between *待查/推論* markers and actual verifiability.
- **Task quality:** rubric scores on benign legal tasks (to check mitigations don't over-restrict).

## 6. Budget (illustrative, ≤ US$1,000)

| Item | Est. |
|---|---|
| 4 conditions × N queries × M models, with repeats | the bulk of credits |
| Buffer for prompt-length overhead (the composed system prompt is large) | ~20% |

> Note: the composed system prompt concatenates the full core layer, so per-call input
> tokens are substantial. Budget for that, or use a smaller model for ablations.

## 7. Sharing & publication

State your intended output (preprint / dataset of labelled queries / this open repository)
and confirm alignment with OpenAI's sharing-&-publication policy. Keeping the harness public
and the evaluation reproducible strengthens the application.

## 8. Ethics & limitations

- Outputs are research artifacts, **not legal advice**; under Taiwan's Attorney Act Art. 48,
  B2C legal-advice delivery is constrained — keep the study in a research, non-advisory frame.
- Taiwan-law grounding data must be verified by a qualified person; the system's value claim
  is *reduced* fabrication, not zero.
