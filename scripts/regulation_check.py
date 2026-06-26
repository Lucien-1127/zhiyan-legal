#!/usr/bin/env python3
"""
regulation_check.py — 法規異動每日排程腳本

用法（cron 用）：
    python3 regulation_check.py              # 每日查核 + 同步索引
    python3 regulation_check.py --status     # 只檢查是否有異動
    python3 regulation_check.py --report     # 產出週報告

回傳值：
    0 = 全部無異動
    1 = 有異動
    2 = 錯誤

可從 Hermes cron job 呼叫：
    python3 ~/zhiyan-legal/scripts/regulation_check.py
"""

import json
import os
import sys
from datetime import datetime

# 加入專案路徑
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_DIR, "src"))

from zhiyan_legal.regulation_tracker import RegulationTracker


def main():
    tracker = RegulationTracker()
    tracker.sync_index(force=False)
    results = tracker.check_all()

    changed = [r for r in results if r.get("changed")]
    errors = [r for r in results if r.get("status") == "error"]

    if errors:
        print(f"[法規異動] 錯誤 ({len(errors)} 部)：")
        for r in errors:
            print(f"  ❌ {r['name']}: {r.get('error')}")
        return 2

    if changed:
        print(f"[法規異動] ⚠ 發現 {len(changed)} 部法規異動！")
        for r in changed:
            print(f"  ⚠ {r['name']}  v{r['old_version']} → v{r['new_version']}")
            meta = tracker.law_meta(r["pcode"])
            if meta:
                print(f"     全國法規資料庫：https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode={r['pcode']}")
        return 1

    print(f"[法規異動] ✓ 全部無異動（{len(results)} 部）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
