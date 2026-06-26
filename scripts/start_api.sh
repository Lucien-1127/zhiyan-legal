#!/bin/bash
# 啟動法規異動監控 API
cd /home/hsieh89t_gmail_com/zhiyan-legal
PYTHONPATH=/home/hsieh89t_gmail_com/zhiyan-legal/src \
  /home/hsieh89t_gmail_com/.hermes/hermes-agent/venv/bin/python3 \
  -m uvicorn zhiyan_legal.regulation_api:app \
  --host 127.0.0.1 --port 7850 \
  >> /home/hsieh89t_gmail_com/zhiyan-legal/data/api.log 2>&1
