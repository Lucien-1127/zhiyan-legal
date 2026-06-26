#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# 智研AI法律工作站 — 一鍵安裝腳本
# ═══════════════════════════════════════════════════════════════════
# 支援任何 OpenAI-compatible API Provider
# ═══════════════════════════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

echo "═══════════════════════════════════════════════════"
echo "  智研AI法律工作站 — 安裝腳本"
echo "  Zhiyan AI Legal System — Setup"
echo "═══════════════════════════════════════════════════"
echo ""

# ── 1. Python venv ──
if [ ! -d ".venv" ]; then
    echo "🔧 建立 Python 虛擬環境..."
    python3 -m venv .venv
fi
source .venv/bin/activate

# ── 2. Dependencies ──
echo "📦 安裝相依套件..."
pip install -q -r requirements.txt

# ── 3. Environment ──
if [ ! -f ".env" ]; then
    echo ""
    echo "⚠️  找不到 .env 設定檔"
    echo ""
    echo "  請選擇你的 API Provider 並設定："
    echo ""
    echo "  ┌─────────────────────────────────────────────────────┐"
    echo "  │  1) OpenAI       — api.openai.com                   │"
    echo "  │  2) OpenRouter   — openrouter.ai (400+ 模型)        │"
    echo "  │  3) DeepSeek V4  — api.deepseek.com                 │"
    echo "  │  4) Google Gemini— generativelanguage.googleapis.com│"
    echo "  │  5) MiniMax M3   — api.minimax.chat                 │"
    echo "  │  6) NVIDIA Nemotron 3 (free) — api.nvidia.com       │"
    echo "  │  7) 自訂端點     — 任何 OpenAI-compatible API       │"
    echo "  └─────────────────────────────────────────────────────┘"
    echo ""
    cp .env.example .env
    echo "📝 已複製 .env.example → .env"
    echo "   請編輯 .env 填入你的 API Key 與端點"
    echo ""
else
    echo "✅ .env 設定檔已存在"
fi

# ── 4. Dry-run test ──
echo ""
echo "🧪 執行乾跑測試 (dry-run) — 0 成本..."
PYTHONPATH=src python -m zhiyan_legal "什麼是公然侮辱罪?" --dry-run 2>&1

echo ""
echo "═══════════════════════════════════════════════════"
echo "✅ 安裝完成！"
echo ""
echo "  使用方法:"
echo "    source .venv/bin/activate"
echo "    PYTHONPATH=src python -m zhiyan_legal \"你的法律問題\""
echo "    PYTHONPATH=src python -m zhiyan_legal \"你的問題\" --dry-run"
echo "    PYTHONPATH=src pytest tests/ -v"
echo ""
echo "  或透過 Hermes Agent:"
echo "    /zhiyan 你的法律問題"
echo "═══════════════════════════════════════════════════"
