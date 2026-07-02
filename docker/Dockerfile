# 智研 AI 法律系統 API

> 將 zhiyan-legal 打包為 Cloud Run API 服務

FROM python:3.11-slim

WORKDIR /app

# PYTHONPATH 讓 src/ 內模組可透過 zhiyan_legal.* 匯入
ENV PYTHONPATH=/app/src

# 安裝系統相依
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 複製專案
COPY pyproject.toml requirements.txt ./
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY knowledge/ ./knowledge/
COPY prompts/ ./prompts/
COPY agents/ ./agents/

# 安裝 Python 套件
RUN pip install --no-cache-dir -r requirements.txt uvicorn fastapi

# API 入口（使用 FastAPI）
COPY docker/api_server.py ./api_server.py

# 非 root 執行
RUN useradd -m -u 1000 zhiyan && chown -R zhiyan:zhiyan /app
USER zhiyan

EXPOSE 8080
CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8080"]
