#!/usr/bin/env python3
"""
run_arch_health_check.py — 架構健康診斷腳本
從 src/zhiyan_legal/config.py 統一入口讀取設定，
驗證各子系統的檔案結構與設定完整性。

用法：
    python scripts/run_arch_health_check.py
"""

import sys
import os
from pathlib import Path

# 確保 src/ 在 PYTHONPATH
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from zhiyan_legal.config import settings

CHECKS = []

def check(name: str, passed: bool, detail: str = "") -> None:
    status = "✅" if passed else "❌"
    print(f"  {status} {name}" + (f"  ({detail})" if detail else ""))
    CHECKS.append(passed)


def main() -> int:
    print("\n🔍 zhiyan-legal 架構健康診斷\n" + "=" * 40)

    # --- 設定層 ---
    print("\n[1] 設定層")
    check("ZHIYAN_API_KEY",    bool(settings.api_key),      settings.api_base_url)
    check("AGNES_API_KEY_1",   bool(settings.agnes_key_1))
    check("AGNES_API_KEY_2",   bool(settings.agnes_key_2))
    check("GEMINI_API_KEY",    bool(settings.gemini_api_key))

    # --- 套件結構 ---
    print("\n[2] 套件結構")
    src = REPO_ROOT / "src" / "zhiyan_legal"
    check("src/zhiyan_legal/__init__.py",       (src / "__init__.py").exists())
    check("src/zhiyan_legal/config.py",         (src / "config.py").exists())
    check("src/zhiyan_legal/engine.py",         (src / "engine.py").exists())
    check("src/zhiyan_legal/schemas/",          (src / "schemas").is_dir())
    check("src/zhiyan_legal/schemas/judgment.py",(src / "schemas" / "judgment.py").exists())

    # --- 資料層 ---
    print("\n[3] 資料層")
    data = REPO_ROOT / "data"
    check("data/ 目錄存在",   data.is_dir())
    check("DB 路徑設定",       bool(settings.db_path),  settings.db_path)

    # --- 合議庭 ---
    print("\n[4] 合議庭")
    committee = REPO_ROOT / "committee"
    check("committee/runner.py",  (committee / "runner.py").exists())
    check("committee/core.py",    (committee / "core.py").exists())
    check("committee/config.yaml",(committee / "config.yaml").exists())

    # --- 廢棄路徑警告 ---
    print("\n[5] 廢棄路徑檢查")
    stale_root_pkg = REPO_ROOT / "zhiyan_legal" / "schemas" / "judgment.py"
    if stale_root_pkg.exists():
        content = stale_root_pkg.read_text()
        is_shim = "Deprecated" in content
        check("zhiyan_legal/schemas/judgment.py 已改為 shim", is_shim,
              "尚未轉換，請手動確認" if not is_shim else "OK")

    stale_audits = [
        "audit_results.json", "audit_prompt_engineering.json",
        "audit-governance-security.json", "audit_test_and_data.json",
    ]
    for f in stale_audits:
        path = REPO_ROOT / f
        if path.exists():
            check(f"根目錄 {f} 已移除", False, "請移至 audit/ 目錄")

    # --- 結果 ---
    total = len(CHECKS)
    passed = sum(CHECKS)
    print(f"\n{'='*40}")
    print(f"結果：{passed}/{total} 通過")
    if passed == total:
        print("🟢 架構健康")
    elif passed >= total * 0.8:
        print("🟡 輕微問題，建議修復")
    else:
        print("🔴 架構問題較多，請優先修復")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
