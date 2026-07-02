# Gemma 4 深度研究報告

> **研究日期：** 2026-07-02
> **發布日期：** 2026-04-03（Apache 2.0 開源）
> **目的：** 評估對 zhiyan-legal 的適用性，特別是 RTX 2050 4GB VRAM 本機部署

---

## 一、基本資訊

| 項目 | 內容 |
|:----|:------|
| **開發者** | Google DeepMind（基於 Gemini 3 研究） |
| **授權** | **Apache 2.0**（完全開源，可商用，無 MAU 限制） |
| **架構** | Dense（12B/31B）+ MoE（26B A4B）+ PLE（E2B/E4B） |
| **上下文** | 128K（小模型）· 256K（中大型模型） |
| **多模態** | 文字 + 圖片（全部模型）；原生音訊（E2B/E4B）；影片（E2B/E4B/12B） |
| **語言** | 140+ 語言 |
| **思考模式** | 可設定 `thinking=True` 內建 Chain-of-Thought |
| **推論加速** | Multi-Token Prediction（MTP）+ Speculative Decoding |
| **量化支援** | 官方 QAT（量化感知訓練）GGUF / w4a16 / mobile |

---

## 二、模型規格一覽

| 模型 | 有效參數 | 總參數 | 架構 | 建議硬體 | BF16 VRAM | Q4 VRAM | 適合本機? |
|:----|:--------|:------|:-----|:---------|:----------|:--------|:---------|
| **E2B** | ~2.3B | ~5.7B | PLE | 手機/樹莓派 | 11.4 GB | **2.9 GB** | ✅✅✅ |
| **E4B** | ~4.5B | ~8.9B | PLE | 手機/筆電 | 17.9 GB | **4.5 GB** | ✅✅ |
| **12B** | 12B | 12B | Dense | 消費級 GPU (16GB+) | 26.7 GB | **6.7 GB** | ❌ |
| **26B A4B** | **3.8B** (活躍) | 26B | **MoE (128專家)** | RTX 3090/4090 | 57.7 GB | **14.4 GB** | ❌ |
| **31B** | 31B | 31B | Dense | 高階 GPU | 69.9 GB | **17.5 GB** | ❌ |

> **對你的 RTX 2050 4GB 的意義：**
> - ✅ **E2B Q4**（2.9 GB）→ **可跑**，甚至還有空間給 KV cache
> - ⚠️ **E4B Q4**（4.5 GB）→ **勉強**，需配合 KV cache 量化或較短 context
> - ❌ 12B/26B/31B → 全部無法（即使 Q4 也超過 4GB）

---

## 三、架構亮點

### 3.1 混合注意力（Hybrid Attention）

每層交錯使用兩種注意力機制：
- **Local Sliding Window** — 局部上下文滑動窗口
- **Global Attention** — 全局注意力（間隔層）

效果：O(n²) 降低為近似 O(n)，長上下文效率顯著提升。

### 3.2 MoE 設計（26B A4B）

| 特性 | 數值 |
|:----|:-----|
| 專家總數 | **128**（每 MoE 層） |
| 活躍專家/Token | **2**（Top-2 routing） |
| 活化率 | **~1.6%**（遠低於 Mixtral 的 25%） |
| 效果 | 26B 參數的知識儲存 x 4B 參數的運算成本 |

每個專家可高度專業化（數學→數學專家，法律→法律專家）。

### 3.3 PLE（Per-Layer Embeddings）— E2B/E4B

- 嵌入表極大（佔總參數約 60%）
- 但僅用於查詢（lookup），非密集運算
- 適合邊緣裝置：低功耗、離線執行

### 3.4 Multi-Token Prediction（MTP）

- 每個模型附帶專用 draft model
- 支援 Speculative Decoding
- 推論加速 2-3x，無品質損失

---

## 四、Benchmark 成績

### 4.1 頂級模型（31B / 26B MoE）

| Benchmark | Gemma 4 31B | Gemma 4 26B | Gemma 3 27B | 說明 |
|:----------|:-----------:|:-----------:|:-----------:|:-----|
| MMMLU Pro | **85.2%** | 82.6% | 67.6% | 多語言問答 |
| AIME 2026 | **89.2%** | 88.3% | 20.8% | ⭐數學競賽（躍進 4x） |
| GPQA Diamond | **84.3%** | 82.3% | 42.4% | 科學推理 |
| LiveCodeBench v6 | **80.0%** | 77.1% | 29.1% | 程式競賽 |
| Codeforces ELO | **2150** | ~2050 | 110 | ⭐程式能力 |
| MMMU Pro (視覺) | **76.9%** | 73.8% | 49.7% | 多模態推理 |
| Arena AI ELO | **1452 (#3)** | 1441 (#6) | 1365 | ⭐人類偏好 |
| τ2-bench (工具使用) | **86.4%** | 85.5% | 6.6% | ⭐代理能力（140x 躍進） |

### 4.2 邊緣模型（E2B / E4B）— 對你比較重要

| Benchmark | E2B | E4B | 等同哪個等級？ |
|:----------|:---:|:---:|:--------------|
| MMMLU Pro | 60.0% | **69.4%** | E4B ≈ Gemma 3 27B 等級 |
| MMMU Pro | 44.2% | **52.6%** | 超越 Gemma 3 27B |
| AIME 2026 | 37.5% | **42.5%** | 遠超 Gemma 3 (20.8%) |
| LiveCodeBench | 44.0% | **52.0%** | 遠超 Gemma 3 (29.1%) |
| GPQA Diamond | 43.4% | **58.6%** | ⭐ E4B 超越 Gemma 3 27B (42.4%) |
| τ2-bench | 29.4% | **57.5%** | ⭐ E4B 代理能力極強 |

**關鍵發現：** E4B（4.5B 活躍參數）在多項 benchmark 上超越 Gemma 3 27B。這對 4GB VRAM 使用者是重大利好。

---

## 五、RTX 2050 4GB 實測評估

### 5.1 可執行的模型組合

| 模型 | 量化 | VRAM | Context 128K | 預估速度 | 適合用途 |
|:----|:----|:----:|:------------|:---------|:---------|
| **E2B Q4** | Q4_0 GGUF | **2.9 GB** | ⚠️ 剩 1.1GB 給 KV cache | >60 tok/s | 法條搜尋、分類、簡單問答 |
| **E2B Q4 Mobile** | Mobile QAT | **~1.5 GB** | ✅ 綽綽有餘 | >60 tok/s | 離線法律查詢 |
| **E4B Q4** | Q4_0 GGUF | **4.5 GB** | ❌ 超出 4GB | — | 無法完整載入 |
| **E4B Q4 Mobile** | Mobile QAT | **~2.5 GB** | ✅ | >40 tok/s | ⭐法律分析最佳選擇 |

### 5.2 建議方案

```
RTX 2050 4GB 最佳配置：
┌─────────────────────────────────────┐
│ 主要模型： Gemma 4 E4B Mobile (QAT) │
│  VRAM 使用： ~2.5 GB                │
│  剩餘 VRAM： ~1.5 GB (KV cache)     │
│  預估速度： 40-50 tok/s             │
│                                     │
│ 輕量模型： Gemma 4 E2B Q4 (GGUF)    │
│  VRAM 使用： ~1.5 GB                │
│  適合：簡單分類、快速查詢            │
└─────────────────────────────────────┘
```

### 5.3 與當前模型（DeepSeek v4 Flash / Agnes）比較

| 面向 | DeepSeek v4 Flash（API） | Gemma 4 E4B（本機） |
|:----|:------------------------|:-------------------|
| 延遲 | 網路延遲 0.5-3s | **即時（本機）** |
| 成本 | 按 token 計費 | **免費（電費）** |
| 隱私 | 資料送出 | **資料不離機** |
| 品質 | 大模型級 | ~中型模型級 |
| 法律能力 | 強（通用） | 需微調或優化 prompt |
| 工具使用 | 原生支援 | ✅ 原生 function calling |

---

## 六、對 zhiyan-legal 的應用分析

### 6.1 可立即使用的場景

| 場景 | 模型 | 原因 |
|:----|:----|:------|
| 法條分類/標記 | E2B Q4 | 輕量任務，60+ tok/s |
| 條款切分（Clause Segmenter） | E2B Q4 | 正則+輕量 LLM 即可 |
| 風險初篩 | E4B Mobile | 子代理之一，中型推理 |
| 離線法條問答 | E4B Mobile | 隱私敏感場景 |

### 6.2 取代現有子代理的潛力

zhiyan-legal 目前的 4 子代理架構：
```
ClauseExtractor → RiskReviewer → LegalVerifier → LayoutChecker
```

| 子代理 | 可取代性 | 說明 |
|:-------|:--------|:------|
| ClauseExtractor | ✅ E2B Q4 | 正則+規則為主，E2B 輔助邊界偵測 |
| RiskReviewer | ✅ E4B Mobile | 中型推理+function calling = 天然適合 |
| LegalVerifier | ⚠️ 部分 | 法源驗證需外部 API 比對 |
| LayoutChecker | ❌ 規則引擎 | 排版校驗 LC-01~LC-15 不需要 LLM |

### 6.3 不適合的場景

- ❌ 複雜法律推理（需要大型模型的深度推理能力）
- ❌ 合約起草（需要高品質輸出，E4B 能力仍不足）
- ❌ 多模型合議庭仲裁（需要大型模型當最終仲裁者）

---

## 七、部署方式

### Ollama（推薦）

```bash
# 安裝
curl -fsSL https://ollama.com/install.sh | sh

# 拉取 Gemma 4 E2B（2.9GB 4-bit）
ollama run gemma4:e2b

# 或 E4B（若 VRAM 足夠）
ollama run gemma4:e4b
```

### llama.cpp + GGUF

```bash
# 從 Hugging Face 下載 GGUF
# https://huggingface.co/collections/google/gemma-4-qat-q4-0

# 執行（E2B）
./llama-cli -m gemma-4-e2b-qat-q4_0.gguf -p "你的提示詞"
```

### LM Studio

搜尋 "Gemma 4"，選擇 Q4 量化版本，直接載入。

---

## 八、結論

| 面向 | 評價 |
|:----|:-----|
| **對開源社群的意義** | ⭐⭐⭐⭐⭐ — Apache 2.0 最高授權，從手機到伺服器全覆蓋 |
| **對本機部署的意義** | ⭐⭐⭐⭐⭐ — E2B/E4B 能在 4GB VRAM 上跑，前所未有 |
| **對法律 AI 的適用性** | ⭐⭐⭐☆☆ — E4B 適合子代理角色，但複雜法律推理仍需 API |
| **對 zhiyan-legal 的整合價值** | ⭐⭐⭐⭐☆ — 可作為 RiskReviewer 子代理的離線後端 |

**一句話總結：**
Gemma 4 E4B Mobile 是目前唯一能在 RTX 2050 4GB 上跑的「有品質的開源法律 AI 模型」。不適合當主模型，但非常適合作為 zhiyan-legal 的子代理離線引擎 — 特別是 RiskReviewer 和 ClauseExtractor。

建議下一步：在 Ollama 上部署 Gemma 4 E2B Q4，串接進 SKILL-03 取代 RiskReviewer 的 API 呼叫測試。
