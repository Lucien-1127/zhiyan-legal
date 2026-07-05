"""快速法條檢索評測 — 本機 numpy + sentence-transformers，不需 Qdrant

用法：
    PYTHONPATH=src python benchmark/run_retrieval_eval.py
"""
from __future__ import annotations

import json, sys, datetime, numpy as np
from pathlib import Path
from typing import List, Dict
from sentence_transformers import SentenceTransformer

def load_benchmark(path: str = "benchmark/retrieval-100.json") -> List[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    print(f"📋 評測集：{len(data['queries'])} 題")
    return data["queries"]

def load_articles(articles_dir: str = "data/articles") -> List[Dict]:
    """載入法條資料，建立檢索索引"""
    # 絕對路徑
    base = Path("C:/Users/ysga1/zhiyan-legal/data/articles")
    records = []
    stat_map = {
        "A0030055": "行政程序法", "A0030154": "行政訴訟法", "A0030159": "訴願法",
        "B0000001": "民法總則", "B0010001": "民法債編",
        "C0000001": "民法物權編", "C0000008": "民法親屬編",
        "C0010001": "民法繼承編",
        "G0340003": "刑法總則", "G0340080": "刑法分則",
        "G0400001": "刑事訴訟法",
        "I0030019": "民事訴訟法", "J0080001": "強制執行法",
        "J0080041": "破產法",
        "N0030001": "公司法", "N0030014": "票據法",
        "N0030020": "海商法", "N0050001": "保險法",
        "N0050021": "證券交易法",
        "T0030001": "勞動基準法",
        "U0010001": "國家賠償法",
    }
    for f in sorted(base.glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        law_name = stat_map.get(f.stem, f.stem)
        for date_key, content in data.items():
            if isinstance(content, dict):
                for art_num, art_text in content.items():
                    if isinstance(art_text, str) and len(art_text) > 20:
                        art_id = f"§{art_num}"
                        records.append({
                            "id": art_id,
                            "title": f"{law_name} 第{art_num}條",
                            "text": art_text[:500],
                            "law": law_name,
                            "article": art_id,
                        })
                break  # 只取第一個日期
    return records

def build_index(records: List[Dict], model: SentenceTransformer):
    texts = [r["text"] for r in records]
    vecs = model.encode(texts, show_progress_bar=True)
    return np.array(vecs)

def search(query_vec: np.ndarray, index: np.ndarray, records: List[Dict], top_k: int = 5):
    sims = np.dot(index, query_vec) / (np.linalg.norm(index, axis=1) * np.linalg.norm(query_vec) + 1e-10)
    top_indices = np.argsort(sims)[::-1][:top_k]
    return [(records[i]["id"], float(sims[i])) for i in top_indices]

def extract_article_numbers(text: str) -> set:
    """從 title 中提取條號（如 §354）"""
    import re
    return set(re.findall(r'§(\d+(?:-\d+)?)', text))

def evaluate(queries: List[dict], records: List[Dict], model: SentenceTransformer):
    print(f"🔨 建立法條索引（{len(records)} 篇）...")
    index = build_index(records, model)
    print("✅ 索引就緒\n")

    recall_sum, precision_sum = 0.0, 0.0
    domain_stats: Dict[str, list] = {}
    details = []

    for q in queries:
        qid = q["id"]
        domain = q.get("domain", "其他")
        expected = set(q["expected_articles"])
        query_vec = model.encode(q["query"])
        results = search(query_vec, index, records, top_k=5)

        retrieved = []
        for rid, score in results:
            # find article number
            match = [r for r in records if r["id"] == rid]
            if match:
                nums = extract_article_numbers(match[0]["title"])
                retrieved.extend(nums)

        retrieved = retrieved[:5]
        hits = len(set(retrieved) & expected)
        recall = hits / len(expected) if expected else 0.0
        precision = hits / len(retrieved) if retrieved else 0.0

        recall_sum += recall
        precision_sum += precision

        if domain not in domain_stats:
            domain_stats[domain] = []
        domain_stats[domain].append(recall)

        details.append({
            "id": qid, "query": q["query"][:50],
            "domain": domain,
            "expected": sorted(expected),
            "retrieved": retrieved,
            "recall@5": round(recall, 3),
            "precision@5": round(precision, 3),
        })

    avg_recall = recall_sum / len(queries)
    avg_precision = precision_sum / len(queries)

    print(f"\n{'='*50}")
    print(f"📊 法條檢索評測結果")
    print(f"{'='*50}")
    print(f"   總題數: {len(queries)}")
    print(f"   Avg Recall@5: {avg_recall:.1%}")
    print(f"   Avg Precision@5: {avg_precision:.1%}")
    print(f"\n   各法域 Recall@5:")
    for domain, recalls in sorted(domain_stats.items()):
        avg = sum(recalls) / len(recalls)
        print(f"     {domain:12s}: {avg:.1%} ({len(recalls)} 題)")

    # Miss rate
    zero_recall = sum(1 for d in details if d["recall@5"] == 0.0)
    print(f"\n   完全未檢出: {zero_recall}/{len(queries)} ({zero_recall/len(queries):.1%})")

    return {
        "avg_recall@5": round(avg_recall, 3),
        "avg_precision@5": round(avg_precision, 3),
        "total": len(queries),
        "zero_recall": zero_recall,
        "by_domain": {d: round(sum(r)/len(r), 3) for d, r in domain_stats.items()},
        "details": details,
    }

if __name__ == "__main__":
    queries = load_benchmark()
    records = load_articles()
    if not records:
        print("❌ 找不到法條資料（data/articles/ 為空）")
        sys.exit(1)

    model = SentenceTransformer("all-MiniLM-L6-v2")
    report = evaluate(queries, records, model)

    output_dir = Path("benchmark/results")
    output_dir.mkdir(exist_ok=True)
    today = datetime.date.today().isoformat()
    output_path = output_dir / f"retrieval-eval-{today}.json"
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n📄 報告寫入: {output_path}")
