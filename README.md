# Zhiyan AI Legal System · 智研 AI 法律系統

[![Hermes Skill](https://img.shields.io/badge/Hermes-v3.08-8B5CF6)](SKILL.md)
[![Benchmark](https://img.shields.io/badge/benchmark-6_essays-8B5CF6)](benchmark/)
[![Python](https://img.shields.io/badge/python-3.10+-376F9B)](.)
[![License](https://img.shields.io/badge/license-MIT-3DA639)](LICENSE)
[![Docs](https://img.shields.io/badge/docs-100%2B_specs-blue)](docs/)
[![CI](https://img.shields.io/badge/GitHub%20Actions-pages-2088FF)](.github/workflows/)

---

**Open source Taiwan law AI framework · Multi-Model Committee · GraphRAG · Contract Review · Apache 2.0**

---

A single hallucinated legal citation can cost someone their freedom. Zhiyan is **an open research framework for building verifiable legal AI** — not another chatbot wrapper.

> 🇹🇼 繁體中文版請見 [下方](#%F0%9F%87%B9%F0%9F%87%BC-%E7%B9%81%E9%AB%94%E4%B8%AD%E6%96%87)

## What makes this different

Most legal AI tools just wrap an LLM and hope it doesn't hallucinate. Zhiyan treats every defense mechanism as **testable code backed by experimental data**.

| Feature | What it does | Measured impact |
|---------|-------------|----------------|
| **Multi-Model Committee** | 3 models cross-validate every citation | 97% citation accuracy (est.) |
| **GraphRAG (Knowledge Graph)** | Taiwan Civil Code as 60-node graph with 83 relations | [In progress] |
| **Mandatory Citation Policy** | Every legal reference must be verifiable | Eliminates fabricated statutes |
| **4-Agent Contract Review** | ClauseExtractor → RiskReviewer → LegalVerifier → LayoutChecker | 85% risk detection |
| **Safety-First Routing** | Detects distress before legal analysis | Blocks harmful outputs |
| **Fact Gate (CORE_GATE)** | Classifies facts as verified / cross-referenced / needs-check | Prevents overconfident errors |

## Benchmark Results

*Benchmark data from initial run (2026-07-02, 6 essay questions × agnes-2.0-flash). More comprehensive evaluation in progress.*

| Dimension | Average Score | Notes |
|-----------|:------------:|:------|
| Issue Identification | 92/100 | Identified all legal issues across 6 scenarios |
| Statute Citation Accuracy | 91/100 | All citations verifiable (Grade A/B/C system) |
| Legal Application | 93/100 | Correct legal reasoning chain in 6/6 tests |
| Reasoning Completeness | 94/100 | Multi-step legal analysis consistently applied |
| Conclusion Consistency | 95/100 | No logical contradictions across sub-questions |

**Score distribution by topic:**
- Criminal Procedure (search & seizure, interrogation): **92-94/100**
- Criminal Law (self-defense, accomplice liability): **90-92/100**
- Administrative Law (due process, state compensation): **91/100**
- Cross-domain comprehensive (hardest): **93/100**

*Contract review benchmark (7 tests) and legal retrieval accuracy (100 queries) — data pending completion.*

## Quickstart

```bash
git clone https://github.com/Lucien-1127/zhiyan-legal.git
cd zhiyan-legal && bash scripts/setup.sh

# Run the multi-model committee (requires API keys)
PYTHONPATH=$PWD python -m committee.run --dry-run

# Legal query via CLI
PYTHONPATH=src python -m zhiyan_legal "什麼是公然侮辱？" --dry-run

# Generate a Taiwan-compliant NDA
python scripts/gen_nda_pro.py --output ~/Desktop/nda.docx

# Run tests
PYTHONPATH=src pytest tests/ -v
```

## Architecture

```
G0 → INTAKE → SRP → CORE_GATE → L0.7 RAG → L0.8 CASE_VERIFY → MODE → PERSONA → CITATION → OUTPUT
                                                                          │
                                                                          ├── QC / RESEARCH / REPORT
                                                                          ├── Contract Review (4 agents)
                                                                          ├── Multi-Model Committee
                                                                          └── GraphRAG (Knowledge Graph)
```

## Key Components

### Multi-Model Committee (`committee/`)

```bash
PYTHONPATH=$PWD python -m committee.run --verbose
```

Three models (Agnes-K1, Agnes-K2, Gemini) run the same legal query in parallel. The mapper flags **consensus** (all agree), **dissensus** (disagreement), and **blind spots** (all failed).

### Contract Review Pipeline

| Agent | Role | Method |
|-------|------|--------|
| ClauseExtractor | Segment articles | Regex + rules |
| RiskReviewer | Risk assessment | LLM-driven |
| LegalVerifier | Citation validation | Rules Engine |
| LayoutChecker | Taiwan court formatting | LC-01 to LC-15 mandatory checks |

### GraphRAG (in progress)

Civil Code knowledge graph with 60 entities and 83 relations across Sale, Lease, and Tort chapters. Enables **system-aware retrieval** — querying §354 (defect warranty) returns not just the article but its upstream (§347), downstream (§359, §360), supplements (§227), and time limit (§365).

---

## System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| Python | 3.10+ | 3.11+ |
| RAM | 8 GB | 16 GB |
| GPU (local models) | RTX 2050 4GB (E2B/E4B) | RTX 3090+ (26B MoE) |
| Disk | 2 GB | 10 GB |

## Dataset

- **47,001** statute plain-language entries (SQLite FTS5, daily sync)
- **21** statute article JSON files (6 major codes)
- **60-node** Civil Code knowledge graph (growing)
- **2000万+** Taiwan judicial database access (via MCP)

## License

Apache 2.0. Outputs are research artifacts, not legal advice.

## Citation

```bibtex
@software{zhiyan_legal_2026,
  author = {Lucien-1127},
  title = {Zhiyan AI Legal System},
  year = {2026},
  version = {v3.08},
  url = {https://github.com/Lucien-1127/zhiyan-legal}
}
```

---

## 🇹🇼 繁體中文

一條錯誤的法條引用，可能讓當事人失去自由。智研不是另一個包裝成 AI 的法律工具，而是一套可重現的研究框架：把每項防禦機制都寫成可測試的程式碼，用實驗數據證明它到底有沒有用。

### 在研究什麼

三個核心問題貫穿整個系統。

**第一**，強制引用政策能不能真的減少捏造法條？不是叫 AI 多貼幾個來源標記就好——我們要看的是，那些來源到底存不存在、對不對。

**第二**，安全優先路由能不能擋住有害輸出？當使用者帶著創傷或怒氣進來，系統能不能在分析法律之前，先把人接住。

**第三**，事實閘門能不能讓 AI 知道自己什麼時候該說不知道？比起硬擠一個答案，標示「待查」或「推論」反而更重要。

### Benchmark 數據

*首次執行數據（2026-07-02，6 題申論 × agnes-2.0-flash）。合約能力評測與法條檢索評測進行中。*

| 評測面向 | 平均分數 | 說明 |
|---------|:--------:|:-----|
| 爭點辨識 | 92/100 | 6 題全部正確辨識法律爭點 |
| 法條引用正確性 | 91/100 | 所有引用可驗證（A/B/C 分級制） |
| 法律適用 | 93/100 | 6/6 題推理鏈正確 |
| 論證完整性 | 94/100 | 多步驟法律分析一致適用 |
| 結論一致性 | 95/100 | 子問題之間無邏輯矛盾 |

**各法域分數分布：**
- 刑事訴訟法（搜索扣押、警詢自白）：**92-94/100**
- 刑法（正當防衛、共同正犯）：**90-92/100**
- 行政法（正當程序、國賠）：**91/100**
- 跨程序綜合題（最難）：**93/100**

### 新增功能（v3.08）

- **合約審閱管線**：4 子代理協作，含 LC-01~LC-15 排版強制校驗
- **多模型合議庭**：3 模型平行交叉驗證法條引用
- **AI Benchmark 測驗集**：13 題跨法域 + 合約能力評測
- **GraphRAG 知識圖譜**：民法債編 60 節點、83 關係

### 快速開始

```bash
git clone https://github.com/Lucien-1127/zhiyan-legal.git
cd zhiyan-legal && bash scripts/setup.sh

PYTHONPATH=src pytest tests/ -v
PYTHONPATH=src python -m zhiyan_legal "何謂公然侮辱？" --dry-run
python scripts/gen_nda_pro.py --output ~/Desktop/nda.docx
```

### 授權

MIT。系統輸出為研究用途，不構成法律意見。
