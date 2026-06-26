#!/usr/bin/env python3
"""
從 GCP Secret Manager 讀取 API 金鑰

用法：
  python scripts/get_secret.py openrouter-api-key

先決條件：
  gcloud auth application-default login  # 或使用 compute service account
"""

import sys
import os
from google.cloud import secretmanager


def get_secret(secret_name: str, project: str = "gen-lang-client-0435318113") -> str:
    """從 Secret Manager 讀取機密"""
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project}/secrets/{secret_name}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")


def load_env(project: str = "gen-lang-client-0435318113") -> dict:
    """載入所有 zhiyan-legal 需要的環境變數"""
    secrets_map = {
        "OPENAI_API_KEY": "openai-api-key",
        "OPENROUTER_API_KEY": "openrouter-api-key",
        "GEMINI_API_KEY": "gemini-api-key",
        "NVIDIA_API_KEY": "nvidia-api-key",
        "GMAIL_APP_PASSWORD": "gmail-app-password",
    }
    env = {}
    for env_var, secret_name in secrets_map.items():
        try:
            env[env_var] = get_secret(secret_name, project)
        except Exception:
            print(f"  ⚠️ 無法讀取 {secret_name}（不存在或無權限）")
    return env


if __name__ == "__main__":
    if len(sys.argv) > 1:
        val = get_secret(sys.argv[1])
        print(val)
    else:
        env = load_env()
        print("已載入的金鑰：", ", ".join(env.keys()))
        # 寫入臨時 .env（僅供呼叫用）
        with open(".env.gcp", "w") as f:
            for k, v in env.items():
                f.write(f"{k}={v}\n")
        print("已寫入 .env.gcp（已 .gitignore）")
