#!/bin/bash
# ── 消融實驗啟動腳本 ──
# 先 source .env 再跑實驗

cd "$(dirname "$0")/.."  # 回到專案根目錄
set -a
source .env
set +a
export PYTHONPATH=src
exec python scripts/run_ablation_experiment.py
