#!/usr/bin/env python3
"""Test Gemini OpenAI - full response debug."""
import json, os, subprocess, urllib.request

out = subprocess.run(
    ["grep", "-A1", "gemini:", os.path.expanduser("~/.hermes/profiles/lenien-gcp/config.yaml")],
    capture_output=True, text=True
).stdout
key = [l for l in out.split("\n") if "api_key" in l][0].split("api_key:")[1].strip()

url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
auth = "Bearer " + key

payload = {
    "model": "gemini-2.5-flash",
    "messages": [{"role": "user", "content": "Say only HELLO"}],
    "max_tokens": 20
}

req = urllib.request.Request(
    url, data=json.dumps(payload).encode(),
    headers={"Authorization": auth, "Content-Type": "application/json"},
    method="POST"
)

with urllib.request.urlopen(req, timeout=20) as resp:
    raw = resp.read().decode()
    data = json.loads(raw)

print("=== Full response ===")
print(json.dumps(data, indent=2, ensure_ascii=False))
