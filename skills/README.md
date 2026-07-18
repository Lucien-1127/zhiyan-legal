# Claude Skill 打包版

`skills/zhiyan-legal/` 是本儲存庫「內化」成 [Anthropic Agent Skills](https://support.claude.com/en/articles/12512142) 格式的版本，
可上傳到 claude.ai 後在**網頁、桌面與手機 App** 的 Claude 中使用。

與根目錄的 `SKILL.md`（Hermes Agent Manifest，含 GCP/Telegram/本地 RAG 基礎設施）不同，
此版本只保留 Claude App 環境能實際執行的部分：

- 法律分析核心（G0–G6 鐵律、事實分級、四法融合、最小追問）
- 安全前置路由（L0.5 SRP）
- 引用政策 Citation v2.1（本地 RAG `[T1]` 改為聯網查官方來源）
- 13 種模式路由（QC / RESEARCH / LEGAL_WRITER / CONTRACT / ESSAY_TEST…）
- 台灣合約排版規範（LC-01~LC-15）與合約 Schema（21 類）
- 申論寫作人格

## 結構

```
skills/zhiyan-legal/
├── SKILL.md                        # 技能入口（frontmatter + 核心流程）
└── references/                     # 按需載入的細節文件
    ├── safety-routing.md           # L0.5 安全評分與回應模板
    ├── analysis-pipeline.md        # 四法融合、TYPE-S 審查、品質閘門
    ├── citation-policy.md          # 引用編號體系與禁止項
    ├── modes.md                    # 13 種模式細則
    ├── contract-layout.md          # 台灣合約排版規範 v1.0
    ├── contract-schema.md          # 21 類合約 Schema
    └── writer-persona.md           # 申論寫作人格 prompt
```

## 打包與上傳

```bash
cd skills && zip -r zhiyan-legal.zip zhiyan-legal
```

1. 用瀏覽器（手機瀏覽器也可以）開 **claude.ai → Settings → Capabilities → Skills**
2. 點 **Upload skill**，上傳 `zhiyan-legal.zip`
3. 啟用後，手機 App 的對話中提出法律問題（或輸入「智研」）即會自動觸發

> 需要 Pro / Max / Team / Enterprise 方案，且 Settings 中的 Code execution（含 Skills）功能已開啟。
