"""Zhiyan Legal 儲存庫架構健康檢查 — 4 模型平行審查"""
import asyncio
import json
import sys
import os
import time
from pathlib import Path

# Load env
env_path = Path.home() / ".hermes" / "profiles" / "lenien-gcp" / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, "/home/hsieh89t_gmail_com/zhiyan-legal")

from openai import AsyncOpenAI
import httpx

# ── Repo profile ──────────────────────────────────────
REPO_PROFILE = """
# Zhiyan Legal v3.7.2 — 儲存庫架構摘要

## 基本資料
- 版本: 3.7.2
- 授權: MIT
- Python 要求: >=3.10
- 總 Python 行數: ~6,936 行
- 文檔數: 70+ 份 .md 文件
- 測試: 9 個 pytest 檔案 + 8 個 ablation 腳本

## 目錄結構
```
zhiyan-legal/
├── src/zhiyan_legal/       # 核心套件 (14 檔案, ~3,700 行)
│   ├── __init__.py, __main__.py, cli.py
│   ├── router.py           # 關鍵詞路由 (161 行)
│   ├── runner.py           # LLM API 呼叫器 (306 行)
│   ├── sub_agent.py        # Hermes 子代理協調 (164 行)
│   ├── loader.py           # 文件載入組合 (134 行)
│   ├── manifest.py         # 文件清單與載入順序 (135 行)
│   ├── doc_generator.py    # 文件產生器 (164 行)
│   ├── judicial_api.py     # 司法院 API (203 行)
│   ├── regulation_api.py   # 法規 API (266 行)
│   ├── regulation_diff.py  # 法規差異比對 (697 行)
│   └── regulation_tracker.py # 法規追蹤 (879 行)
│
├── backend/                # SaaS API 層 (2 檔案, ~821 行)
│   ├── engine.py           # Async LLM 引擎 (504 行)
│   └── main.py             # FastAPI 應用 (317 行)
│
├── committee/              # 多模型合議系統 (4 子系統)
│   ├── core.py             # 核心資料結構
│   ├── normalizer.py       # 跨模型正規化
│   ├── mapper.py           # 共識映射
│   ├── runner.py / run.py  # 執行器
│   ├── quota.py            # Token 配額
│   ├── config.yaml         # 設定檔
│   ├── api/                # 合議庭 API
│   └── prompt_optimization/ # 提示詞優化子合議庭
│
├── docs/                   # 系統規格文件 (7 子目錄)
│   ├── 00_入口與總覽/      # 入口文件 (3 份)
│   ├── 10_核心控制層/      # 核心層文件 (7 份)
│   ├── 20_模式與引用層/    # 模式/引用 (6 份)
│   ├── 40_模組與人格層/    # 6 人格 + 模組 (14 份)
│   ├── 60_概念詞條/        # 法律詞條 (33 份)
│   ├── 80_封存參考/        # 歷史版本 (10 份)
│   └── 90_維運治理/        # 維運文件 (9 份)
│
├── tests/                  # 測試
│   ├── test_core.py, test_routing.py, test_*.py (9 份)
│   └── run_ablation_v*.py  (8 份實驗腳本)
│
├── data/articles/          # 22 份法條 JSON
├── docker/                 # Dockerfile
├── .github/workflows/      # CI/CD
├── mkdocs.yml              # 文件站設定
├── pyproject.toml          # 套件設定
└── scripts/                # 部署/實驗腳本
```

## 核心資料流
```
使用者輸入 → router.py (關鍵詞路由)
  → manifest.py (組合對應 system prompt)
  → runner.py (呼叫 LLM API)
  → loader.py (載入 docs/ 文件)
  └→ sub_agent.py (可選的子代理並行)

SaaS 版路徑:
使用者 → backend/main.py (FastAPI)
  → backend/engine.py (Async LLM, 連接池 + retry)
  → loader.py + manifest.py (載入 docs/)
```

## 已知架構特徵
1. **雙路由系統**: router.py (關鍵詞) + manifest.py (文件清單, 路由表 + 排除規則)
2. **雙 LLM 引擎**: runner.py (同步, 舊) + engine.py (非同步, 新, 有連接池)
3. **sub_agent.py** 依賴 Hermes Agent 專屬 delegate_task — 不可攜
4. manifest.py 中有一個 `FIXME: 目前無獨立書狀起草模組文件，暫時指向訴訟策略`
5. docs/ 檔案名稱含版本號 (v1.0.0, v1.1.0, v2.0.0 ...) — 多版本並存
6. 22 個 data/ JSON + 8 個 ablation 腳本但僅 9 個單元測試
7. 無明確 API 版本前綴 (/api/chat 無 v1/v2)
8. mkdocs.yml 列出完整導航但部分導航指向的檔案路徑不存在或已移動
"""

MODELS = {
    "deepseek_v4_flash": ("deepseek-v4-flash", "https://api.deepseek.com/v1", "DEEPSEEK_API_KEY"),
    "gemini_3_5_flash": ("gemini-2.5-flash", "https://generativelanguage.googleapis.com/v1beta/openai", "GEMINI_API_KEY"),
    "claude": ("anthropic/claude-sonnet-4", "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "nvidia": ("nvidia/llama-3.3-nemotron-super-49b-v1", "https://integrate.api.nvidia.com/v1", "NVIDIA_API_KEY"),
}

# ── Review prompts per model ──────────────────────────

REVIEW_PROMPTS = {
    "deepseek_v4_flash": """你是資深 Python 架構審查工程師。請對以下 Zhiyan Legal 儲存庫進行「結構完整性審查」。

重點維度：
1. **目錄結構健康度**: module 邊界是否清晰？命名是否一致？有無過大/過小的模組？
2. **依賴圖純淨度**: import chain 是否合理？有無循環依賴？有無不必要的耦合？
3. **重複或冗餘**: 有無兩個以上的模組做同一件事？
4. **設定管理**: 環境變數 vs 設定檔的使用是否一致？有無硬編碼？
5. **版本與套件化**: pyproject.toml 的依賴管理是否完善？optional dependencies 夠不夠？

以 JSON 格式輸出，key 為 "findings"，value 為陣列：
```json
{
  "findings": [
    {
      "category": "structure|duplication|dependencies|config|packaging",
      "severity": "critical|major|minor",
      "location": "問題位置 (檔案或目錄)",
      "issue": "問題描述 (繁體中文, 40字內)",
      "suggestion": "具體改善建議",
      "confidence": 0.0~1.0
    }
  ]
}
```
請嚴格遵守 JSON 格式。""",

    "gemini_3_5_flash": """你是資深文件工程師，專精程式碼與文件的對齊審查。請對以下 Zhiyan Legal 儲存庫進行「文件完整性審查」。

重點維度：
1. **文件-程式碼對齊**: docs/ 描述的架構 vs 實際程式碼有無落差？
2. **README/mkdocs 準確度**: 導航連結是否有效？描述的 API 是否真的存在？
3. **命名一致性**: 檔案命名規則是否一致？有無中英混雜不一致？
4. **測試覆蓋**: 關鍵邏輯是否有對應測試？測試品質如何？
5. **過期文件**: 封存/舊版文件是否明確標示？有無混淆風險？

以 JSON 格式輸出，key 為 "findings"：
```json
{
  "findings": [
    {
      "category": "doc_code_gap|navigation|naming|test_coverage|outdated_docs",
      "severity": "critical|major|minor",
      "location": "問題位置",
      "issue": "問題描述 (繁體中文, 40字內)",
      "suggestion": "具體改善建議",
      "confidence": 0.0~1.0
    }
  ]
}
```
請嚴格遵守 JSON 格式。""",

    "claude": """你是頂尖的系統安全與錯誤處理審查專家。請對以下 Zhiyan Legal 儲存庫進行「錯誤處理與邊界壓力測試審查」。

重點維度：
1. **例外處理**: API 金鑰缺失、網路斷線、API 錯誤的回退策略是否完善？
2. **SaaS API 防護**: rate limit 設定是否合理？有無防禦 SSRF/注入攻擊？
3. **資源洩漏**: 連線池、檔案句柄是否正確關閉？有無 async/sync 混用風險？
4. **測試缺口**: 哪些關鍵路徑完全沒有測試？ablation 實驗 vs 單元測試的平衡？
5. **sub_agent 安全**: sub_agent.py 的 Hermes 依賴若不存在時的行為？

以 JSON 格式輸出，key 為 "findings"：
```json
{
  "findings": [
    {
      "category": "exception_handling|security|resource_leak|test_gap|dependency_risk",
      "severity": "critical|major|minor",
      "location": "問題位置",
      "issue": "問題描述 (繁體中文, 40字內)",
      "suggestion": "具體改善建議",
      "confidence": 0.0~1.0
    }
  ]
}
```
請嚴格遵守 JSON 格式。""",

    "nvidia": """你是一位架構盲點偵測專家。你的任務是找出 Zhiyan Legal 儲存庫中「大家都覺得正常但其實有問題」的架構瑕疵。

重點維度（交叉驗證視角）：
1. **隱含耦合**: 兩個看似不相關的模組之間是否存在隱含的約定或依賴？
2. **技術債**: 哪些地方為了快速迭代而留下了「以後再修」的技術債？
3. **可維護性**: 新人加入需要多久才能上手？文檔+程式碼的 onboarding 體驗如何？
4. **水平擴展性**: 如果流量成長 10 倍，哪個元件會最先撐不住？
5. **未來風險**: 目前的架構選擇中有哪些可能在未來一年內變成瓶頸？

以 JSON 格式輸出，key 為 "findings"：
```json
{
  "findings": [
    {
      "category": "hidden_coupling|tech_debt|maintainability|scalability|future_risk",
      "severity": "critical|major|minor",
      "location": "問題位置",
      "issue": "問題描述 (繁體中文, 40字內)",
      "suggestion": "具體改善建議",
      "confidence": 0.0~1.0
    }
  ]
}
```
請嚴格遵守 JSON 格式。""",
}

async def call_model(model_key: str) -> dict:
    """Call a single model with its review prompt."""
    model_id, base_url, key_var = MODELS[model_key]
    api_key = os.getenv(key_var, "")
    if not api_key:
        return {"model": model_key, "error": f"Missing {key_var}", "findings": []}
    
    start = time.perf_counter()
    
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(120.0),
        limits=httpx.Limits(max_keepalive_connections=2, max_connections=5),
    )
    client = AsyncOpenAI(base_url=base_url, api_key=api_key, http_client=http_client)
    
    try:
        response = await client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": REVIEW_PROMPTS[model_key]},
                {"role": "user", "content": f"以下為 Zhiyan Legal 儲存庫完整架構摘要，請依你的角色審查：\n\n{REPO_PROFILE}"},
            ],
            temperature=0.2,
            max_tokens=4096,
        )
        content = response.choices[0].message.content or ""
        elapsed = time.perf_counter() - start
        print(f"  ✅ {model_key:20s} ({elapsed:.1f}s) 收到 {len(content)} chars")
        return {"model": model_key, "response": content, "elapsed_s": round(elapsed, 1)}
    except Exception as e:
        elapsed = time.perf_counter() - start
        print(f"  ❌ {model_key:20s} ({elapsed:.1f}s) 錯誤: {e}")
        return {"model": model_key, "error": str(e), "response": "", "elapsed_s": round(elapsed, 1)}
    finally:
        await http_client.aclose()


def extract_findings(model_key: str, raw: str) -> list:
    """Extract findings from model response."""
    import re
    try:
        # Try to find JSON block
        if "```json" in raw:
            blocks = re.findall(r"```json\s*\n?(.*?)\n?```", raw, re.DOTALL)
            for b in reversed(blocks):
                data = json.loads(b.strip())
                if isinstance(data, dict) and "findings" in data:
                    return data["findings"]
        # Try direct parse
        data = json.loads(raw.strip())
        if isinstance(data, dict) and "findings" in data:
            return data["findings"]
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass
    return []


async def main():
    print("=" * 70)
    print("📐 智研 Legal 儲存庫架構健康檢查 — 4 模型平行審查")
    print("=" * 70)
    
    print("\n📄 Repo Profile:")
    for line in REPO_PROFILE.strip().split("\n"):
        print(f"   {line}")
    
    print(f"\n🚀 呼叫 {len(MODELS)} 模型 (asyncio.gather parallel)...")
    results = await asyncio.gather(*[call_model(k) for k in MODELS])
    
    print("\n" + "=" * 70)
    print("📋 審查結果彙整")
    print("=" * 70)
    
    all_findings = []
    for r in results:
        model = r["model"]
        raw = r.get("response", "")
        error = r.get("error")
        
        if error:
            print(f"\n  ❌ {model}: {error}")
            continue
        
        findings = extract_findings(model, raw)
        print(f"\n  {model} — {len(findings)} 項發現 ({r.get('elapsed_s', '?')}s)")
        
        for f in findings:
            sev = f.get("severity", "minor")
            icon = {"critical": "🔴", "major": "🟠", "minor": "🔵"}.get(sev, "⚪")
            cat = f.get("category", "?")
            issue = f.get("issue", "?")
            loc = f.get("location", "")
            sug = f.get("suggestion", "")
            print(f"    {icon} [{sev:8s}] {cat:20s} | {issue}")
            if sug:
                print(f"       → {sug}")
        
        for f in findings:
            f["_reviewer"] = model
        all_findings.extend(findings)
    
    # ── Summary ──
    print("\n" + "=" * 70)
    print("📊 總計")
    print("=" * 70)
    critical = [f for f in all_findings if f.get("severity") == "critical"]
    major = [f for f in all_findings if f.get("severity") == "major"]
    minor = [f for f in all_findings if f.get("severity") == "minor"]
    print(f"   總共: {len(all_findings)} 項發現")
    print(f"   🔴 Critical: {len(critical)}")
    print(f"   🟠 Major:    {len(major)}")
    print(f"   🔵 Minor:    {len(minor)}")
    
    # Save to file
    out = {
        "repo": "zhiyan-legal v3.7.2",
        "total_findings": len(all_findings),
        "by_severity": {"critical": len(critical), "major": len(major), "minor": len(minor)},
        "findings": all_findings,
        "reports": [
            {"model": r["model"], "elapsed_s": r.get("elapsed_s"), "error": r.get("error"), "raw_response": r.get("response", "")[:500]}
            for r in results
        ],
    }
    out_path = "/home/hsieh89t_gmail_com/zhiyan-legal/results/architecture_health_check.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n💾 完整報告儲存: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
