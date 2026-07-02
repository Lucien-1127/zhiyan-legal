---
title: 智研 AI 法律系統 · Zhiyan AI Legal System
description: 以分層架構、強制引用與安全路由為核心的台灣法律 AI 研究平台。
license: MIT
authors:
  - 謝小育 (Lucien-1127) <Lucien127@proton.me>
repository: https://github.com/Lucien-1127/zhiyan-legal
---

# 智研 AI 法律系統 · Zhiyan AI Legal System

[![Hermes Skill](https://img.shields.io/badge/Hermes-v3.08-8B5CF6)](SKILL.md)
[![Docs](https://img.shields.io/badge/docs-100%2B_specs-blue)](docs/)
[![MkDocs](https://img.shields.io/badge/MkDocs-Material-0094F5)](https://lucien-1127.github.io/zhiyan-legal/)
[![Wiki](https://img.shields.io/badge/wiki-6_pages-2E8B57)](docs/wiki/)
[![Python](https://img.shields.io/badge/python-3.10+-376F9B)](.)
[![License](https://img.shields.io/badge/license-MIT-3DA639)](LICENSE)
[![Benchmark](https://img.shields.io/badge/benchmark-6_essays-8B5CF6)](benchmark/)
[![Contract Benchmark](https://img.shields.io/badge/contract_benchmark-7_tests-8B5CF6)](benchmark/contract-benchmark.md)
[![CI](https://img.shields.io/badge/GitHub%20Actions-pages-2088FF)](.github/workflows/)

<p align="center">
  <img src="docs/banner.png" alt="智研AI法律工作站" width="100%">
</p>

---

<details open>
<summary><b>🇹🇼 繁體中文</b></summary>

一條錯誤的法條引用，可能讓當事人失去自由，也可能讓一份書狀被打回。法律 LLM 的幻覺不是技術瑕疵——它是真實的損害。

智研就是為了解決這個問題而生的。它不是另一個包裝成 AI 的法律工具，而是一套可重現的研究框架：把每項防禦機制都寫成可測試的程式碼，用實驗數據證明它到底有沒有用。

## 在研究什麼

三個核心問題貫穿整個系統。

第一，強制引用政策能不能真的減少捏造法條？不是叫 AI 多貼幾個來源標記就好——我們要看的是，那些來源到底存不存在、對不對。

第二，安全優先路由能不能擋住有害輸出？當使用者帶著創傷或怒氣進來，系統能不能在分析法律之前，先把人接住。

第三，事實閘門能不能讓 AI 知道自己什麼時候該說不知道？比起硬擠一個答案，標示「待查」或「推論」反而更重要。

這三題的答案，都寫在每次提交的實驗數據裡。

## 系統怎麼運作

從使用者丟一句話進來，到產出結構化的法律分析，中間經過七層關卡。

最前面是信心檢查——沒有把握的事，系統會直接告訴你它不知道，不硬擠。接著是安全路由，把高風險的發言導入專門的對話處理流程，不再繼續法律分析。

過了安全關之後，核心閘門開始做事：把使用者說的事實分級（哪些是可以追查的、哪些是推測的）、抓出五個關鍵要素（人、事、時、地、果），再判斷案件落在哪個法域。如果是跨域案件，有一套優先序來決定誰是主法域、誰是輔助。

這一層現在還多了兩個新功能：程序階段偵測——確認案件是尚未處理、已報案、已開庭還是已判決——以及一套禁止事項，防止在事實不足時就下結論。

打完基礎後，系統會去查本機端的法條白話資料庫——四萬七千多條，每天同步。遇到爭議性條文，還會用 MCP 協議直接連司法院的判決查詢系統拉真實判決，同時強制檢查憲法法庭的最新見解。

最後，根據使用者的問題類型，系統會選擇適合的模式來回應：是要做品質檢查、法律研究、報告產出，還是出題考試、批改申論、模擬法庭——甚至連寫一篇申論示範答案都行。如果主題不是法律而是科普或商業，還有一個專門的提示詞工程模式，幫你生成客製化的寫手指令。

### 新增功能（v3.08）

- **合約審閱管線**：ClauseExtractor → RiskReviewer → LegalVerifier → LayoutChecker 四個子代理協作，含 LC-01~LC-15 排版強制校驗
- **多模型合議庭（committee/）**：3 模型平行交叉驗證法條引用，標示共識／分歧／盲區
- **AI Benchmark 申論題測驗集**：6 題跨法域（刑訴、刑法、行政法）按 6 項評分標準自動評測
- **prompts/modes/router.json**：12 個 task_mode 對應提示詞路徑，統一路由入口

## 可以怎麼用

### Hermes Agent（法律問題直接問）

```text
請分析這個契約有沒有風險
什麼是公然侮辱罪？
```

### 合約產生（CLI）

```bash
python scripts/gen_nda_pro.py                          # 預設 NDA
python scripts/gen_nda_pro.py --output ./nda.docx      # 自訂路徑
python scripts/gen_nda_pro.py --compact --party-a "XXX" # 緊湊排版
```

### 多模型合議庭

```bash
cd zhiyan-legal
PYTHONPATH=$PWD python -m committee.run --dry-run              # 預覽
PYTHONPATH=$PWD python -m committee.run                        # 完整執行
PYTHONPATH=$PWD python -m committee.run --categories correct_query  # 指定類別
```

### 跑實驗

```bash
git clone https://github.com/Lucien-1127/zhiyan-legal.git
cd zhiyan-legal && bash scripts/setup.sh

PYTHONPATH=src pytest tests/ -v
PYTHONPATH=src python -m zhiyan_legal "什麼是公然侮辱？" --dry-run
```

### AI Benchmark（測試法律推理能力）

```bash
# 申論題測驗（6 題跨法域）
# 見 benchmark/essay-questions.md

# 合約能力測驗（7 題，含終極壓力測試）
# 見 benchmark/contract-benchmark.md
```

## 想更深入

完整的文件放在 [MkDocs 站台](https://lucien-1127.github.io/zhiyan-legal/)。如果想了解整個架構怎麼設計、引用政策怎麼運作、壓力測試結果如何，那裡有上百份規格文件可以翻。

## 引用

```bibtex
@software{zhiyan_legal_2026,
  author = {謝小育 (Lucien127@proton.me)},
  title = {Zhiyan AI Legal System},
  year = {2026},
  version = {v3.08},
  url = {https://github.com/Lucien-1127/zhiyan-legal}
}
```

## 授權

MIT。系統輸出為研究人工製品，不構成法律意見。

</details>

---

<details>
<summary><b>🇬🇧 English</b></summary>

A single hallucinated legal citation can cost someone their freedom or get a brief rejected. For legal LLMs, hallucination isn't a quality issue — it's real harm.

Zhiyan was built to address that. It's not another AI wrapper for legal tasks. It's a reproducible research framework where every defense mechanism is written as testable code, backed by experimental data.

## Research Questions

Three questions drive the system.

First, does a mandatory citation policy actually reduce fabricated statutes? Not just formatting citations — verifying whether those citations exist.

Second, does priority safety routing reduce harmful outputs? When someone brings trauma or anger into a conversation, can the system respond to the human before analyzing the law?

Third, does a fact gate improve how AI calibrates uncertainty? Knowing when to say "this needs verification" matters more than forcing an answer.

## Architecture

Input passes through seven layers before producing a structured legal analysis.

A confidence gate comes first — if the system can't answer, it says so. Then safety routing diverts high-risk input to specialized handling.

The core gate classifies facts (verifiable vs.推测), extracts five elements (who, when, where, what, result), and determines jurisdiction. For cross-domain cases, a priority chain decides which domain leads. Program stage detection checks whether the case is pending, filed, in trial, or已判決.

From there, a local RAG database of 47,001 statute plain-language entries is queried. For contested provisions, the system connects directly to Taiwan's judicial judgment database via MCP protocol, with mandatory constitutional court checks for fundamental rights cases.

Finally, the mode router selects the right response pattern: QC, research, report, essay grading, moot court, or contract review.

### New in v3.08

- **Contract Review Pipeline**: 4-agent collaboration (ClauseExtractor → RiskReviewer → LegalVerifier → LayoutChecker) with mandatory LC-01~LC-15 layout checks
- **Multi-Model Committee**: 3-model parallel citation verification, flagging consensus/dissensus/blind spots
- **AI Benchmark Suite**: 6 cross-domain essay questions with 6-dimension scoring rubric
- **Unified Router**: `prompts/modes/router.json` mapping 12 task_modes to prompt paths

## Quickstart

```bash
git clone https://github.com/Lucien-1127/zhiyan-legal.git
cd zhiyan-legal && bash scripts/setup.sh

PYTHONPATH=src pytest tests/ -v
PYTHONPATH=src python -m zhiyan_legal "What is public insult?" --dry-run
```

### Multi-Model Committee

```bash
PYTHONPATH=$PWD python -m committee.run --verbose
```

## Citation

```bibtex
@software{zhiyan_legal_2026,
  author = {謝小育 (Lucien127@proton.me)},
  title = {Zhiyan AI Legal System},
  year = {2026},
  version = {v3.08},
  url = {https://github.com/Lucien-1127/zhiyan-legal}
}
```

## License

MIT. Outputs are research artifacts, not legal advice.

</details>
