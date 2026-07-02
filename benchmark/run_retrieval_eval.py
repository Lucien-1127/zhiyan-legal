"""法條檢索評測執行器

用法：
    # 需要先設定好 RAG 資料庫與 API key
    PYTHONPATH=src python benchmark/run_retrieval_eval.py

輸出：
    benchmark/results/retrieval-eval-YYYY-MM-DD.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import List


def load_benchmark(path: str = "benchmark/retrieval-100.json") -> List[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    print(f"✅ 載入評測集：{len(data['queries'])} 題")
    print(f"   涵蓋法域：{', '.join(f'{k}={v}' for k, v in data['meta']['domain_coverage'].items())}")
    return data["queries"]


def run_rag_retrieval(query: str) -> List[str]:
    """透過 zhiyan-legal RAG 檢索法條

    回傳檢索到的條號清單（如 ['§354', '§359']）
    需有 RAG 資料庫才能實際執行。
    """
    # TODO: 實際串接 src/zhiyan_legal/ 的 RAG 檢索
    # 暫時僅回傳空值供測試
    return []


def evaluate(queries: List[dict]):
    total = len(queries)
    recall_at_5_sum = 0.0
    precision_at_5_sum = 0.0
    details = []

    for q in queries:
        qid = q["id"]
        expected = set(q["expected_articles"])
        retrieved = run_rag_retrieval(q["query"])

        if not retrieved:
            details.append({
                "id": qid, "query": q["query"][:40],
                "expected": list(expected), "retrieved": [],
                "recall@5": 0.0, "precision@5": 0.0,
                "status": "pending",
            })
            continue

        top5 = retrieved[:5]
        hits = len(set(top5) & expected)
        recall = hits / len(expected) if expected else 0
        precision = hits / len(top5) if top5 else 0

        recall_at_5_sum += recall
        precision_at_5_sum += precision

        details.append({
            "id": qid, "query": q["query"][:40],
            "expected": list(expected), "retrieved": top5,
            "recall@5": round(recall, 3),
            "precision@5": round(precision, 3),
            "status": "done",
        })

    report = {
        "total_queries": total,
        "executed": sum(1 for d in details if d["status"] == "done"),
        "pending": sum(1 for d in details if d["status"] == "pending"),
        "avg_recall@5": round(recall_at_5_sum / total, 3),
        "avg_precision@5": round(precision_at_5_sum / total, 3),
        "details": details,
    }

    output_dir = Path("benchmark/results")
    output_dir.mkdir(exist_ok=True)
    import datetime
    output_path = output_dir / f"retrieval-eval-{datetime.date.today().isoformat()}.json"
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n📊 結果摘要：")
    print(f"   執行：{report['executed']} 題 / 待執行：{report['pending']} 題")
    if report['executed'] > 0:
        print(f"   Avg Recall@5: {report['avg_recall@5']:.1%}")
        print(f"   Avg Precision@5: {report['avg_precision@5']:.1%}")
    print(f"   報告：{output_path}")

    return report


if __name__ == "__main__":
    queries = load_benchmark()
    report = evaluate(queries)
    sys.exit(0 if report["executed"] == report["total_queries"] else 1)
