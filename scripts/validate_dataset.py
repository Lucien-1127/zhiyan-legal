#!/usr/bin/env python3
"""validate_dataset.py — zhiyan-legal 評估資料集驗證腳本
用法: python scripts/validate_dataset.py data/eval_queries.json
"""
import json, sys, re
from pathlib import Path

REQUIRED_FIELDS = ["id","version","route","difficulty","query_text","ground_truth","ablation_flags","metadata"]
VALID_ROUTES = {"QC","RESEARCH","REPORT","CONSULTANT","TUTOR","TA","LITIGATION","SAFETY","CROSS_JUR"}
VALID_DIFFICULTIES = {"STANDARD","EDGE_CASE"}
VALID_GATE_TRIGGERS = {"NONE","UNCERTAINTY_MARKER","HUMAN_REVIEW","SAFETY_ABORT"}
VALID_CONFIDENCE = {"HIGH","MEDIUM","LOW"}
VALID_SAFETY = {"RL0","RL1","RL2","RL3","N/A"}
ID_PATTERN = re.compile(r"^Q\d{3}$")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

def validate_query(q, idx):
    errors = []
    qid = q.get("id", f"idx:{idx}")
    for f in REQUIRED_FIELDS:
        if f not in q: errors.append(f"{qid}: 缺少必要欄位 '{f}'")
    if "id" in q and not ID_PATTERN.match(q["id"]): errors.append(f"{qid}: id 格式錯誤")
    if "version" in q and not DATE_PATTERN.match(q["version"]): errors.append(f"{qid}: version 格式錯誤")
    if "route" in q and q["route"] not in VALID_ROUTES: errors.append(f"{qid}: route 不合法")
    if "difficulty" in q and q["difficulty"] not in VALID_DIFFICULTIES: errors.append(f"{qid}: difficulty 不合法")
    if "safety_level" in q and q["safety_level"] not in VALID_SAFETY: errors.append(f"{qid}: safety_level 不合法")
    gt = q.get("ground_truth", {})
    if "expected_gate_trigger" in gt and gt["expected_gate_trigger"] not in VALID_GATE_TRIGGERS:
        errors.append(f"{qid}: expected_gate_trigger 不合法")
    if "expected_confidence" in gt and gt["expected_confidence"] not in VALID_CONFIDENCE:
        errors.append(f"{qid}: expected_confidence 不合法")
    if q.get("route") == "SAFETY" and q.get("safety_level") == "N/A":
        errors.append(f"{qid}: SAFETY route 必須指定 safety_level")
    if q.get("difficulty") == "EDGE_CASE":
        rq = q.get("metadata", {}).get("rq_target", [])
        if "RQ3" not in rq: errors.append(f"{qid}: ⚠️  EDGE_CASE 建議包含 RQ3（目前: {rq}）")
    for s in gt.get("statutes", []):
        if not s.get("moj_verified", False):
            errors.append(f"{qid}: ⚠️  {s.get('law_name')} {s.get('article')} moj_verified=False")
    return errors

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "data/eval_queries.json"
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    queries = data.get("queries", [])
    info = data.get("dataset_info", {})
    print(f"\n🔍 驗證：{path}")
    print(f"   {len(queries)} / {info.get('total_planned',200)} queries")
    all_errors = []
    ids = [q.get("id","?") for q in queries]
    for i, q in enumerate(queries): all_errors.extend(validate_query(q, i))
    dup = [i for i in ids if ids.count(i) > 1]
    if dup: all_errors.append(f"重複 ID：{set(dup)}")
    from collections import Counter
    rc = Counter(q.get("route","?") for q in queries)
    print("\n📊 路由分布：", dict(sorted(rc.items())))
    print(f"   EDGE_CASE: {sum(1 for q in queries if q.get('difficulty')=='EDGE_CASE')}")
    warnings = [e for e in all_errors if "⚠️" in e]
    errors = [e for e in all_errors if "⚠️" not in e]
    if errors:
        print(f"\n❌ 錯誤（{len(errors)}）：")
        for e in errors: print(f"   {e}")
    if warnings:
        print(f"\n⚠️  待驗證（{len(warnings)}）：")
        for w in warnings[:5]: print(f"   {w}")
        if len(warnings) > 5: print(f"   ... 還有 {len(warnings)-5} 個")
    if not errors:
        print(f"\n✅ 驗證通過！")
    else:
        print(f"\n💥 請修正 {len(errors)} 個錯誤")
        sys.exit(1)

if __name__ == "__main__":
    main()
