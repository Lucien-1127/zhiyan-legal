#!/bin/bash
# ── Run ablation experiment with output logging ──
cd /home/hsieh89t_gmail_com/zhiyan-legal
source .venv/bin/activate
exec python3 -u scripts/run_ablation_v2.py > /tmp/exp_output.log 2>&1
