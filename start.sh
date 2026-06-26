#!/bin/bash
# ══════════════════════════════════════════════════
# 智研 AI 法律系統 · SaaS 版 — 啟動腳本 (WSL/Linux)
# ══════════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

echo ""
echo "  ╔═══════════════════════════════════════════╗"
echo "  ║   ⚖️  智研 AI 法律系統 · SaaS 版         ║"
echo "  ║       啟動中...                          ║"
echo "  ╚═══════════════════════════════════════════╝"
echo ""

# ─── 檢查 .env ──────────────────────────────────
if [ ! -f "$BACKEND_DIR/.env" ]; then
    echo "⚠️  未發現 .env 設定檔"
    echo "   複製範本並填入 API 金鑰："
    echo "   cp $BACKEND_DIR/.env.example $BACKEND_DIR/.env"
    echo "   然後編輯 $BACKEND_DIR/.env"
    echo ""
    echo "   使用預設值 (DeepSeek) 繼續啟動..."
fi

# ─── 虛擬環境 ─────────────────────────────────────
VENV_DIR="$BACKEND_DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "📦 建立虛擬環境..."
    python3 -m venv "$VENV_DIR"
    echo "✅ 虛擬環境已建立"
fi

# ─── 安裝依賴 ────────────────────────────────────
echo "📦 安裝相依套件..."
source "$VENV_DIR/bin/activate"
pip install -q -r "$BACKEND_DIR/requirements.txt" 2>/dev/null
echo "✅ 相依套件已安裝"

# ─── 啟動服務 ────────────────────────────────────
cd "$BACKEND_DIR"
echo ""
echo "  🌐 服務位址：http://localhost:8000"
echo "  🛑 Ctrl+C 停止服務"
echo ""
echo "═══════════════════════════════════════════════"
echo ""

# 載入 .env（若存在）
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi

export ZHIYAN_API_BASE_URL="${ZHIYAN_API_BASE_URL:-https://api.deepseek.com/v1}"
export ZHIYAN_MODEL="${ZHIYAN_MODEL:-deepseek-chat}"

python -m uvicorn main:app --host "${APP_HOST:-0.0.0.0}" --port "${APP_PORT:-8000}" --reload
