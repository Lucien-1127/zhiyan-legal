# 🤖 代理整合

智研支援多種 AI 代理整合方式：

## Hermes Agent

安裝智研技能後，直接在對話中使用：

```
/zhiyan 分析這份合約
```

詳細安裝方式請參考 `SKILL.md`。

## Claude Code

```bash
cd zhiyan-legal
claude -p "執行所有測試"
claude -p "分析刑法第271條的構成要件"
```

## Gemini CLI

```bash
cd zhiyan-legal
gemini -p "查詢公然侮辱的相關判決"
```

## OpenClaw / Codex

1. 載入智研提示詞系統
2. 根據需求選擇對應人格
3. 執行查詢或分析

## 通用整合流程

```yaml
# 所有代理共用同一套：
prompts/       # 提示詞系統
  personas/    # 人格定義
  workflows/   # 工作流程
  modes/       # 操作模式

knowledge/     # 知識庫
  statutes/    # 法條
  case_law/    # 判決
  glossary/    # 詞彙
```
